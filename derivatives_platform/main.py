"""Demo: run the platform for a few seconds with a sample book."""
import argparse
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from dpp.engine import Engine
from dpp.market_data import SimulatedFeed
from dpp.models import Future, Option, OptionType
from dpp.pricing import black_scholes
from dpp.risk import Alert, RiskChecker, RiskLimits


def build_book(engine: Engine, spots: dict[str, float]) -> None:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=30)
    r, vol = engine.rate, engine.vols["AAPL"]

    call = Option("AAPL-C-190", "AAPL", 190.0, exp, OptionType.CALL)
    put = Option("AAPL-P-180", "AAPL", 180.0, exp, OptionType.PUT)
    fut = Future("ES-FUT", "ES", now + timedelta(days=90))

    t = call.time_to_expiry(now)
    engine.book_trade(call, +20, black_scholes(OptionType.CALL, spots["AAPL"], 190, t, r, vol).price)
    engine.book_trade(put, -15, black_scholes(OptionType.PUT, spots["AAPL"], 180, t, r, vol).price)
    engine.book_trade(fut, +2, spots["ES"])


def printer(event: dict) -> None:
    kind = event["type"]
    if kind == "trade":
        t = event["trade"]
        print(f"[TRADE #{t.trade_id}] {t.quantity:+d} {t.instrument.symbol} @ {t.price:.4f}")
    elif kind == "alert":
        print(f"  !! {event['alert']}")
    elif kind == "snapshot":
        T = event["totals"]
        print(f"{event['ts']:%H:%M:%S} "
              f"Δ={T['delta']:>9,.1f} Γ={T['gamma']:>7,.2f} ν={T['vega']:>9,.1f} "
              f"Θ={T['theta']:>8,.1f} PnL={T['total_pnl']:>10,.2f}")


async def main(duration: float) -> None:
    spots = {"AAPL": 185.0, "ES": 5200.0}
    engine = Engine(rate=0.05, vols={"AAPL": 0.28, "ES": 0.16},
                    risk=RiskChecker(RiskLimits(max_abs_delta=1_500)))
    engine.subscribe(printer)
    engine.spots.update(spots)
    build_book(engine, spots)

    queue: asyncio.Queue = asyncio.Queue(maxsize=10_000)
    feed = SimulatedFeed(spots, annual_vol=0.3, interval=0.5, seed=42)

    tasks = [asyncio.create_task(feed.run(queue)),
             asyncio.create_task(engine.run(queue))]
    try:
        await asyncio.sleep(duration)
    finally:
        feed.stop()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    print(f"\nProcessed {engine.ticks_processed} ticks, {len(engine.trades)} trades booked.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--seconds", type=float, default=10.0)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main(args.seconds))
