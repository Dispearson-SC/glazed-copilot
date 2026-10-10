"""Waste-aware order policy and data-driven promotion lift. The default (margin) policy must not move."""
import dataclasses
from datetime import date, timedelta

import pytest

from glazed_backend.metrics.analysis import label
from glazed_backend.metrics.backtest import backtest_sku
from glazed_backend.metrics.detect import expiring_candidate
from glazed_backend.metrics.options import eval_delta, expiring_options, overstock_options, stockout_options
from glazed_backend.metrics.plan import recommended_qty, service_for
from glazed_backend.metrics.promo_lift import (PromoLiftTable, PromoObs, did_uplift_pct, markdown_recovery,
                                               promo_effect)
from glazed_backend.metrics.service_level import critical_ratio, service_target
from glazed_backend.metrics.tiers import classify
from glazed_backend.metrics.types import Config, DayRow, Product, config_from_env
from tests.unit.metrics.test_policy import T, flat_rows, state

WA = Config(order_policy="waste_aware", waste_penalty=1.0)


# ---- config ---------------------------------------------------------------------------------------------------
def test_default_config_is_the_margin_policy_and_env_flags_are_opt_in():
    c = Config()
    assert c.order_policy == "margin" and c.waste_penalty == 0.0 and c.perishable_service_cap is None and not c.waste_aware
    assert config_from_env({}) == c
    assert config_from_env({"GLAZED_ORDER_POLICY": "bogus", "GLAZED_WASTE_PENALTY": "x"}) == c
    w = config_from_env({"GLAZED_ORDER_POLICY": "waste_aware", "GLAZED_WASTE_PENALTY": "1.5", "GLAZED_SERVICE_CAP": "0.8"})
    assert w.waste_aware and w.waste_penalty == 1.5 and w.perishable_service_cap == 0.8


def test_margin_policy_ignores_waste_knobs_and_recommendations_are_unchanged():
    s = state(1, closing=0, rows=flat_rows(closing=0), case=6)
    base = recommended_qty(s, service_for(s, Config()), Config())
    knobs = Config(order_policy="margin", waste_penalty=3.0, perishable_service_cap=0.5)
    assert recommended_qty(s, service_for(s, knobs), knobs)[1] == base[1]
    assert service_for(s, Config()) == critical_ratio(4.0, 1.0) == 0.75
    # values pinned from the pre-change implementation
    assert base[1] == 12
    assert recommended_qty(state(150, closing=5, rows=flat_rows(closing=5), case=6), 0.95)[1] == 24
    a = stockout_options("S|k|1", state(3, closing=4, rows=flat_rows(closing=4), case=6), Config(), _line())
    b = stockout_options("S|k|1", state(3, closing=4, rows=flat_rows(closing=4), case=6), knobs, _line())
    assert [o["option_id"] for o in a] == [o["option_id"] for o in b]
    assert all("shadow_waste_penalty_usd" not in o for o in a)


def _line():
    return {"order_deadline": None, "order_deadline_status": "x", "projected_stockout_date": "2026-03-12",
            "expected_delivery": "2026-03-11"}


# ---- penalty lowers the order ---------------------------------------------------------------------------------
def test_waste_penalty_lowers_the_service_level_and_the_quantity_of_perishables():
    s = state(1, closing=0, rows=flat_rows(closing=0))
    cr0, cr1 = service_for(s, Config()), service_for(s, WA)
    assert cr1 < cr0 == pytest.approx(0.75) and cr1 == pytest.approx(critical_ratio(4.0, 1.0, waste_penalty=1.0))
    q0 = recommended_qty(s, cr0, Config())[1]
    q1 = recommended_qty(s, cr1, WA)[1]
    q3 = recommended_qty(s, service_for(s, dataclasses.replace(WA, waste_penalty=3.0)), dataclasses.replace(WA, waste_penalty=3.0))[1]
    assert q0 > q1 >= q3


def test_cap_bounds_perishables_only_and_shelf_stable_stock_keeps_its_floor():
    capped = Config(order_policy="waste_aware", waste_penalty=0.0, perishable_service_cap=0.6)
    assert service_target(10.0, 1.0, True, capped) == 0.6          # CR 0.9 capped
    assert service_target(10.0, 1.0, False, capped) == pytest.approx(max(0.9, capped.non_perishable_service))
    assert service_target(10.0, 1.0, False, WA) == service_target(10.0, 1.0, False, Config())


