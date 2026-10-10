import numpy as np
import pandas as pd
import pytest

from forecast import baselines, glm, models
from tests.helpers import synthetic_panel

CUTOFF = pd.Timestamp("2026-03-01")  # 56 days in: 8 full weeks of training


def _key(df):
    return df.sort_values(["model", "store_id", "sku", "date"]).reset_index(drop=True)


def test_split_hides_actuals_from_future():
    panel = synthetic_panel()
    train, future = models.split_at_cutoff(panel, CUTOFF)
    assert train["date"].max() <= CUTOFF
    assert future["date"].min() > CUTOFF
    assert not {"units", "censored", "inv_covered"} & set(future.columns)


def test_no_leakage_forecast_independent_of_post_cutoff_actuals():
    panel = synthetic_panel()
    base = _key(models.forecast_all(panel, CUTOFF))
    pert = panel.copy()
    late = pert["date"] > CUTOFF
    pert.loc[late, "units"] = 10_000.0
    pert.loc[late, "censored"] = True
    pert.loc[late, "inv_covered"] = True
    again = _key(models.forecast_all(pert, CUTOFF))
    pd.testing.assert_frame_equal(base, again)


def test_fit_rejects_training_data_after_cutoff():
    panel = synthetic_panel()
    with pytest.raises(ValueError, match="after cutoff"):
        glm.fit_poisson(panel, CUTOFF)
    with pytest.raises(ValueError, match="after cutoff"):
        baselines.fit_baselines(panel, CUTOFF)


def test_seasonal_naive_repeats_last_week_by_weekday():
    panel = synthetic_panel(skus=("A",), stores=("S1",))
    train, future = models.split_at_cutoff(panel, CUTOFF)
    out = baselines.fit_baselines(train, CUTOFF).predict(future)
    sn = out["seasonal_naive"].set_index("date")["forecast"]
    last = train.set_index("date")["units"]
    for d in sn.index[:7]:
        prev = d - pd.Timedelta(days=7 * ((d - CUTOFF).days // 7 + (1 if (d - CUTOFF).days % 7 else 0)))
        assert sn[d] == last[prev]


def test_ma28_is_mean_of_last_four_same_weekdays():
    panel = synthetic_panel(skus=("A",), stores=("S1",))
    train, future = models.split_at_cutoff(panel, CUTOFF)
    out = baselines.fit_baselines(train, CUTOFF).predict(future)
    ma = out["ma28_weekday"].set_index("date")["forecast"]
    t = train.set_index("date")["units"]
    d = ma.index[0]
    hist = t[(t.index > CUTOFF - pd.Timedelta(days=28)) & (t.index.dayofweek == d.dayofweek)]
    assert ma[d] == pytest.approx(hist.mean())


def test_censored_days_are_excluded_from_baselines_and_fit():
    panel = synthetic_panel(skus=("A",), stores=("S1",))
    a = panel.copy()
    mask = (a["date"] > CUTOFF - pd.Timedelta(days=7)) & (a["date"] <= CUTOFF)
    a.loc[mask, "units"] = 0.0
    a.loc[mask, "censored"] = True
    b = panel[~mask]  # same rows physically removed
    fa = _key(models.forecast_all(a, CUTOFF))
    fb = _key(models.forecast_all(b, CUTOFF))
    pd.testing.assert_frame_equal(fa, fb)


def test_glm_recovers_weekday_pattern_and_level():
    panel = synthetic_panel(n_days=200, seed=1)
    cutoff = pd.Timestamp("2026-05-05")
    train, future = models.split_at_cutoff(panel, cutoff)
    mdl = glm.fit_poisson(train, cutoff)
    pred = mdl.predict(future)
    truth = panel[panel["date"] > cutoff].set_index(["store_id", "sku", "date"])["units"]
    pred = pred.set_index(["store_id", "sku", "date"])["forecast"].reindex(truth.index)
    assert abs(pred.sum() / truth.sum() - 1) < 0.05
    fri = pred[pred.index.get_level_values("date").dayofweek == 4].mean()
    mon = pred[pred.index.get_level_values("date").dayofweek == 0].mean()
    assert fri / mon == pytest.approx(1.5, rel=0.15)


def test_glm_skips_series_with_short_history():
    panel = synthetic_panel(skus=("A", "B"), stores=("S1",))
    short = panel[(panel["sku"] == "B") & (panel["date"] > CUTOFF - pd.Timedelta(days=5))]
    panel = pd.concat([panel[panel["sku"] == "A"], panel[(panel["sku"] == "B") & ~panel.index.isin(short.index) & (panel["date"] > CUTOFF)], short])
    out = models.forecast_all(panel, CUTOFF)
    assert set(out["sku"]) == {"A"}


def test_recency_weights_follow_half_life():
    dates = pd.to_datetime(["2026-01-01", "2026-01-11"])
    w = glm.recency_weights(dates, pd.Timestamp("2026-01-11"), half_life=10)
    assert w.tolist() == pytest.approx([0.5, 1.0])
    assert glm.recency_weights(dates, pd.Timestamp("2026-01-11"), half_life=None).tolist() == [1.0, 1.0]
