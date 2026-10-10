import numpy as np
import pytest

from forecast import calibration as c


def test_centered_grid_keeps_model_location_and_backtest_spread():
    rng = np.random.default_rng(0)
    f = np.full(5000, 6.0)
    a = rng.poisson(6.0, 5000) + 3  # backtest window drifted +3 above the model
    raw = c.residual_grid(f, a, center=False)
    cen = c.residual_grid(f, a, center=True)
    assert c.quantile(np.array([6.0]), raw, 0.5)[0] == pytest.approx(9, abs=1.1)
    # centered: the drift is removed, the spread is kept (median near the model mean)
    assert c.quantile(np.array([6.0]), cen, 0.5)[0] == pytest.approx(6, abs=1.1)
    spread_raw = c.quantile(np.array([6.0]), raw, 0.9)[0] - c.quantile(np.array([6.0]), raw, 0.1)[0]
    spread_cen = c.quantile(np.array([6.0]), cen, 0.9)[0] - c.quantile(np.array([6.0]), cen, 0.1)[0]
    assert spread_cen == pytest.approx(spread_raw)


def test_center_is_default_off_for_backward_compat():
    f = np.full(100, 6.0)
    a = np.full(100, 9.0)
    g = c.residual_grid(f, a)
    assert c.quantile(np.array([6.0]), g, 0.5)[0] == pytest.approx(9.0)
