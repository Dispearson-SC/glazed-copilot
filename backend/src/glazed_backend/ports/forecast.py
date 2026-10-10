"""Forecast ports. A forecaster only produces the model's quantiles; actuals, censoring and the baseline come from the
metrics port, and the application enforces the no-look-ahead rules on top of whatever an adapter returns."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from ..metrics.forecast import LEVELS, interpolate_quantile
from ..metrics.types import SkuSeries


@dataclass(frozen=True)
class ForecastRow:
    """One SKU-day: `forecast` is the p50 (the mean for the baseline) and `quantiles` holds whichever of
    p10/p20/p50/p80/p90 the model provides. `extra` carries model parameters (mu, alpha) when present."""
    sku: str
    date: date
    forecast: float
    quantiles: dict[str, float] = field(default_factory=dict)
    extra: dict[str, float] = field(default_factory=dict)

    def levels(self) -> dict[float, float]:
        lv = {LEVELS[k]: v for k, v in self.quantiles.items() if k in LEVELS}
        lv.setdefault(0.5, self.forecast)
        return lv

    def quantile(self, q: float) -> float | None:
        """Any level: exact when the model provides it, else linear interpolation (clamped to p10..p90)."""
        return interpolate_quantile(self.levels(), q)


@dataclass(frozen=True)
class ForecastResult:
    model: str
    model_version: str
    origin: date  # when the forecast was issued; rows carry no information later than this
    rows: list[ForecastRow]


class ForecastPort(Protocol):
    def forecast(self, store_id: str, as_of: date, skus: list[str] | None, date_from: date, date_to: date,
                 history: list[SkuSeries]) -> ForecastResult | None: ...
    def quantile(self, store_id: str, as_of: date, sku: str, target_date: date, q: float,
                 history: list[SkuSeries]) -> float | None: ...


@dataclass(frozen=True)
class FlowResult:
    model: str
    origin: date
    granularity: str
    transactions: dict[str, float]
    footfall: dict[str, float] | None
    avg_ticket: dict[str, float] | None


class FlowForecastPort(Protocol):
    def flow(self, store_id: str, as_of: date, target_date: date, history: list[dict[str, Any]]) -> FlowResult | None: ...
