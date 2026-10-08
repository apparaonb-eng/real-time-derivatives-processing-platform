"""Real-time processing engine: ticks in -> revalue -> risk -> publish."""
from __future__ import annotations

import asyncio
import itertools
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable

from .models import Future, Instrument, Option, Position, Tick, Trade, Valuation
from .pricing import black_scholes, future_price
from .risk import RiskChecker

log = logging.getLogger("dpp.engine")


class Engine:
    def __init__(self, rate: float = 0.05, div_yield: float = 0.0,
                 vols: dict[str, float] | None = None,
                 risk: RiskChecker | None = None):
        self.rate = rate
        self.div_yield = div_yield
        self.vols = vols or {}                # underlying -> implied vol
        self.default_vol = 0.25
        self.risk = risk or RiskChecker()
        self.spots: dict[str, float] = {}
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []
        self._trade_ids = itertools.count(1)
        self._by_underlying: dict[str, set[str]] = defaultdict(set)
        self._subscribers: list[Callable[[dict], None]] = []
        self.ticks_processed = 0
        self.last_snapshot: dict | None = None

    # ---------- Pub/sub ----------
    def subscribe(self, callback: Callable[[dict], None]) -> None:
        self._subscribers.append(callback)

    def _publish(self, event: dict) -> None:
        for cb in self._subscribers:
            try:
                cb(event)
            except Exception:  # a bad subscriber must not kill the engine
                log.exception("subscriber failed")

    # ---------- Trading ----------
    def book_trade(self, instrument: Instrument, quantity: int, price: float) -> Trade:
        if quantity == 0:
            raise ValueError("quantity must be non-zero")
        trade = Trade(next(self._trade_ids), instrument, quantity, price)
        pos = self.positions.setdefault(instrument.symbol, Position(instrument))
        pos.apply(quantity, price)
        self._by_underlying[instrument.underlying].add(instrument.symbol)
        self.trades.append(trade)
        self._publish({"type": "trade", "trade": trade})
        return trade

    # ---------- Valuation ----------
    def _value(self, pos: Position, now: datetime) -> Valuation | None:
        inst = pos.instrument
        spot = self.spots.get(inst.underlying)
        if spot is None:
            return None
        t = inst.time_to_expiry(now)
        mult = inst.multiplier

        if isinstance(inst, Option):
            vol = self.vols.get(inst.underlying, self.default_vol)
            g = black_scholes(inst.kind, spot, inst.strike, t, self.rate, vol, self.div_yield)
            price, d, gm, vg, th, rh = g.price, g.delta, g.gamma, g.vega, g.theta, g.rho
        else:  # Future
            price = future_price(spot, t, self.rate, self.div_yield)
            d, gm, vg, th, rh = 1.0, 0.0, 0.0, 0.0, 0.0

        scale = pos.quantity * mult
        return Valuation(
            symbol=inst.symbol, quantity=pos.quantity, spot=spot, price=price,
            market_value=scale * price,
            unrealized_pnl=scale * (price - pos.avg_price),
            delta=scale * d, gamma=scale * gm, vega=scale * vg,
            theta=scale * th, rho=scale * rh,
        )

    def snapshot(self) -> dict:
        now = datetime.now(timezone.utc)
        vals: list[Valuation] = []
        for pos in self.positions.values():
            if pos.quantity == 0:
                continue
            v = self._value(pos, now)
            if v:
                vals.append(v)
        totals = {
            "market_value": sum(v.market_value for v in vals),
            "unrealized_pnl": sum(v.unrealized_pnl for v in vals),
            "realized_pnl": sum(p.realized_pnl for p in self.positions.values()),
            "delta": sum(v.delta for v in vals),
            "gamma": sum(v.gamma for v in vals),
            "vega": sum(v.vega for v in vals),
            "theta": sum(v.theta for v in vals),
            "rho": sum(v.rho for v in vals),
        }
        totals["total_pnl"] = totals["unrealized_pnl"] + totals["realized_pnl"]
        return {"type": "snapshot", "ts": now, "valuations": vals, "totals": totals}

    # ---------- Tick processing ----------
    def on_tick(self, tick: Tick) -> None:
        self.spots[tick.symbol] = tick.price
        self.ticks_processed += 1
        if tick.symbol not in self._by_underlying:
            return  # nothing held on this underlying
        snap = self.snapshot()
        self.last_snapshot = snap
        self._publish(snap)
        for alert in self.risk.check(snap["totals"]):
            self._publish({"type": "alert", "alert": alert})

    async def run(self, queue: asyncio.Queue) -> None:
        """Consume ticks until cancelled."""
        while True:
            tick = await queue.get()
            try:
                self.on_tick(tick)
            finally:
                queue.task_done()
