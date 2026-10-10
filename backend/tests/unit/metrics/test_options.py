from datetime import date, timedelta

import pytest

from glazed_backend.metrics.detect import expiring_candidate, overstock_candidate, stockout_candidate
from glazed_backend.metrics.options import (eval_delta, expiring_options, make_option, overstock_options,
                                            stockout_options)
from glazed_backend.metrics.plan import recommended_qty
from glazed_backend.metrics.types import Config, DayRow
from tests.unit.metrics.test_policy import T, flat_rows, state

CFG = Config()
SIG = {"low", "mid", "high"}


def test_option_id_is_a_deterministic_hash_of_issue_action_and_sorted_params():
    a = make_option("S|k|1", "place_order", {"qty": 12, "sku": "A"}, {"benefit": {"low": 0, "mid": 1, "high": 2},
                    "cost_usd": 1, "net_mid": 0, "waste_delta": 0, "lost_delta": 0}, {}, [])
    b = make_option("S|k|1", "place_order", {"sku": "A", "qty": 12}, {"benefit": {"low": 0, "mid": 1, "high": 2},
                    "cost_usd": 1, "net_mid": 0, "waste_delta": 0, "lost_delta": 0}, {}, [])
    c = make_option("S|k|1", "place_order", {"sku": "A", "qty": 18}, a and {"benefit": {"low": 0, "mid": 1, "high": 2},
                    "cost_usd": 1, "net_mid": 0, "waste_delta": 0, "lost_delta": 0}, {}, [])
    assert a["option_id"] == b["option_id"] != c["option_id"] and len(a["option_id"]) == 12


def test_eval_delta_values_extra_units_against_the_baseline():
    s = state(3, closing=0, rows=flat_rows(closing=0))
    rec, qplan = recommended_qty(s, 0.75)
    ev = eval_delta(rec, qplan, 0, price=4.0, unit_cost=1.0, perishable=True)
    assert ev["net_mid"] > 0 and ev["cost_usd"] == pytest.approx(qplan * 1.0)
    assert SIG == set(ev["benefit"]) and ev["benefit"]["low"] <= ev["benefit"]["high"]
    assert ev["lost_delta"] < 0  # ordering reduces lost sales
    huge = eval_delta(rec, qplan * 4, 0, 4.0, 1.0, True)
    assert huge["net_mid"] < ev["net_mid"] and huge["waste_delta"] > ev["waste_delta"]


def test_stockout_detector_and_options_include_do_nothing_with_its_cost():
    s = state(3, closing=4, rows=flat_rows(closing=4), case=6)
    line = stockout_candidate(s, CFG)
    assert line and line["stockout_risk_without_order"] >= 0.3
    opts = stockout_options("S|stockout_risk|SKU", s, CFG, line)
    kinds = [o["action_type"] for o in opts]
    assert kinds[0] == "place_order" and kinds[-1] == "do_nothing" and len(opts) <= 5
    assert set(kinds) <= {"place_order", "adjust_order_qty", "do_nothing"}
    dn = opts[-1]
    assert dn["cost_usd"] > 0 and dn["net_usd_mid"] == 0 and dn["loss_impact"]["lost_sales_usd_delta"] > 0
    po = opts[0]
    assert po["urgency"]["reason"] and "deadline_date" in po["urgency"] and po["params"]["qty"] % 6 == 0
    assert po["net_usd_mid"] > 0 and po["if_act"] is None and po["if_not"] is None
    assert len({o["option_id"] for o in opts}) == len(opts)


def test_no_stockout_candidate_when_stock_is_plentiful():
    assert stockout_candidate(state(3, closing=300, rows=flat_rows(closing=300)), CFG) is None


def test_overstock_detector_needs_waste_and_over_receiving():
    waste_rows = flat_rows(sold=4, received=14, closing=0, expired=10)
    s = state(1, rows=waste_rows)
    assert overstock_candidate(s, CFG) is not None
    assert overstock_candidate(state(1, rows=flat_rows(sold=10, received=10, expired=0)), CFG) is None


def test_overstock_options_cut_the_order_versus_current_practice():
    s = state(1, rows=flat_rows(sold=4, received=14, closing=0, expired=10))
    opts = overstock_options("S|overstock_waste|SKU", s, CFG, typical_qty=14.0)
    acts = [o["action_type"] for o in opts]
    assert "adjust_order_qty" in acts and acts[-1] == "do_nothing"
    adj = next(o for o in opts if o["action_type"] == "adjust_order_qty")
    assert adj["params"]["qty"] < 14 and adj["net_usd_mid"] > 0 and adj["loss_impact"]["waste_usd_delta"] < 0
    assert opts[-1]["cost_usd"] > 0  # waste if nothing changes


def test_expiring_markdown_carries_the_elasticity_caveat_and_n2_cap():
    rows = tuple(DayRow(T - timedelta(days=55 - i), 4, 4, 0, 0) for i in range(55)) + (DayRow(T, 20, 3, 0, 17),)
    s = state(2, rows=rows)
    assert expiring_candidate(s) is not None
    opts = expiring_options("S|expiring|SKU", s, CFG, typical_qty=6.0)
    md = next(o for o in opts if o["action_type"] == "markdown_end_of_day")
    assert md["data_caveat"] == "assumed elasticity" and md["tier_cap"] == "N2"
    assert md["net_usd_mid"] > 0 and md["loss_impact"]["waste_usd_delta"] < 0
