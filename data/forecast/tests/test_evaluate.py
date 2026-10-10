import pandas as pd
import pytest

from forecast import evaluate as ev


def frame():
    return pd.DataFrame(
        {
            "model": "m",
            "store_id": ["S1"] * 4,
            "sku": ["A"] * 4,
            "date": pd.date_range("2026-08-01", periods=4),
            "actual": [10.0, 10.0, 10.0, 10.0],
            "censored": [False, False, False, True],
            "forecast": [8.0, 12.0, 10.0, 6.0],
            "mu": [8.0, 12.0, 10.0, 6.0],
            "p10": [5.0, 5.0, 5.0, 3.0],
            "p74": [11.0, 13.0, 11.0, 8.0],
            "p90": [12.0, 14.0, 12.0, 9.0],
            "scale": [2.0] * 4,
        }
    )


def test_summary_scores_uncensored_rows_only():
    s = ev.summarize(frame())
    assert s["n"] == 3
    assert s["wape"] == pytest.approx(4 / 30)
    assert s["bias"] == pytest.approx(0.0)
    assert s["mase"] == pytest.approx((1 + 1 + 0) / 3)
    assert s["cov_p10_p90"] == 1.0
    assert s["pinball_p74"] == pytest.approx(0.26 * 5 / 3)


def test_summary_censored_scored_one_sided_and_separately():
    s = ev.summarize(frame())
    assert s["n_censored"] == 1
    assert s["cens_cov_p74"] == 0.0  # p74 = 8 < sale 10: under-forecast on a stockout day
    assert s["cens_pinball_p74"] == pytest.approx(0.74 * 2)


def test_summary_censored_overforecast_is_not_a_miss():
    f = frame()
    f.loc[3, "p74"] = 50.0
    s = ev.summarize(f)
    assert s["cens_cov_p74"] == 1.0
    assert s["cens_pinball_p74"] == 0.0


def test_group_summary_by_column():
    f = pd.concat([frame(), frame().assign(store_id="S2", actual=20.0)], ignore_index=True)
    t = ev.group_summary(f, "store_id")
    assert set(t["store_id"]) == {"S1", "S2"}
    assert (t["model"] == "m").all()


def test_series_scale_uses_lag7_and_skips_censored():
    d = pd.date_range("2026-01-01", periods=15)
    train = pd.DataFrame({"store_id": "S1", "sku": "A", "date": d, "units": [1.0] * 7 + [3.0] * 7 + [5.0], "censored": False})
    s = ev.series_scale(train).set_index(["store_id", "sku"])["scale"]
    assert s.loc[("S1", "A")] == pytest.approx((7 * 2 + 1 * 2) / 8)
    train.loc[train.index[7:], "censored"] = True
    s2 = ev.series_scale(train).set_index(["store_id", "sku"])["scale"]
    assert pd.isna(s2.loc[("S1", "A")])


def test_simulate_policy_lost_and_waste():
    df = pd.DataFrame(
        {
            "actual": [10.0, 4.0, 6.0, 9.0],
            "censored": [False, False, False, True],
            "S": [8.0, 9.0, 6.0, 0.0],
            "shelf_class": ["1d", "1d", "non-perishable", "1d"],
            "price": [2.0] * 4,
            "cost": [1.0] * 4,
        }
    )
    r = ev.simulate_policy(df)
    assert r["lost_units"] == 2.0  # row1 short by 2; censored row ignored
    assert r["waste_units"] == 5.0  # row2 leftover 5 of a 1-day item; non-perishable carried
    assert r["lost_value"] == 4.0
    assert r["waste_cost"] == 5.0
    assert r["fill_rate"] == pytest.approx(1 - 2 / 20)
    assert r["overstock_units"] == 5.0
