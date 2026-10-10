from glazed_backend.metrics.detect import inflated_order_candidate
from glazed_backend.metrics.issues import finalize_options
from glazed_backend.metrics.options import inflated_order_options
from glazed_backend.metrics.types import Config
from tests.unit.metrics.test_policy import flat_rows, state

CFG = Config()
KIOSK = dict(sold=4, received=14, closing=0, expired=10)  # 71% of what arrives is thrown away


def test_flags_a_full_case_far_above_the_optimum_when_waste_is_high():
    s = state(1, rows=flat_rows(**KIOSK), case=12)
    cand = inflated_order_candidate(s, CFG, typical_qty=12.0)
    assert cand and cand["ordered_qty"] == 12 and cand["optimum_qty"] < 6 and cand["case_size"] == 12
    assert cand["excess_units"] >= 6 and cand["waste_rate"] > 0.25


def test_needs_both_excess_of_half_a_case_and_waste_over_25_percent():
    low_waste = state(1, rows=flat_rows(sold=10, received=11, closing=0, expired=1), case=12)
    assert inflated_order_candidate(low_waste, CFG, typical_qty=12.0) is None
    small_gap = state(1, rows=flat_rows(**KIOSK), case=2)  # a 2-unit case: the excess is within half a case? no, but check typical
    assert inflated_order_candidate(small_gap, CFG, typical_qty=4.0) is None


def test_options_cut_to_the_optimum_offer_alternate_days_and_cost_of_doing_nothing():
    s = state(2, rows=flat_rows(**KIOSK), case=12)
    cand = inflated_order_candidate(s, CFG, typical_qty=12.0)
    opts = inflated_order_options("S030|inflated_order|SKU", s, CFG, cand)
    acts = [o["action_type"] for o in opts]
    assert acts[-1] == "do_nothing" and acts.count("adjust_order_qty") == 2 and len(opts) <= 4
    adj = next(o for o in opts if o["action_type"] == "adjust_order_qty" and "pattern" not in o["params"])
    alt = next(o for o in opts if o["params"].get("pattern") == "alternate_days")
    assert adj["params"]["qty"] == round(cand["optimum_qty"]) and adj["loss_impact"]["waste_usd_delta"] < 0
    assert alt["params"]["cycle_days"] == 2 and alt["net_usd_mid"] > 0
    dn = opts[-1]
    assert dn["cost_usd"] > 0 and dn["loss_impact"]["waste_usd_delta"] > 0  # cost = expected waste
    finalize_options(opts, "inflated_order", {}, CFG)
    assert all(o["tier"] in ("N0", "N1", "N2", "N3") for o in opts)


def test_alternate_days_is_not_offered_for_one_day_shelf_life():
    s = state(1, rows=flat_rows(**KIOSK), case=12)
    opts = inflated_order_options("S|inflated_order|X", s, CFG, inflated_order_candidate(s, CFG, typical_qty=12.0))
    assert not any(o["params"].get("pattern") == "alternate_days" for o in opts)


def test_when_the_optimum_is_to_order_nothing_the_cut_is_a_skip_order():
    s = state(2, closing=200, rows=flat_rows(sold=4, received=14, closing=200, expired=10), case=12)
    cand = inflated_order_candidate(s, CFG, typical_qty=12.0)
    opts = inflated_order_options("S|inflated_order|X", s, CFG, cand)
    assert opts[0]["action_type"] == "skip_order" and opts[-1]["action_type"] == "do_nothing"
