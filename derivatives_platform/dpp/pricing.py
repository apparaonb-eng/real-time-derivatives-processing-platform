"""Pricing library: Black-Scholes-Merton, Greeks, implied volatility, futures."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .models import OptionType


def _pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


@dataclass(frozen=True)
class Greeks:
    price: float
    delta: float
    gamma: float
    vega: float    # per 1 vol point (1%)
    theta: float   # per calendar day
    rho: float     # per 1% rate move


def _d1_d2(s: float, k: float, t: float, r: float, q: float, vol: float):
    vsqrt = vol * math.sqrt(t)
    d1 = (math.log(s / k) + (r - q + 0.5 * vol * vol) * t) / vsqrt
    return d1, d1 - vsqrt


def black_scholes(kind: OptionType, s: float, k: float, t: float,
                  r: float, vol: float, q: float = 0.0) -> Greeks:
    """Price and Greeks for a European option (continuous dividend yield q)."""
    if s <= 0 or k <= 0:
        raise ValueError("spot and strike must be positive")
    if vol <= 0:
        raise ValueError("volatility must be positive")

    # At/after expiry: intrinsic value only
    if t <= 1e-12:
        intrinsic = max(s - k, 0.0) if kind == OptionType.CALL else max(k - s, 0.0)
        delta = (1.0 if s > k else 0.0) if kind == OptionType.CALL else (-1.0 if s < k else 0.0)
        return Greeks(intrinsic, delta, 0.0, 0.0, 0.0, 0.0)

    d1, d2 = _d1_d2(s, k, t, r, q, vol)
    disc_r, disc_q = math.exp(-r * t), math.exp(-q * t)
    gamma = disc_q * _pdf(d1) / (s * vol * math.sqrt(t))
    vega = s * disc_q * _pdf(d1) * math.sqrt(t)
    common_theta = -(s * disc_q * _pdf(d1) * vol) / (2.0 * math.sqrt(t))

    if kind == OptionType.CALL:
        price = s * disc_q * _cdf(d1) - k * disc_r * _cdf(d2)
        delta = disc_q * _cdf(d1)
        theta = common_theta - r * k * disc_r * _cdf(d2) + q * s * disc_q * _cdf(d1)
        rho = k * t * disc_r * _cdf(d2)
    else:
        price = k * disc_r * _cdf(-d2) - s * disc_q * _cdf(-d1)
        delta = -disc_q * _cdf(-d1)
        theta = common_theta + r * k * disc_r * _cdf(-d2) - q * s * disc_q * _cdf(-d1)
        rho = -k * t * disc_r * _cdf(-d2)

    return Greeks(price, delta, gamma, vega / 100.0, theta / 365.0, rho / 100.0)


def implied_vol(kind: OptionType, market_price: float, s: float, k: float,
                t: float, r: float, q: float = 0.0,
                lo: float = 1e-4, hi: float = 5.0, tol: float = 1e-10) -> float:
    """Implied volatility via bisection (robust, no derivatives needed)."""
    if t <= 0:
        raise ValueError("cannot solve implied vol at expiry")

    def f(v: float) -> float:
        return black_scholes(kind, s, k, t, r, v, q).price - market_price

    if f(lo) > 0 or f(hi) < 0:
        raise ValueError("market price outside no-arbitrage bounds")
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        val = f(mid)
        if abs(val) < tol:
            return mid
        lo, hi = (mid, hi) if val < 0 else (lo, mid)
    return 0.5 * (lo + hi)


def future_price(s: float, t: float, r: float, q: float = 0.0) -> float:
    """Cost-of-carry fair value of a future."""
    return s * math.exp((r - q) * t)


def put_call_parity_gap(call: float, put: float, s: float, k: float,
                        t: float, r: float, q: float = 0.0) -> float:
    """C - P - (S e^{-qT} - K e^{-rT}); ~0 when no arbitrage."""
    return call - put - (s * math.exp(-q * t) - k * math.exp(-r * t))
