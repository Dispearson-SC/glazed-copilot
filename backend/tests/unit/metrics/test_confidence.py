from datetime import date, timedelta

import pytest

from glazed_backend.metrics.confidence import (Calibration, confidence_for, realized_add_net,
                                               realized_reduce_net, score_replays)
from glazed_backend.metrics.types import Config, DayRow

D0 = date(2026, 3, 1)


def rows(sold, expired=0, closing=0, so=0.0, n=3):
    return [DayRow(D0 + timedelta(days=i), 10, sold, expired, closing, so) for i in range(n)]


def test_adding_stock_earns_margin_on_unmet_demand_and_wastes_the_rest():
    # unmet demand of 6 units (estimated demand 10 vs sold 4 per day over 3 days, lost = 18); order 10 units, perishable
    win = rows(sold=4, n=3)
    demand = {r.date: 10.0 for r in win}
    net = realized_add_net(win, demand, qty=10, price=5.0, unit_cost=2.0, perishable=True)
    assert net == pytest.approx(5.0 * 10 - 2.0 * 10)  # all 10 units sell: +50 revenue, -20 cost
    over = realized_add_net(win, {r.date: 4.0 for r in win}, qty=10, price=5.0, unit_cost=2.0, perishable=True)
    assert over == pytest.approx(-20.0)  # no unmet demand: the whole order is waste
    keep = realized_add_net(win, {r.date: 4.0 for r in win}, qty=10, price=5.0, unit_cost=2.0, perishable=False)
    assert keep == pytest.approx(0.0)  # non-perishable leftover stays as inventory at cost


def test_removing_stock_saves_cost_but_loses_sales_that_would_have_happened():
    wasted = rows(sold=2, expired=5, closing=0)  # 15 units expired in the window
    assert realized_reduce_net(wasted, delta=10, price=5.0, unit_cost=2.0) == pytest.approx(20.0)  # cost saved, no sales lost
    tight = rows(sold=8, expired=0, closing=0)
    assert realized_reduce_net(tight, delta=10, price=5.0, unit_cost=2.0) == pytest.approx(2.0 * 10 - 5.0 * 10)


def test_score_is_the_share_of_replays_with_positive_net():
    c = score_replays([10.0, 5.0, -2.0, 8.0], Config())
    assert isinstance(c, Calibration) and c.score == pytest.approx(0.75) and c.n_backtest == 4
    assert c.effect_mean_usd == pytest.approx(5.25) and c.method == "backtest_replay"
    assert score_replays([], Config()).n_backtest == 0


def test_effect_below_the_noise_floor_caps_confidence_at_0_3():
    c = score_replays([0.2, 0.3, 0.1, 0.4] * 10, Config())  # always positive but tiny
    assert c.score == 1.0
    conf = confidence_for(c, option_net=0.25, cfg=Config())
    assert conf["score"] == 0.3 and conf["noise_capped"] is True and conf["n_backtest"] == 40
    ok = confidence_for(score_replays([20.0, 30.0, -1.0, 25.0], Config()), option_net=18.0, cfg=Config())
    assert ok["score"] == pytest.approx(0.75) and ok["noise_capped"] is False


def test_uncalibrated_actions_get_a_capped_score_with_zero_cases():
    conf = confidence_for(None, option_net=50.0, cfg=Config())
    assert conf == {"score": 0.3, "n_backtest": 0, "method": "uncalibrated", "noise_capped": False,
                    "effect_mean_usd": None, "noise_floor_usd": 1.0}


def test_replay_scores_stockout_orders_and_never_uses_outcomes_past_ref():
    from glazed_backend.metrics.replay import calibrate
    from glazed_backend.metrics.snapshot import StoreSnapshot
    from glazed_backend.metrics.types import Product, StoreInfo
    ref = date(2026, 3, 10)
    # SKU sells 10/day; only 6 units arrive daily (3-day shelf life) so it keeps stocking out: ordering more would have paid
    rs = [DayRow(ref - timedelta(days=59 - i), 6, 6, 0, 0, 12.0) for i in range(60)]
    snap = StoreSnapshot(StoreInfo(18.0), {"A": Product("A", "Item", "SUP", 5.0, 1.0, 1, 3)}, {"A": rs}, [],
                         {"SUP": (frozenset(range(1, 8)), 1, 0.0)})
    cal = calibrate(snap, ref, Config())
    assert all(r.date <= ref for r in snap.rows["A"])
    c = cal[("stockout_risk", "place_order")]
    assert c.n_backtest > 0 and 0.0 <= c.score <= 1.0
    empty = StoreSnapshot(StoreInfo(18.0), {}, {}, [], {})
    assert calibrate(empty, ref, Config()) == {}
