import math
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dpp.engine import Engine
from dpp.models import Option, OptionType, Position, Tick
from dpp.pricing import black_scholes, implied_vol, put_call_parity_gap


def test_bs_known_value():
    g = black_scholes(OptionType.CALL, 100, 100, 1.0, 0.05, 0.20)
    assert abs(g.price - 10.4506) < 1e-3
    assert 0.6 < g.delta < 0.7


def test_put_call_parity():
    c = black_scholes(OptionType.CALL, 110, 100, 0.5, 0.03, 0.3, 0.01).price
    p = black_scholes(OptionType.PUT, 110, 100, 0.5, 0.03, 0.3, 0.01).price
    assert abs(put_call_parity_gap(c, p, 110, 100, 0.5, 0.03, 0.01)) < 1e-9


def test_implied_vol_roundtrip():
    price = black_scholes(OptionType.PUT, 95, 100, 0.25, 0.04, 0.37).price
    assert abs(implied_vol(OptionType.PUT, price, 95, 100, 0.25, 0.04) - 0.37) < 1e-6


def test_position_realized_pnl():
    opt = Option("X", "U", 100, datetime.now(timezone.utc) + timedelta(days=10), OptionType.CALL)
    pos = Position(opt)
    pos.apply(10, 2.0)
    pos.apply(-4, 3.0)
    assert pos.quantity == 6
    assert math.isclose(pos.realized_pnl, 4 * 1.0 * 100)


def test_engine_tick_flow():
    eng = Engine(vols={"U": 0.3})
    opt = Option("X", "U", 100, datetime.now(timezone.utc) + timedelta(days=30), OptionType.CALL)
    events = []
    eng.subscribe(events.append)
    eng.spots["U"] = 100
    eng.book_trade(opt, 10, 3.0)
    eng.on_tick(Tick("U", 105.0))
    snaps = [e for e in events if e["type"] == "snapshot"]
    assert snaps and snaps[-1]["totals"]["delta"] > 0
