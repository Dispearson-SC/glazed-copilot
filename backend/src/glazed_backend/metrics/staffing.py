"""Staffing benchmark and recommendation, daily basis (the data has no hourly staffing). Pure; rows after as_of ignored."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .demand import quantile

WINDOW_DAYS = 90


def productivity_p50(rows: list[dict[str, Any]], as_of: date, window_days: int = WINDOW_DAYS) -> tuple[float | None, int]:
    """(median transactions per staff hour over store-days, number of store-days) in the window ending at as_of."""
    ratios = [r["transactions"] / r["staff_hours"] for r in rows
              if as_of - timedelta(days=window_days) < r["date"] <= as_of  # NO LOOK-AHEAD
              and r.get("transactions") and r.get("staff_hours") and r["staff_hours"] > 0]
    return (quantile(ratios, 0.5), len(ratios)) if ratios else (None, 0)


def recommended_hours(transactions: dict[str, float], tx_per_staff_hour: float) -> dict[str, float]:
    """Staff hours that serve a {low, mid, high} transaction forecast at the benchmark productivity."""
    return {k: round(v / tx_per_staff_hour, 1) for k, v in transactions.items()}
