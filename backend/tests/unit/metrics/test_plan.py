from datetime import date, timedelta

import pytest

from glazed_backend.metrics.plan import (apply_min_order, order_deadline, plan_line, projected_stockout,
                                         stockout_risk)
from glazed_backend.metrics.types import Config
from tests.unit.metrics.test_policy import ALL, T, flat_rows, state, sup


def test_projected_stockout_is_first_day_inventory_goes_negative():
    s = state(3, closing=20, rows=flat_rows(closing=20))
    assert projected_stockout(s, horizon=7) == date(2026, 3, 12)
    covered = state(3, closing=20, rows=flat_rows(closing=20), in_transit=[(date(2026, 3, 11), 40)])
    assert projected_stockout(covered, horizon=3) is None


def test_order_deadline_is_last_order_day_landing_before_the_stockout():
    s = state(3, closing=20, rows=flat_rows(closing=20), supplier=sup(lead=1.0, p90=2.0))
    assert order_deadline(s, date(2026, 3, 12)) == (date(2026, 3, 10), "ok")
    slow = state(3, closing=20, rows=flat_rows(closing=20), supplier=sup(lead=1.0, p90=3.0))
    assert order_deadline(slow, date(2026, 3, 12)) == (None, "deadline_passed")
    assert order_deadline(s, None) == (None, "no_stockout_projected")


def test_deadline_respects_supplier_delivery_days():
    thu = state(3, closing=20, rows=flat_rows(closing=20), supplier=sup(days={4}, lead=1.0, p90=1.0))
    # stockout Thu 12th: the order must be placed Wed 11th at the latest to land on Thursday... Tue + 1 -> Thu also fine
    day, why = order_deadline(thu, date(2026, 3, 12))
    assert why == "ok" and day == date(2026, 3, 11)


def test_stockout_risk_falls_with_stock_and_rises_with_late_suppliers():
    low = stockout_risk(state(3, closing=60, rows=flat_rows(closing=60)), with_qty=None)
    high = stockout_risk(state(3, closing=5, rows=flat_rows(closing=5)), with_qty=None)
    assert 0 <= low < 0.05 and high > 0.9
    ordered = stockout_risk(state(3, closing=5, rows=flat_rows(closing=5)), with_qty=40)
    assert ordered < high


def test_plan_line_contract_fields():
    s = state(3, closing=5, rows=flat_rows(closing=5), case=6)
    line = plan_line(s, Config(), typical_qty=30, window_received=300, window_sold=200)
    assert line["sku"] == "SKU" and line["method"] == "order_up_to"
    assert line["service_level_target"] == pytest.approx(0.75)  # (4-1)/4
    assert line["qty"] % 6 == 0 and line["cases"] == line["qty"] // 6 and line["qty"] > 0
    assert line["qty_range"]["low"] <= line["qty"] <= line["qty_range"]["high"]
    assert set(line["sensitivity"]) == {"0.60", "0.74", "0.85"}
    for k in ("expected_waste_usd", "expected_lost_sales_usd"):
        v = line[k]
        assert v["low"] <= v["mid"] <= v["high"]
    assert line["stockout_risk_without_order"] > line["stockout_risk_with_order"]
    assert line["vs_current_practice"] == {"received_to_sold": 1.5, "qty_delta": line["qty"] - 30}
    assert line["order_deadline"] == "2026-03-10" and line["projected_stockout_date"] == "2026-03-11"


def test_plan_line_is_none_when_nothing_must_be_ordered():
    s = state(3, closing=200, rows=flat_rows(closing=200, received=0))
    assert plan_line(s, Config(), None, 0, 0) is None


def test_min_order_value_is_a_warning_never_an_inflated_quantity():
    lines = [{"supplier_id": "SUP", "qty": 6, "est_cost_usd": 6.0}, {"supplier_id": "SUP", "qty": 12, "est_cost_usd": 12.0}]
    out = apply_min_order(lines, {"SUP": 150.0})
    assert [l["qty"] for l in out] == [6, 12]
    w = out[0]["min_order_warning"]
    assert w["min_order_value"] == 150.0 and w["order_value_usd"] == 18.0 and "consolidate" in w["suggestion"]
    ok = apply_min_order([{"supplier_id": "SUP", "qty": 1, "est_cost_usd": 200.0}], {"SUP": 150.0})
    assert ok[0]["min_order_warning"] is None


def test_plan_line_compares_with_doing_nothing_and_names_lead_time_and_delivery():
    s = state(3, closing=5, rows=flat_rows(closing=5), case=6, supplier=sup(lead=2.0, p90=3.0))
    line = plan_line(s, Config(), typical_qty=30, window_received=300, window_sold=200)
    dn = line["do_nothing"]
    assert set(dn) == {"net_usd_mid", "expected_lost_sales_usd", "expected_waste_usd"}
    assert dn["expected_lost_sales_usd"]["mid"] > line["expected_lost_sales_usd"]["mid"]  # not ordering loses more sales
    assert dn["net_usd_mid"] == pytest.approx(-(dn["expected_lost_sales_usd"]["mid"] + dn["expected_waste_usd"]["mid"]), abs=0.02)
    assert isinstance(line["net_usd_mid"], float)  # value of ordering, to put next to the do-nothing figure
    assert line["lead_time_days"] == 2 and line["next_delivery_date"] == line["expected_delivery"]
