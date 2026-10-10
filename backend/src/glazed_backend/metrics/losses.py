"""Lost sales in USD from stockout hours."""
from __future__ import annotations

from datetime import date, timedelta

from .demand import SAMPLE_DAYS, quantile
from .types import DayRow


def lost_sales_window(rows: list[DayRow], price: float, open_hours: float, date_from: date, date_to: date) -> dict[str, float]:
    """lost_sales_usd {low, mid, high} for one SKU over [date_from, date_to].

    mid  = stockout_hours x units sold per open hour on uncensored same-weekday days x price.
    low  = the same restricted to partial-day stockouts (the store still sold that day).
    high = mid with the P75 hourly rate instead of the mean.
    Rates use only days up to the stockout day itself and exclude other stockout days."""
    if open_hours <= 0:
        return {"low": 0.0, "mid": 0.0, "high": 0.0}
    clean = [r for r in rows if r.stockout_hours <= 0]
    low = mid = high = 0.0
    for r in rows:
        if r.stockout_hours <= 0 or not (date_from <= r.date <= date_to):
            continue
        ref = [float(c.sold) for c in clean if c.date.isoweekday() == r.date.isoweekday()
               and r.date - timedelta(days=SAMPLE_DAYS) <= c.date < r.date]
        if not ref:
            ref = [float(c.sold) for c in clean if r.date - timedelta(days=28) <= c.date < r.date]
        if not ref:
            continue
        hours = min(r.stockout_hours, open_hours)
        m = hours * (sum(ref) / len(ref)) / open_hours * price
        mid += m
        high += hours * quantile(ref, 0.75) / open_hours * price
        if r.stockout_hours < open_hours:
            low += m
    return {"low": round(low, 2), "mid": round(mid, 2), "high": round(max(high, mid), 2)}
