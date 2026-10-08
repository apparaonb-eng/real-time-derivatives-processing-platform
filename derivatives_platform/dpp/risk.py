"""Post-trade risk limits and alerting."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RiskLimits:
    max_abs_delta: float = 5_000.0     # share-equivalent
    max_abs_gamma: float = 500.0
    max_abs_vega: float = 20_000.0
    max_loss: float = -50_000.0        # total P&L floor


@dataclass
class Alert:
    metric: str
    value: float
    limit: float

    def __str__(self) -> str:
        return f"LIMIT BREACH {self.metric}: {self.value:,.2f} (limit {self.limit:,.2f})"


@dataclass
class RiskChecker:
    limits: RiskLimits = field(default_factory=RiskLimits)

    def check(self, totals: dict[str, float]) -> list[Alert]:
        alerts: list[Alert] = []
        L = self.limits
        if abs(totals["delta"]) > L.max_abs_delta:
            alerts.append(Alert("delta", totals["delta"], L.max_abs_delta))
        if abs(totals["gamma"]) > L.max_abs_gamma:
            alerts.append(Alert("gamma", totals["gamma"], L.max_abs_gamma))
        if abs(totals["vega"]) > L.max_abs_vega:
            alerts.append(Alert("vega", totals["vega"], L.max_abs_vega))
        if totals["total_pnl"] < L.max_loss:
            alerts.append(Alert("total_pnl", totals["total_pnl"], L.max_loss))
        return alerts
