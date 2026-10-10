"""Forecast helpers: the same-weekday baseline, empirical quantiles and quantile interpolation. Pure."""
from __future__ import annotations

from datetime import date, timedelta

from .demand import quantile

LEVELS = {"p10": 0.1, "p20": 0.2, "p50": 0.5, "p80": 0.8, "p90": 0.9}
BASELINE_WEEKS = 8


def same_weekday_dates(d: date, n: int = BASELINE_WEEKS, include_d: bool = False) -> list[date]:
    """The `n` previous same-weekday dates of `d` (what day-summary averages for its baseline)."""
    return [d - timedelta(days=7 * k) for k in range(0 if include_d else 1, n + 1)]


def weekday_samples(by_date: dict[date, float], target: date, origin: date, n: int = BASELINE_WEEKS) -> list[float]:
    """Values of the previous `n` same-weekday dates of `target` that are known (date <= origin and present)."""
    return [by_date[x] for x in same_weekday_dates(target, n) if x <= origin and x in by_date]


def empirical_quantiles(samples: list[float]) -> dict[str, float]:
    return {name: quantile([float(s) for s in samples], q) for name, q in LEVELS.items()}


def interpolate_quantile(levels: dict[float, float], q: float) -> float | None:
    """Linear interpolation over known {level: value}; clamped to the outermost known levels."""
    if not levels:
        return None
    xs = sorted(levels)
    if q <= xs[0]:
        return levels[xs[0]]
    if q >= xs[-1]:
        return levels[xs[-1]]
    hi = next(x for x in xs if x >= q)
    lo = max(x for x in xs if x <= q)
    if hi == lo:
        return levels[lo]
    return levels[lo] + (levels[hi] - levels[lo]) * (q - lo) / (hi - lo)
