"""Forecast accuracy as pure functions. Censored days (a stockout hid part of the demand) never count as misses for
being above the observed value: they are scored one-sided and kept out of WAPE, bias and band coverage."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .forecast import interpolate_quantile

PRIMARY_Q = 0.74


@dataclass(frozen=True)
class ScoredPoint:
    actual: float
    forecast: float  # p50
    p10: float
    p90: float
    censored: bool = False
    baseline: float | None = None
    levels: tuple[tuple[float, float], ...] = ()  # extra (level, value) pairs such as (0.2, v), (0.8, v)

    def at(self, q: float) -> float:
        lv = {0.1: self.p10, 0.5: self.forecast, 0.9: self.p90, **dict(self.levels)}
        return interpolate_quantile(lv, q)  # type: ignore[return-value]


def pinball_loss(actual: float, pred: float, q: float) -> float:
    diff = actual - pred
    return max(q * diff, (q - 1.0) * diff)


def censored_pinball_loss(actual: float, pred: float, q: float) -> float:
    """The actual is only a lower bound of demand: a prediction at or above it cannot be wrong."""
    return 0.0 if pred >= actual else pinball_loss(actual, pred, q)


def _r(x: float | None) -> float | None:
    return None if x is None else round(x, 4)


def summarize(points: Iterable[ScoredPoint]) -> dict:
    pts = list(points)
    ok, cens = [p for p in pts if not p.censored], [p for p in pts if p.censored]
    total = sum(p.actual for p in ok)
    wape = sum(abs(p.actual - p.forecast) for p in ok) / total if total > 0 else None
    bias = sum(p.forecast - p.actual for p in ok) / total if total > 0 else None
    base = [p for p in ok if p.baseline is not None]
    base_total = sum(p.actual for p in base)
    wape_base = sum(abs(p.actual - p.baseline) for p in base) / base_total if base_total > 0 else None  # type: ignore[operator]
    return {
        "wape": _r(wape), "bias": _r(bias),
        "coverage_p10_p90": _r(sum(1 for p in ok if p.p10 <= p.actual <= p.p90) / len(ok)) if ok else None,
        "wape_baseline": _r(wape_base),
        "pinball_074": _r(sum(pinball_loss(p.actual, p.at(PRIMARY_Q), PRIMARY_Q) for p in ok) / len(ok)) if ok else None,
        "censored_coverage": _r(sum(1 for p in cens if p.forecast >= p.actual) / len(cens)) if cens else None,
        "censored_pinball_074": _r(sum(censored_pinball_loss(p.actual, p.at(PRIMARY_Q), PRIMARY_Q) for p in cens) / len(cens))
        if cens else None,
        "n_days": len(ok), "n_censored": len(cens),
    }


def segment(items: Iterable[tuple[str, ScoredPoint]]) -> dict[str, dict]:
    groups: dict[str, list[ScoredPoint]] = {}
    for key, p in items:
        groups.setdefault(key, []).append(p)
    return {k: summarize(v) for k, v in sorted(groups.items())}


def shelf_life_class(days: int | None) -> str:
    """1 day / 2-3 days / 4-14 days (still perishable) / non-perishable (none or longer than 14 days)."""
    if days is None or days > 14:
        return "non_perishable"
    return "1" if days <= 1 else "2-3" if days <= 3 else "4-14"
