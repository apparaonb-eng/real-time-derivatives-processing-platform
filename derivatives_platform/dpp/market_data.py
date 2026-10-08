"""Simulated real-time market data feed (geometric Brownian motion)."""
from __future__ import annotations

import asyncio
import math
import random
from datetime import datetime, timezone

from .models import Tick


class SimulatedFeed:
    """Publishes ticks for several underlyings onto an asyncio queue."""

    TIME_SCALE = 5000  # exaggerate time so demo price moves are visible

    def __init__(self, start_prices: dict[str, float], annual_vol: float = 0.25,
                 interval: float = 0.2, drift: float = 0.0, seed: int | None = None):
        self.prices = dict(start_prices)
        self.annual_vol = annual_vol
        self.drift = drift
        self.interval = interval
        self._rng = random.Random(seed)
        self._running = False

    def _step(self, price: float) -> float:
        dt = self.interval / (252 * 6.5 * 3600) * self.TIME_SCALE  # in years
        z = self._rng.gauss(0.0, 1.0)
        return price * math.exp((self.drift - 0.5 * self.annual_vol ** 2) * dt
                                + self.annual_vol * math.sqrt(dt) * z)

    async def run(self, queue: asyncio.Queue) -> None:
        self._running = True
        while self._running:
            for sym in self.prices:
                self.prices[sym] = self._step(self.prices[sym])
                await queue.put(Tick(sym, round(self.prices[sym], 4),
                                     datetime.now(timezone.utc)))
            await asyncio.sleep(self.interval)

    def stop(self) -> None:
        self._running = False
