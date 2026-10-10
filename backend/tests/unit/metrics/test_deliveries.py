from datetime import date, timedelta

from glazed_backend.metrics.deliveries import LATE_LOOKBACK_DAYS, build_delivery_days

AS_OF = date(2026, 7, 19)  # Sunday


def po(po_id, expected, sup="SUP01", received=None, sku="A", qty=10, cost=2.0, name="Alpha"):
    return {"po_id": po_id, "supplier_id": sup, "supplier_name": f"Name {sup}", "sku": sku, "product_name": name, "qty": qty,
            "unit_cost": cost, "order_date": AS_OF - timedelta(days=3), "expected_date": expected, "received_date": received}


def day(days, d):
    return next(x for x in days if x["date"] == d.isoformat())


def test_window_lists_every_future_day_and_the_as_of_day_only_when_it_has_deliveries():
    out = build_delivery_days([], [], AS_OF, 3)
    assert [d["date"] for d in out] == ["2026-07-20", "2026-07-21", "2026-07-22"]
    assert all(d["deliveries"] == [] and d["projected"] is True for d in out)


def test_open_po_is_expected_with_lines_and_value():
    rows = [po("PO1", AS_OF + timedelta(days=2)), po("PO1", AS_OF + timedelta(days=2), sku="B", qty=5, cost=4.0, name="Bravo")]
    (dl,) = day(build_delivery_days(rows, [], AS_OF, 7), AS_OF + timedelta(days=2))["deliveries"]
    assert dl["kind"] == "open_po" and dl["po_id"] == "PO1" and dl["status"] == "expected" and dl["supplier_name"] == "Name SUP01"
    assert dl["lines"] == [{"sku": "A", "product_name": "Alpha", "qty": 10}, {"sku": "B", "product_name": "Bravo", "qty": 5}]
    assert dl["value_usd"] == 40.0 and dl["projected"] is True


def test_overdue_po_is_late_on_the_as_of_day_and_stale_ones_are_dropped():
    rows = [po("LATE", AS_OF - timedelta(days=2)), po("STALE", AS_OF - timedelta(days=LATE_LOOKBACK_DAYS + 1))]
    out = build_delivery_days(rows, [], AS_OF, 2)
    (dl,) = day(out, AS_OF)["deliveries"]
    assert dl["po_id"] == "LATE" and dl["status"] == "late" and dl["expected_date"] == (AS_OF - timedelta(days=2)).isoformat()
    assert "projected" not in day(out, AS_OF) or day(out, AS_OF)["projected"] is False


def test_received_on_as_of_is_on_time_or_late_and_receipts_after_as_of_are_unknown():
    rows = [po("OK", AS_OF, received=AS_OF), po("LAT", AS_OF - timedelta(days=1), received=AS_OF),
            po("FUT", AS_OF + timedelta(days=1), received=AS_OF + timedelta(days=1))]  # a receipt we cannot know yet
    out = build_delivery_days(rows, [], AS_OF, 3)
    by = {d["po_id"]: d for d in day(out, AS_OF)["deliveries"]}
    assert by["OK"]["status"] == "on_time" and by["LAT"]["status"] == "late"
    (fut,) = day(out, AS_OF + timedelta(days=1))["deliveries"]
    assert fut["po_id"] == "FUT" and fut["status"] == "expected"


def test_scheduled_slots_follow_supplier_weekdays_and_yield_to_an_open_po():
    sup = [{"supplier_id": "SUP07", "supplier_name": "Tue Fri Co", "delivery_days": [2, 5]},
           {"supplier_id": "SUP01", "supplier_name": "Daily Co", "delivery_days": [1, 2, 3, 4, 5, 6, 7]}]
    out = build_delivery_days([po("PO7", date(2026, 7, 21), sup="SUP07")], sup, AS_OF, 7)
    kinds = {d["date"]: sorted((x["kind"], x["supplier_id"]) for x in d["deliveries"]) for d in out}
    assert kinds["2026-07-21"] == [("open_po", "SUP07"), ("scheduled", "SUP01")]  # Tue: PO replaces SUP07's slot
    assert kinds["2026-07-24"] == [("scheduled", "SUP01"), ("scheduled", "SUP07")]  # Fri
    assert kinds["2026-07-20"] == [("scheduled", "SUP01")]  # Mon
    sched = day(out, date(2026, 7, 24))["deliveries"][0]
    assert sched["po_id"] is None and sched["lines"] == [] and sched["value_usd"] == 0.0 and sched["status"] == "expected"
    assert sched["value_known"] is False and sched["projected"] is True


def test_po_beyond_the_window_is_left_out():
    out = build_delivery_days([po("FAR", AS_OF + timedelta(days=9))], [], AS_OF, 7)
    assert all(d["deliveries"] == [] for d in out)
