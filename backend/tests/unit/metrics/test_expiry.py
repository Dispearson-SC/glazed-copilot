from datetime import date, timedelta

import pytest

from glazed_backend.metrics.expiry import Lot, expiring_items, infer_lots, summarize_expiry
from glazed_backend.metrics.types import DayRow

AS_OF = date(2026, 7, 19)
Z = 0.84 * (0.5 * 10 ** 0.5)  # sd floor of a flat history selling 10 a day
PRODUCT = {"product_name": "Sandwich", "unit_cost": 2.0, "shelf_life_days": 2}


def history(received_by_offset, closing_last, sold=10, days=60):
    """Flat sales of `sold` a day; receipts at AS_OF + offset; the last closing stock is `closing_last`."""
    out = []
    for i in range(days):
        d = AS_OF - timedelta(days=days - 1 - i)
        off = (d - AS_OF).days
        out.append(DayRow(d, received_by_offset.get(off, 0), sold, 0, closing_last if d == AS_OF else 50, 0.0))
    return out


def test_infer_lots_assigns_the_closing_stock_to_the_newest_receipts():
    receipts = [(AS_OF - timedelta(days=1), 20), (AS_OF, 20)]
    lots = infer_lots(30, receipts, 2, AS_OF)
    assert lots == [Lot(AS_OF - timedelta(days=1), 10.0, AS_OF), Lot(AS_OF, 20.0, AS_OF + timedelta(days=1))]


def test_infer_lots_unknown_age_leftover_is_assumed_received_yesterday():
    lots = infer_lots(25, [(AS_OF, 10)], 3, AS_OF)
    assert sum(l.qty for l in lots) == 25 and min(l.received for l in lots) == AS_OF - timedelta(days=1)


def test_expiring_items_fifo_ranges_and_dates():
    rows = history({-1: 20, 0: 20}, closing_last=30)
    items = expiring_items("SKU1", PRODUCT, rows, AS_OF, days=7, open_hours=12.0)
    assert [i["expiry_date"] for i in items] == ["2026-07-20", "2026-07-21"]
    first, second = items
    assert first["expiring_units"] == pytest.approx(10) and first["waste_units"]["mid"] == pytest.approx(10)
    assert second["expiring_units"] == pytest.approx(20)
    assert second["waste_units"]["low"] == pytest.approx(20 - (10 + Z), abs=0.01)  # more demand, less waste
    assert second["waste_units"]["mid"] == pytest.approx(10)
    assert second["waste_units"]["high"] == pytest.approx(20 - (10 - Z), abs=0.01)
    assert first["waste_usd"]["mid"] == pytest.approx(20.0)  # 10 units x cost 2
    assert first["lot_age_inferred"] is True and first["shelf_life_days"] == 2 and first["sku"] == "SKU1"
    assert first["product_name"] == "Sandwich" and first["projected"] is True


def test_window_and_ineligible_skus():
    rows = history({-1: 20, 0: 20}, closing_last=30)
    assert [i["expiry_date"] for i in expiring_items("S", PRODUCT, rows, AS_OF, 1, 12.0)] == ["2026-07-20"]
    assert expiring_items("S", {**PRODUCT, "shelf_life_days": None}, rows, AS_OF, 7, 12.0) == []
    assert expiring_items("S", {**PRODUCT, "shelf_life_days": 365}, rows, AS_OF, 7, 12.0) == []
    assert expiring_items("S", PRODUCT, history({}, closing_last=0), AS_OF, 7, 12.0) == []


def test_rows_after_as_of_are_ignored():
    rows = history({-1: 20, 0: 20}, closing_last=30)
    rows += [DayRow(AS_OF + timedelta(days=1), 500, 0, 0, 999, 0.0)]
    same = expiring_items("S", PRODUCT, history({-1: 20, 0: 20}, closing_last=30), AS_OF, 7, 12.0)
    assert expiring_items("S", PRODUCT, rows, AS_OF, 7, 12.0) == same


def test_summary_by_day_and_total():
    rows = history({-1: 20, 0: 20}, closing_last=30)
    items = expiring_items("S", PRODUCT, rows, AS_OF, 7, 12.0) + expiring_items("T", PRODUCT, rows, AS_OF, 7, 12.0)
    by_day, total = summarize_expiry(items)
    assert [d["date"] for d in by_day] == ["2026-07-20", "2026-07-21"]
    assert by_day[0]["waste_usd"]["mid"] == pytest.approx(40.0)
    assert total["mid"] == pytest.approx(sum(i["waste_usd"]["mid"] for i in items))
    assert total["low"] <= total["mid"] <= total["high"]
