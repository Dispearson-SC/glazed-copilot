import numpy as np
import pandas as pd
import pytest

from forecast import calibration as c
from forecast import models
from tests.helpers import synthetic_panel


def test_table_quantiles_per_bucket():
    f = np.array([1.0] * 10 + [10.0] * 10)
    a = np.concatenate([np.arange(0, 10) * 0.5 + 0.5, 10 + np.arange(-5, 5) * 2.0])
    t = c.residual_table(f, a, edges=[0, 5, np.inf], lo=0.1, hi=0.9)
    assert len(t) == 2
    assert t.loc[0, "q_lo"] == pytest.approx(np.quantile(a[:10] - 1, 0.1))
    assert t.loc[1, "q_hi"] == pytest.approx(np.quantile(a[10:] - 10, 0.9))


def test_apply_interval_nonnegative_ordered_and_bucketed():
    t = pd.DataFrame({"lower": [0, 5], "upper": [5, np.inf], "q_lo": [-3.0, -4.0], "q_hi": [2.0, 6.0]})
    out = c.apply_interval(np.array([1.0, 10.0]), t)
    assert out["p10"].tolist() == [0.0, 6.0]
    assert out["p90"].tolist() == [3.0, 16.0]
    assert (out["p10"] <= out["p90"]).all()


def test_backtest_uses_only_data_up_to_cutoff():
    panel = synthetic_panel(n_days=120)
    cutoff = pd.Timestamp("2026-03-15")
    base = c.backtest(panel[panel["date"] <= cutoff], cutoff, horizon_days=28)
    pert = panel.copy()
    pert.loc[pert["date"] > cutoff, "units"] = 9999.0
    again = c.backtest(pert[pert["date"] <= cutoff], cutoff, horizon_days=28)
    pd.testing.assert_frame_equal(base.reset_index(drop=True), again.reset_index(drop=True))
    assert base["date"].max() <= cutoff
    assert base["date"].min() > cutoff - pd.Timedelta(days=28)


def test_backtest_excludes_censored_actuals():
    panel = synthetic_panel(n_days=120)
    cutoff = pd.Timestamp("2026-03-15")
    mask = (panel["date"] > cutoff - pd.Timedelta(days=28)) & (panel["date"] <= cutoff) & (panel["sku"] == "A")
    panel.loc[mask, "censored"] = True
    bt = c.backtest(panel[panel["date"] <= cutoff], cutoff, horizon_days=28)
    assert "A" not in set(bt["sku"])


def test_select_half_life_returns_candidate():
    panel = synthetic_panel(n_days=140)
    cutoff = pd.Timestamp("2026-04-30")
    best, scores = c.select_half_life(panel[panel["date"] <= cutoff], cutoff, [None, 30], horizon_days=28)
    assert best in (None, 30)
    assert set(scores) == {None, 30}
