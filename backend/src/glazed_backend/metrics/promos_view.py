"""Promotion lifecycle for the manager's promo list. Pure. The data day `as_of` is closed, so a promo whose end date is
as_of is past (its evaluation window is complete)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

STATUSES = ("active", "upcoming", "past")
_ORDER = {s: i for i, s in enumerate(STATUSES)}


def promo_status(start: date, end: date, as_of: date) -> str:
    if start > as_of:
        return "upcoming"
    return "past" if end <= as_of else "active"


def in_window(status: str, start: date, end: date, as_of: date, days: int) -> bool:
    """Active promos always show; past ones that ended within `days`; upcoming ones that start within `days`."""
    if status == "past":
        return end >= as_of - timedelta(days=days)
    if status == "upcoming":
        return start <= as_of + timedelta(days=days)
    return True


def sort_promos(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Active (ending soonest first), upcoming (starting soonest first), then past (most recently ended first)."""
    def key(i: dict[str, Any]) -> tuple:
        st = _ORDER[i["status"]]
        if i["status"] == "active":
            return (st, i["end_date"], i["promo_id"])
        if i["status"] == "upcoming":
            return (st, i["start_date"], i["promo_id"])
        return (st, _neg(i["end_date"]), i["promo_id"])
    return sorted(items, key=key)


def _neg(iso: str) -> int:
    return -date.fromisoformat(iso).toordinal()
