"""KPIs against "normal": the same window shifted back by whole weeks, so it covers the same weekdays. Pure."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable

BASELINE_WEEKS = 8
_SCALARS = ("net_sales", "units", "transactions", "footfall", "conversion", "tx_per_staff_hour", "waste_usd", "stockout_hours")
KPI_NAMES = _SCALARS + ("lost_sales_usd",)  # lost sales is a {low, mid, high} range: its delta uses the mid


def _pct(current: float | None, base: float | None) -> float | None:
    if current is None or base is None or base == 0:
        return None
    return round((current - base) / base * 100, 1)


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def with_baseline(read: Callable[[date, date], dict[str, Any]], date_from: date, date_to: date,
                  weeks: int = BASELINE_WEEKS) -> dict[str, Any]:
    """`read(from, to)` returns the KPIs of a window (data <= the case date: every shifted window ends before date_to).
    Adds `baseline` (mean of the previous `weeks` windows of the same length and weekdays that have data) and
    `delta_pct` (current vs baseline, in percent). Without any earlier window both are None."""
    current = read(date_from, date_to)
    seen = []
    for k in range(1, weeks + 1):
        shift = timedelta(days=7 * k)
        got = read(date_from - shift, date_to - shift)
        if got.get("days_with_data", 1):
            seen.append(got)
    if not seen:
        return {**current, "baseline": None, "delta_pct": None}
    base: dict[str, Any] = {"weeks_used": len(seen), "weeks_requested": weeks,
                            "method": f"mean of the previous {weeks} windows of {(date_to - date_from).days + 1} days "
                                      "covering the same weekdays; data up to the case date only"}
    for name in _SCALARS:
        base[name] = _mean([float(s[name]) for s in seen if s.get(name) is not None])
    base["lost_sales_usd"] = {k: _mean([float(s["lost_sales_usd"][k]) for s in seen if s.get("lost_sales_usd")])
                              for k in ("low", "mid", "high")}
    delta = {name: _pct(current.get(name), base[name]) for name in _SCALARS}
    delta["lost_sales_usd"] = _pct((current.get("lost_sales_usd") or {}).get("mid"), base["lost_sales_usd"]["mid"])
    return {**current, "baseline": base, "delta_pct": delta}
