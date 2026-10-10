"""Demand estimation from sales history, corrected for stockouts (censored demand)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .types import DayRow

SAMPLE_DAYS = 56
POOL_DAYS = 28
MIN_WEEKDAY_SAMPLES = 3


def quantile(values: list[float], q: float) -> float:
    """Linear-interpolation quantile (same convention as DuckDB quantile_cont)."""
    if not values:
        return 0.0
    xs = sorted(values)
    pos = q * (len(xs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


@dataclass(frozen=True)
class CensoredDemand:
    demand: dict[date, float]
    censored_dates: frozenset[date]

    @property
    def censored_share(self) -> float:
        return len(self.censored_dates) / len(self.demand) if self.demand else 0.0


def uncensor(rows: list[DayRow], open_hours: float) -> CensoredDemand:
    """Days with stockout_hours > 0 understate demand: demand = sold / (1 - stockout_hours/open_hours).

    The estimate is capped at the p90 of uncensored same-weekday days (all uncensored days if there is
    no same-weekday reference). With no uncensored reference at all, observed sales are kept."""
    clean = [r for r in rows if r.stockout_hours <= 0]
    by_wd: dict[int, list[float]] = {}
    for r in clean:
        by_wd.setdefault(r.date.isoweekday(), []).append(float(r.sold))
    overall = [float(r.sold) for r in clean]
    demand: dict[date, float] = {}
    censored: set[date] = set()
    for r in rows:
        if r.stockout_hours <= 0:
            demand[r.date] = float(r.sold)
            continue
        censored.add(r.date)
        ref = by_wd.get(r.date.isoweekday()) or overall
        cap = quantile(ref, 0.9) if ref else None
        frac = min(1.0, r.stockout_hours / open_hours) if open_hours > 0 else 1.0
        est = r.sold / (1.0 - frac) if frac < 1.0 else None
        if cap is None:
            demand[r.date] = float(r.sold)
        else:
            demand[r.date] = cap if est is None else min(est, cap)
    return CensoredDemand(demand, frozenset(censored))


def weekday_stats(demand: dict[date, float], ref: date, weekday: int) -> tuple[float, float]:
    """(mean, sd) of daily demand for an ISO weekday over the last 56 days up to ref.

    Falls back to the last 28 days pooled when there are fewer than 3 same-weekday samples. The sd has a
    floor of half the Poisson sd so a flat history is not read as certainty."""
    same = [v for d, v in demand.items() if ref - timedelta(days=SAMPLE_DAYS) < d <= ref and d.isoweekday() == weekday]
    xs = same if len(same) >= MIN_WEEKDAY_SAMPLES else [
        v for d, v in demand.items() if ref - timedelta(days=POOL_DAYS) < d <= ref]
    if not xs:
        return 0.0, 0.0
    mean = sum(xs) / len(xs)
    var = sum((x - mean) ** 2 for x in xs) / (len(xs) - 1) if len(xs) > 1 else 0.0
    return mean, max(var ** 0.5, 0.5 * mean ** 0.5)


def horizon_demand(demand: dict[date, float], ref: date, days: list[date]) -> tuple[float, float]:
    """Demand over several future days: means add, variances add (days treated as independent)."""
    mean = var = 0.0
    for d in days:
        m, s = weekday_stats(demand, ref, d.isoweekday())
        mean, var = mean + m, var + s * s
    return mean, var ** 0.5
