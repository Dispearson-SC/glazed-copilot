"""Per-SKU stock view for the manager: cover, turnover, value and slow movers. Pure; reads rows <= as_of only."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .demand import SAMPLE_DAYS, uncensor
from .types import DayRow

RECENT_DAYS = 28
SLOW_COVER_DAYS = 28.0  # more than four weeks of stock at the current demand is a slow mover
SORTS = ("days_of_cover", "turnover", "slow")


def _r(x: float | None, nd: int = 2) -> float | None:
    return None if x is None else round(x, nd)


def inventory_item(sku: str, product: dict[str, Any], rows: list[DayRow], as_of: date, open_hours: float) -> dict[str, Any] | None:
    """One SKU's stock line at the end of `as_of`, or None when it has no row in the last 28 days (inactive)."""
    known = sorted((r for r in rows if r.date <= as_of), key=lambda r: r.date)  # NO LOOK-AHEAD
    recent = [r for r in known if r.date > as_of - timedelta(days=RECENT_DAYS)]
    if not recent:
        return None
    window = [r for r in known if r.date > as_of - timedelta(days=SAMPLE_DAYS)]
    demand = uncensor(window, open_hours).demand
    recent_demand = [demand[r.date] for r in recent]
    avg = sum(recent_demand) / len(recent_demand)
    on_hand = known[-1].closing
    sold_28d = sum(r.sold for r in recent)
    mean_stock = sum(r.closing for r in recent) / len(recent)
    cover = on_hand / avg if avg > 0 else None
    last_sale = next((r.date for r in reversed(known) if r.sold > 0), None)
    slow = on_hand > 0 and (sold_28d == 0 or (cover is not None and cover > SLOW_COVER_DAYS))
    return {"sku": sku, "product_name": product["product_name"], "department": product.get("department"),
            "on_hand": on_hand, "avg_daily_demand": _r(avg), "days_of_cover": _r(cover),
            "turnover_28d": _r(sold_28d / mean_stock) if mean_stock > 0 else None,
            "weeks_of_supply": _r(cover / 7) if cover is not None else None,
            "inventory_value_usd": _r(on_hand * float(product.get("unit_cost") or 0)),
            "last_sale_date": last_sale.isoformat() if last_sale else None, "slow_mover": slow}


def sort_items(items: list[dict[str, Any]], by: str) -> list[dict[str, Any]]:
    if by == "days_of_cover":  # emptiest shelf first, unknown cover last
        return sorted(items, key=lambda i: (i["days_of_cover"] is None, i["days_of_cover"] or 0.0, i["sku"]))
    if by == "turnover":  # fastest first
        return sorted(items, key=lambda i: (i["turnover_28d"] is None, -(i["turnover_28d"] or 0.0), i["sku"]))
    if by == "slow":  # slow movers first, the most money tied up first
        return sorted(items, key=lambda i: (not i["slow_mover"], -i["inventory_value_usd"], i["sku"]))
    raise ValueError(f"sort must be one of {', '.join(SORTS)}")
