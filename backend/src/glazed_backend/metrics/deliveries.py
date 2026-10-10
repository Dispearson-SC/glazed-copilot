"""Deliveries the manager can plan around: purchase orders known at as_of (open ones, overdue ones, those received on
as_of) plus the supplier delivery calendar. Receipts after as_of are not known and read as "not received". Pure."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta
from typing import Any

LATE_LOOKBACK_DAYS = 14  # an open order expected longer ago than this is a stale record, not a late delivery


def _po_entry(rows: list[dict[str, Any]], as_of: date) -> tuple[date, dict[str, Any]] | None:
    first = rows[0]
    expected = first["expected_date"]
    received = first.get("received_date")
    received = received if received is not None and received <= as_of else None  # NO LOOK-AHEAD
    lines = sorted(({"sku": r["sku"], "product_name": r.get("product_name") or r["sku"], "qty": r["qty"]} for r in rows),
                   key=lambda l: l["sku"])
    base = {"supplier_id": first["supplier_id"], "supplier_name": first.get("supplier_name"), "po_id": first["po_id"],
            "kind": "open_po", "lines": lines,
            "value_usd": round(sum(r["qty"] * float(r.get("unit_cost") or 0) for r in rows), 2),
            "expected_date": expected.isoformat()}
    if received is not None:
        if received != as_of:
            return None
        return as_of, {**base, "status": "on_time" if received <= expected else "late",
                       "received_date": received.isoformat(), "projected": False}
    if expected <= as_of:
        if expected < as_of - timedelta(days=LATE_LOOKBACK_DAYS):
            return None
        return as_of, {**base, "status": "late", "projected": False}
    return expected, {**base, "status": "expected", "projected": True}


def build_delivery_days(pos: list[dict[str, Any]], suppliers: list[dict[str, Any]], as_of: date, days: int) -> list[dict[str, Any]]:
    """One entry per day in (as_of, as_of + days], plus as_of itself when something was due or received that day."""
    until = as_of + timedelta(days=days)
    by_po: dict[str, list[dict[str, Any]]] = {}
    for r in pos:
        if r["order_date"] <= as_of:
            by_po.setdefault(r["po_id"], []).append(r)
    slots: dict[date, list[dict[str, Any]]] = {as_of + timedelta(days=i): [] for i in range(1, days + 1)}
    for rows in by_po.values():
        entry = _po_entry(rows, as_of)
        if entry is None or entry[0] > until:
            continue
        slots.setdefault(entry[0], []).append(entry[1])
    for sup in suppliers:
        weekdays: Iterable[int] = sup["delivery_days"]
        for i in range(1, days + 1):
            d = as_of + timedelta(days=i)
            if d.isoweekday() in weekdays and not any(x["supplier_id"] == sup["supplier_id"] and x["kind"] == "open_po"
                                                      for x in slots[d]):
                slots[d].append({"supplier_id": sup["supplier_id"], "supplier_name": sup.get("supplier_name"), "po_id": None,
                                 "kind": "scheduled", "lines": [], "value_usd": 0.0, "value_known": False,
                                 "status": "expected", "projected": True})
    return [{"date": d.isoformat(), "projected": d > as_of,
             "deliveries": sorted(slots[d], key=lambda x: (x["kind"] != "open_po", x["supplier_id"], x["po_id"] or ""))}
            for d in sorted(slots) if d > as_of or slots[d]]