def test_waste_penalty_is_a_shadow_cost_in_the_option_net_and_reduction_options_gain_from_it():
    s = state(3, closing=0, rows=flat_rows(closing=0))
    rec, q = recommended_qty(s, 0.75, Config())
    plain = eval_delta(rec, q * 2, q, 4.0, 1.0, True)
    pen = eval_delta(rec, q * 2, q, 4.0, 1.0, True, WA)
    assert pen["net_mid"] < plain["net_mid"] and pen["shadow_usd"] > 0 and plain["waste_delta"] == pen["waste_delta"]
    cut = eval_delta(rec, q // 2, q, 4.0, 1.0, True, WA)
    assert cut["shadow_usd"] < 0 and cut["net_mid"] > eval_delta(rec, q // 2, q, 4.0, 1.0, True)["net_mid"]
    opts = stockout_options("S|k|1", state(3, closing=4, rows=flat_rows(closing=4), case=6), WA, _line())
    assert any("shadow_waste_penalty_usd" in o for o in opts if o["action_type"] != "do_nothing")


def test_backtest_uses_the_same_service_target():
    prod = Product("A", "Item", "SUP", 4.0, 1.0, 1, 1)
    hist = [DayRow(T - timedelta(days=30 - i), 10, 8 + i % 3, 0, 0, 0.0) for i in range(30)]
    out = DayRow(T + timedelta(days=1), 12, 8, 4, 0, 0.0)
    cur = backtest_sku(hist, out, prod, 12.0, Config())["policy"]["waste_usd"]
    low = backtest_sku(hist, out, prod, 12.0, dataclasses.replace(WA, waste_penalty=3.0))["policy"]["waste_usd"]
    assert low <= cur


# ---- promo lift estimator -------------------------------------------------------------------------------------
def obs(pid, dep, cat, disc, up, end=date(2026, 3, 1)):
    return PromoObs(pid, dep, cat, disc, end - timedelta(days=13), end, up, 14, 56)


FIX = [obs("P1", "Bakery", "Bakery", 15, -11), obs("P2", "Bakery", None, 15, 1), obs("P3", "Bakery", "Bakery", 25, 35),
       obs("P4", "Beverage", "Coffee & Tea", 10, 11), obs("P5", "Food", "Sandwiches", 12, 25),
       PromoObs("PX", "Bakery", None, 15, date(2026, 4, 1), date(2026, 4, 30), 14.0, 20, 50, placebo=True)]


def test_did_uplift_compares_the_scope_to_the_control_against_its_own_baseline():
    assert did_uplift_pct(120, 100, 100, 100) == pytest.approx(20.0)
    assert did_uplift_pct(120, 200, 100, 200) == pytest.approx(20.0)  # control volume cancels
    assert did_uplift_pct(100, 100, 0, 100) is None and did_uplift_pct(1, 0, 1, 1) is None


def test_lift_estimate_is_proportional_to_depth_shrunk_and_honest_about_uncertainty():
    t = PromoLiftTable(FIX, date(2026, 6, 1))
    assert len(t.obs) == 5  # the never-run placebo is not an observation
    est = t.estimate("Bakery", "Bakery", 30.0)
    assert est and est.n_promos == 3 and est.promo_ids == ("P1", "P2", "P3")
    assert est.lift_low_pct < est.lift_pct < est.lift_high_pct and est.se_pct > 0
    assert est.extrapolated is False and t.estimate("Bakery", "Bakery", 40.0).extrapolated  # deepest observed: 25%
    assert t.estimate("Bakery", "Bakery", 25.0).extrapolated is False
    assert t.estimate("Food", "Sandwiches", 30.0).confidence == "low"  # one promo only
    assert t.estimate("Merchandise", None, 30.0) is None               # no history in the scope
    assert t.estimate("Bakery", "Bakery", 0.0) is None
    # a promo that ends after as_of is not known yet
    assert PromoLiftTable(FIX, date(2026, 2, 1)).estimate("Bakery", "Bakery", 15.0) is None


def test_markdown_recovery_follows_the_lift_and_is_capped_at_the_units_at_risk():
    est = PromoLiftTable(FIX, date(2026, 6, 1)).estimate("Bakery", "Bakery", 30.0)
    lo, mid, hi = markdown_recovery(est, daily_demand=10.0, units=20.0)
    assert 0 <= lo <= mid <= hi <= 1 and mid == pytest.approx(10.0 * est.lift_pct / 100 / 20.0)
    assert markdown_recovery(est, 10.0, 0.0) == (0.0, 0.0, 0.0)
    assert markdown_recovery(est, 1000.0, 5.0)[1] == 1.0


def test_promo_effect_counts_cannibalisation():
    est = PromoLiftTable(FIX, date(2026, 6, 1)).estimate("Bakery", "Bakery", 30.0)
    eff = promo_effect(est, daily_demand=10.0, days=2, units_at_risk=50.0, price=4.0, unit_cost=1.0, discount=0.3)
    cleared = 10.0 * 2 * est.lift_pct / 100
    assert eff["cleared_units"] == pytest.approx(cleared)
    assert eff["mid"] == pytest.approx(cleared * 4.0 * 0.7 - 10.0 * 2 * 4.0 * 0.3)
    assert eff["waste_avoided_usd"] == pytest.approx(cleared * 1.0) and eff["low"] <= eff["mid"] <= eff["high"]


# ---- options --------------------------------------------------------------------------------------------------
def _expiring_state(dep="Bakery", cat="Bakery", shelf=3):
    rows = flat_rows(sold=10, received=10, closing=45)
    prod = Product("SKU", "Item", "SUP", 4.0, 1.0, 1, shelf, dep, cat)
    return dataclasses.replace(state(shelf, closing=45, rows=rows), product=prod)


def test_without_lift_the_expiring_options_are_the_historic_ones():
    s = _expiring_state()
    assert expiring_candidate(s)
    base = expiring_options("S|expiring|SKU", s, Config(), None)
    assert [o["action_type"] for o in base] == ["markdown_end_of_day", "skip_order", "do_nothing"]
    assert "recovery_pct" not in base[0]["params"] and base[0]["data_caveat"] == "assumed elasticity"
    no_table = expiring_options("S|expiring|SKU", s, WA, None)  # waste_aware but no history table: assumptions stay
    assert [o["option_id"] for o in no_table] == [o["option_id"] for o in base]


def test_waste_aware_markdown_uses_the_estimated_lift_and_offers_activate_promo():
    s = _expiring_state()
    cfg = dataclasses.replace(WA, promo_lift=PromoLiftTable(FIX, date(2026, 6, 1)))
    opts = {o["action_type"]: o for o in expiring_options("S|expiring|SKU", s, cfg, None)}
    assert set(opts) == {"markdown_end_of_day", "skip_order", "activate_promo", "do_nothing"}
    md, promo = opts["markdown_end_of_day"], opts["activate_promo"]
    assert md["params"]["recovery_source"] == "promo_lift" and md["data_caveat"] == "promo lift estimated from history"
    assert md["expected_benefit_usd"]["low"] <= md["expected_benefit_usd"]["mid"] <= md["expected_benefit_usd"]["high"]
    p = promo["params"]
    assert p["sku"] == "SKU" and p["discount_pct"] == 30 and 1 <= p["days"] <= 2   # within a 3-day shelf life
    assert p["lift_confidence"] in ("low", "medium") and p["promo_ids"] == ["P1", "P2", "P3"]
    assert p["expected_units_cleared"] <= p["units_at_risk"]
    assert promo["loss_impact"]["waste_usd_delta"] <= 0 and promo["cost_usd"] > 0 and promo["tier_cap"] == "N2"
    assert promo["risk"] and promo["net_usd_mid"] == pytest.approx(
        promo["expected_benefit_usd"]["mid"] - promo["cost_usd"], abs=0.02)
    assert len({o["option_id"] for o in opts.values()}) == 4


def test_activate_promo_needs_a_shelf_life_of_two_days_and_history_for_the_scope():
    cfg = dataclasses.replace(WA, promo_lift=PromoLiftTable(FIX, date(2026, 6, 1)))
    one_day = [o["action_type"] for o in expiring_options("i", _expiring_state(shelf=1), cfg, None)]
    assert "activate_promo" not in one_day
    other = [o["action_type"] for o in expiring_options("i", _expiring_state("Merchandise", None), cfg, None)]
    assert "activate_promo" not in other
    over = [o["action_type"] for o in overstock_options("i", _expiring_state(), cfg, 30.0)]
    assert over[-1] == "do_nothing"


def test_activate_promo_always_needs_approval_and_has_a_spanish_label():
    o = {"action_type": "activate_promo", "net_usd_mid": 25.0, "cost_usd": 5.0, "params": {"discount_pct": 30, "days": 2}}
    assert classify(o, None, Config())[0] == "N2"
    assert classify({**o, "net_usd_mid": -1.0}, None, Config())[0] == "N0"
    assert label(o, {"product_name": "Dona"}) == "Activar promoción de 30% en Dona por 2 días"
