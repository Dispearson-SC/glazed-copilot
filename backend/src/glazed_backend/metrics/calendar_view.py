"""The next days from the case date with their weekday names, holidays and supplier delivery days. Pure.

The weekday is computed here, once, so that no model has to derive it from an ISO date."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

WEEKDAYS_ES = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
CALENDAR_DAYS = 14


def weekday_es(d: date) -> str:
    return WEEKDAYS_ES[d.weekday()]


def build_calendar(as_of: date, holidays: dict[date, str], suppliers: list[dict[str, Any]],
                   days: int = CALENDAR_DAYS) -> list[dict[str, Any]]:
    """`suppliers` rows carry delivery_days as ISO weekdays (1 = Monday ... 7 = Sunday). The calendar is known in
    advance (it is not store data), so days after as_of are listed; they carry no sales or stock numbers."""
    ordered = sorted(suppliers, key=lambda s: s["supplier_id"])
    out = []
    for i in range(days):
        d = as_of + timedelta(days=i)
        row: dict[str, Any] = {"date": d.isoformat(), "weekday_es": weekday_es(d), "is_today": i == 0,
                               "is_weekend": d.weekday() >= 5}
        if holidays.get(d):
            row["holiday"] = holidays[d]
        row["delivery_suppliers"] = [{"supplier_id": s["supplier_id"], "supplier_name": s.get("supplier_name")}
                                     for s in ordered if d.isoweekday() in set(s.get("delivery_days") or ())]
        out.append(row)
    return out
