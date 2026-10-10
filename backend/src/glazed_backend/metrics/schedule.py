"""Delivery calendar and supplier behaviour known at a date."""
from __future__ import annotations

from datetime import date, timedelta

from .demand import quantile
from .types import PurchaseOrder, SupplierProfile

ALL_DAYS = frozenset(range(1, 8))
_NAMES = {"mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 7}


def parse_delivery_days(spec: str | None) -> frozenset[int]:
    """'Mon/Thu' -> {1, 4}. 'Daily', 'Weekly' (the 7-day lead time already sets the cadence) or unknown -> all days."""
    days = {_NAMES[p.strip()[:3].lower()] for p in (spec or "").replace(",", "/").split("/")
            if p.strip()[:3].lower() in _NAMES}
    return frozenset(days) or ALL_DAYS


def first_delivery(order_date: date, lead_days: int, delivery_days: frozenset[int],
                   closed: frozenset[date] = frozenset()) -> date:
    """Earliest valid arrival of an order placed on order_date: lead time, supplier weekday, store open."""
    d = order_date + timedelta(days=max(1, lead_days))
    for _ in range(60):
        if d.isoweekday() in delivery_days and d not in closed:
            return d
        d += timedelta(days=1)
    return d


def next_delivery_after(d: date, delivery_days: frozenset[int], closed: frozenset[date] = frozenset()) -> date:
    return first_delivery(d, 1, delivery_days, closed)


def supplier_profile(supplier_id: str, pos: list[PurchaseOrder], t: date, delivery_days: frozenset[int],
                     std_lead: int, min_order_value: float = 0.0, window_days: int = 180) -> SupplierProfile:
    """Lead time (mean, p90) and on-time rate from orders already received on or before t."""
    got = [p for p in pos if p.received_date is not None and p.received_date <= t
           and p.order_date > t - timedelta(days=window_days)]
    if not got:
        return SupplierProfile(supplier_id, delivery_days, float(std_lead), float(std_lead) + 1.0, 0.9, min_order_value)
    leads = [float((p.received_date - p.order_date).days) for p in got]
    on_time = sum(1 for p in got if p.received_date <= p.expected_date) / len(got)
    return SupplierProfile(supplier_id, delivery_days, sum(leads) / len(leads), quantile(leads, 0.9),
                           on_time, min_order_value)
