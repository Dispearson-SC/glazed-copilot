import numpy as np
import pytest

from forecast import metrics as m


def test_wape_basic():
    assert m.wape([10, 10], [8, 14]) == pytest.approx(6 / 20)


def test_wape_zero_actual_is_nan():
    assert np.isnan(m.wape([0, 0], [1, 2]))


def test_bias_sign_positive_when_overforecast():
    assert m.bias([10, 10], [12, 14]) == pytest.approx(6 / 20)
    assert m.bias([10, 10], [8, 6]) == pytest.approx(-6 / 20)


def test_mase_scaled_by_series_scale():
    # errors 2 and 4 with scales 2 and 2 -> mean(1, 2) = 1.5
    assert m.mase([10, 10], [8, 14], [2, 2]) == pytest.approx(1.5)


def test_mase_ignores_zero_scale_rows():
    assert m.mase([10, 10], [8, 14], [2, 0]) == pytest.approx(1.0)


def test_naive_scale_is_mean_abs_seasonal_diff():
    y = np.array([1, 2, 3, 4, 3, 4, 5, 6, 5.0])  # lag 4 diffs: 2,2,2,2,2
    assert m.naive_scale(y, season=4) == pytest.approx(2.0)


def test_naive_scale_skips_nan_pairs():
    y = np.array([1, np.nan, 3, 1, 5, 3.0])  # lag 3: (1,1)->0, (nan,5) skip, (3,3)->0
    assert m.naive_scale(y, season=3) == pytest.approx(0.0)


def test_pinball_loss_known_values():
    # q=0.9: under-forecast by 10 costs 9, over-forecast by 10 costs 1
    assert m.pinball([20], [10], 0.9) == pytest.approx(9.0)
    assert m.pinball([10], [20], 0.9) == pytest.approx(1.0)


def test_coverage_inclusive_band():
    assert m.coverage([5, 10, 15, 20], [5, 5, 5, 5], [10, 10, 10, 10]) == pytest.approx(0.5)


def test_interval_score_pair():
    out = m.interval_summary([1, 2, 3, 4], [0, 0, 0, 0], [2, 2, 2, 2])
    assert out["coverage"] == pytest.approx(0.5)
    assert out["mean_width"] == pytest.approx(2.0)
