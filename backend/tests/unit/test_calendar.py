"""R1: the briefing and the snapshot carry the next 14 days with their weekday names, so no model computes a weekday."""
from datetime import date

from glazed_backend.metrics.calendar_view import build_calendar, weekday_es
from tests.unit.snapshot_support import env, mkcase, snap  # noqa: F401

SUPPLIERS = [{"supplier_id": "SUP07", "supplier_name": "Costa", "delivery_days": [2, 5]},
             {"supplier_id": "SUP01", "supplier_name": "Norte", "delivery_days": [1, 2, 3, 4, 5, 6, 7]}]


def test_weekday_names_are_spanish_and_correct():
    assert weekday_es(date(2026, 7, 25)) == "sábado"
    assert [weekday_es(date(2026, 7, 20 + i)) for i in range(7)] == [
        "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def test_calendar_covers_14_days_from_as_of_with_flags_holidays_and_deliveries():
    cal = build_calendar(date(2026, 7, 19), {date(2026, 7, 22): "Día de prueba"}, SUPPLIERS)
    assert len(cal) == 14 and cal[0]["date"] == "2026-07-19" and cal[-1]["date"] == "2026-08-01"
    assert cal[0]["is_today"] is True and sum(d["is_today"] for d in cal) == 1
    by = {d["date"]: d for d in cal}
    sat = by["2026-07-25"]
    assert sat["weekday_es"] == "sábado" and sat["is_weekend"] is True
    assert by["2026-07-20"]["is_weekend"] is False
    assert by["2026-07-22"]["holiday"] == "Día de prueba" and "holiday" not in by["2026-07-21"]
    assert [s["supplier_id"] for s in by["2026-07-21"]["delivery_suppliers"]] == ["SUP01", "SUP07"]  # a Tuesday
    assert [s["supplier_id"] for s in by["2026-07-20"]["delivery_suppliers"]] == ["SUP01"]  # a Monday
    assert by["2026-07-21"]["delivery_suppliers"][1] == {"supplier_id": "SUP07", "supplier_name": "Costa"}


def test_snapshot_and_internal_briefing_carry_calendar_and_weekday(env):
    client, _, m = env
    m.holiday_map = {date(2026, 3, 12): "Feriado"}
    m.suppliers_sched = SUPPLIERS
    cid = mkcase(client, "2026-03-10")  # a Tuesday
    s = snap(client, cid)
    assert s["as_of_weekday_es"] == "martes"
    assert s["calendar"][0] == {"date": "2026-03-10", "weekday_es": "martes", "is_today": True, "is_weekend": False,
                                "delivery_suppliers": [{"supplier_id": "SUP01", "supplier_name": "Norte"},
                                                       {"supplier_id": "SUP07", "supplier_name": "Costa"}]}
    assert s["calendar"][2]["holiday"] == "Feriado" and len(s["calendar"]) == 14
    b = client.get("/internal/v1/briefing", headers={"X-Glazed-Case": cid}).json()
    assert b["calendar"] == s["calendar"] and b["as_of_weekday_es"] == "martes"
    assert b["snapshot"]["calendar"] == s["calendar"]


def test_public_briefing_carries_calendar(env):
    client, _, m = env
    cid = mkcase(client, "2026-07-19")
    b = client.get(f"/api/v1/cases/{cid}/briefing").json()
    assert b["as_of_weekday_es"] == "domingo"
    assert {d["date"]: d["weekday_es"] for d in b["calendar"]}["2026-07-25"] == "sábado"
