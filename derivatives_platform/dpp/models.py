"""Domain models: ticks, instruments, trades, positions."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

SECONDS_PER_YEAR = 365.0 * 24 * 3600


class OptionType(str, Enum):
    CALL = "call"
    PUT = "put"


@dataclass(frozen=True)
class Tick:
    """A market data update for an underlying."""
    symbol: str
    price: float
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class Option:
    """European vanilla option."""
    symbol: str          # e.g. AAPL-C-190
    underlying: str
    strike: float
    expiry: datetime
    kind: OptionType
    multiplier: int = 100

    def time_to_expiry(self, now: datetime | None = None) -> float:
        now = now or datetime.now(timezone.utc)
        return max((self.expiry - now).total_seconds(), 0.0) / SECONDS_PER_YEAR


@dataclass(frozen=True)
class Future:
    """Cost-of-carry future on an underlying."""
    symbol: str
    underlying: str
    expiry: datetime
    multiplier: int = 50

    def time_to_expiry(self, now: datetime | None = None) -> float:
        now = now or datetime.now(timezone.utc)
        return max((self.expiry - now).total_seconds(), 0.0) / SECONDS_PER_YEAR


Instrument = Option | Future


@dataclass
class Trade:
    trade_id: int
    instrument: Instrument
    quantity: int        # +long / -short (contracts)
    price: float         # per-unit premium / entry price
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Position:
    instrument: Instrument
    quantity: int = 0
    avg_price: float = 0.0
    realized_pnl: float = 0.0

    def apply(self, qty: int, price: float) -> None:
        """Update position with a fill, tracking average price and realized P&L."""
        mult = self.instrument.multiplier
        if self.quantity == 0 or (self.quantity > 0) == (qty > 0):
            total = self.quantity + qty
            self.avg_price = (self.avg_price * abs(self.quantity) + price * abs(qty)) / abs(total)
            self.quantity = total
            return
        # Reducing / flipping
        closing = min(abs(qty), abs(self.quantity))
        sign = 1 if self.quantity > 0 else -1
        self.realized_pnl += sign * closing * (price - self.avg_price) * mult
        new_qty = self.quantity + qty
        if new_qty == 0:
            self.avg_price = 0.0
        elif (new_qty > 0) != (self.quantity > 0):
            self.avg_price = price  # flipped side
        self.quantity = new_qty


@dataclass
class Valuation:
    """Priced snapshot of a single position."""
    symbol: str
    quantity: int
    spot: float
    price: float
    market_value: float
    unrealized_pnl: float
    delta: float   # share-equivalent
    gamma: float
    vega: float    # per 1 vol point
    theta: float   # per day
    rho: float     # per 1% rate
