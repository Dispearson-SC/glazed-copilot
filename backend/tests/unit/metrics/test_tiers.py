from glazed_backend.metrics.tiers import classify
from glazed_backend.metrics.types import Config

CFG = Config()


def opt(action="place_order", net=40.0, cost=30.0, score=0.9, n=40, qty=12, **params):
    return {"action_type": action, "net_usd_mid": net, "cost_usd": cost,
            "confidence": {"score": score, "n_backtest": n}, "params": {"qty": qty, **params}}


def test_n1_needs_every_condition():
    tier, why = classify(opt(), runner_up_net=10.0, cfg=CFG, plan_qty=12, case_size=6)
    assert tier == "N1" and any("calibrated" in w for w in why)


def test_each_failed_n1_condition_drops_to_n2_with_a_reason():
    cases = {
        "score": opt(score=0.84), "n": opt(n=29), "cost": opt(cost=151.0),
        "adjust": opt(qty=30),  # far outside the band
    }
    for name, o in cases.items():
        tier, why = classify(o, 10.0, CFG, plan_qty=12, case_size=6)
        assert tier == "N2", name
        assert why, name


def test_adjustment_band_is_15_percent_with_a_minimum_of_one_case():
    assert classify(opt(qty=18), 0.0, CFG, plan_qty=12, case_size=6)[0] == "N1"  # +1 case on 12 is allowed (min 1 case)
    assert classify(opt(qty=24), 0.0, CFG, plan_qty=12, case_size=6)[0] == "N2"
    assert classify(opt("adjust_order_qty", qty=100), 0.0, CFG, plan_qty=100, case_size=1)[0] == "N1"
    assert classify(opt("adjust_order_qty", qty=120), 0.0, CFG, plan_qty=100, case_size=1)[0] == "N2"  # +20% > 15%


def test_n0_when_net_is_not_positive_or_below_the_noise_floor():
    assert classify(opt(net=-3.0), None, CFG, 12, 6)[0] == "N0"
    assert classify(opt(net=0.5), None, CFG, 12, 6)[0] == "N0"
    assert classify({"action_type": "do_nothing", "net_usd_mid": 0.0, "cost_usd": 20.0,
                     "confidence": {"score": 1, "n_backtest": 0}, "params": {}}, 5.0, CFG, None, 1)[0] == "N0"


def test_n3_for_transfers_staffing_large_promos_and_close_options():
    assert classify(opt("transfer_stock", score=0.95), 0.0, CFG, None, 1)[0] == "N3"
    assert classify(opt("shift_staff_hours"), 0.0, CFG, None, 1)[0] == "N3"
    assert classify(opt("run_promo", discount_pct=30, cost=10), 0.0, CFG, None, 1)[0] == "N3"
    tier, why = classify(opt(net=40.0), runner_up_net=38.0, cfg=CFG, plan_qty=12, case_size=6)  # |dnet| < 10%
    assert tier == "N3" and any("close" in w for w in why)


def test_markdown_end_of_day_never_exceeds_n2():
    tier, why = classify(opt("markdown_end_of_day", score=0.99, n=99, cost=0.0), 0.0, CFG, None, 1)
    assert tier == "N2" and any("elasticity" in w for w in why)


def test_a_higher_store_threshold_allows_n1():
    cfg = Config(store_threshold_usd=500.0)
    assert classify(opt(cost=300.0), 0.0, cfg, 12, 6)[0] == "N1"
