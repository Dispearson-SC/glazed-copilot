from datetime import date

import pytest

from glazed_backend.metrics.calendar_effect import MIN_CELL_DAYS, calendar_issue, event_effect
from glazed_backend.metrics.types import Config


def test_a_cell_with_enough_days_uses_its_own_effect():
    r = event_effect([12.0] * 25, [10.0] * 60, [11.0] * 500, [10.0] * 900)
    assert r["effect_pct"] == pytest.approx(20.0) and r["n"] == 25 and not r["shrunk"] and r["data_caveat"] is None
    assert MIN_CELL_DAYS == 20


def test_a_thin_cell_is_pulled_toward_the_format_department_average_and_says_so():
    r = event_effect([15.0] * 5, [10.0] * 60, [11.0] * 500, [10.0] * 900)  # cell +50%, group +10%
    assert r["cell_pct"] == pytest.approx(50.0) and r["group_pct"] == pytest.approx(10.0)
    assert 10.0 < r["effect_pct"] < 50.0 and r["shrunk"] and r["weight"] == pytest.approx(5 / 20)
    assert "5 days" in r["data_caveat"] and "format" in r["data_caveat"]


def test_no_event_days_in_the_cell_falls_back_to_the_group():
    r = event_effect([], [10.0] * 60, [13.0] * 300, [10.0] * 900)
    assert r["effect_pct"] == pytest.approx(30.0) and r["n"] == 0 and r["weight"] == 0.0


def test_no_baseline_means_no_effect():
    assert event_effect([5.0] * 30, [], [], []) is None


def test_calendar_issue_recommends_a_per_department_adjustment_with_do_nothing_cost():
    deps = [{"department": "Food", "effect": {"effect_pct": 22.0, "n": 30, "shrunk": False, "data_caveat": None},
             "units_per_day": 40.0, "avg_price": 4.0, "avg_cost": 1.5},
            {"department": "Bakery", "effect": {"effect_pct": 2.0, "n": 30, "shrunk": False, "data_caveat": None},
             "units_per_day": 30.0, "avg_price": 3.0, "avg_cost": 1.0}]
    ev = {"type": "school_break", "name": "School break", "days": [date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3)]}
    iss = calendar_issue("S030", date(2026, 5, 29), date(2026, 5, 29), ev, deps, Config())
    assert iss["kind"] == "calendar_uplift" and iss["issue_id"] == "S030|calendar_uplift|school_break-2026-06-01"
    adj, dn = iss["options"]
    assert adj["action_type"] == "adjust_order_qty" and dn["action_type"] == "do_nothing"
    effects = adj["params"]["effects"]
    assert [e["department"] for e in effects] == ["Food"]  # Bakery +2% is under the 5% materiality bar
    assert effects[0]["effect_pct"] == 22.0 and adj["params"]["window"] == ["2026-06-01", "2026-06-03"]
    assert adj["net_usd_mid"] > 0 and dn["cost_usd"] > 0 and iss["recommended_option_id"] == adj["option_id"]
    assert adj["tier"] in ("N1", "N2") and iss["severity_usd"] > 0


def test_no_material_effect_means_no_issue():
    deps = [{"department": "Food", "effect": {"effect_pct": 1.0, "n": 30, "shrunk": False, "data_caveat": None},
             "units_per_day": 40.0, "avg_price": 4.0, "avg_cost": 1.5}]
    ev = {"type": "holiday", "name": "Easter", "days": [date(2026, 4, 5)]}
    assert calendar_issue("S030", date(2026, 4, 1), date(2026, 4, 1), ev, deps, Config()) is None
