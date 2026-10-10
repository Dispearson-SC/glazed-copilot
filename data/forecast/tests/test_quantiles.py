import numpy as np
import pytest

from forecast import calibration as c


def _inputs():
    rng = np.random.default_rng(0)
    f = np.repeat([0.7, 6.0], 4000)
    return f, rng.poisson(f)


def test_quantile_monotone_in_q_and_nonnegative():
    f, a = _inputs()
    grid = c.residual_grid(f, a)
    mu = np.array([0.7, 6.0, 6.0])
    prev = np.zeros(3)
    for q in (0.1, 0.2, 0.5, 0.74, 0.8, 0.9):
        cur = c.quantile(mu, grid, q)
        assert (cur >= 0).all() and (cur >= prev - 1e-9).all()
        prev = cur


def test_quantile_matches_poisson_reference():
    f, a = _inputs()
    grid = c.residual_grid(f, a)
    assert c.quantile(np.array([6.0]), grid, 0.5)[0] == pytest.approx(6, abs=1.01)
    assert c.quantile(np.array([6.0]), grid, 0.9)[0] == pytest.approx(9, abs=1.5)


def test_quantile_interpolates_between_grid_levels():
    f, a = _inputs()
    grid = c.residual_grid(f, a)
    lo, mid, hi = (c.quantile(np.array([6.0]), grid, q)[0] for q in (0.7, 0.74, 0.8))
    assert lo <= mid <= hi


def test_quantile_empirical_coverage_in_sample():
    f, a = _inputs()
    grid = c.residual_grid(f, a)
    q = c.quantile(f, grid, 0.74)
    assert (a <= q).mean() >= 0.74 - 0.02


def test_nb_alpha_recovers_overdispersion():
    rng = np.random.default_rng(1)
    mu = np.full(40000, 5.0)
    alpha = 0.5
    y = rng.negative_binomial(1 / alpha, 1 / (1 + alpha * mu))
    tab = c.nb_alpha_table(mu, y, edges=[0, np.inf])
    assert tab.loc[0, "alpha"] == pytest.approx(alpha, rel=0.1)
    assert c.apply_alpha(np.array([5.0]), tab)[0] == pytest.approx(alpha, rel=0.1)


def test_nb_alpha_floor_zero_for_underdispersed():
    mu = np.full(1000, 5.0)
    y = np.full(1000, 5.0)
    tab = c.nb_alpha_table(mu, y, edges=[0, np.inf])
    assert tab.loc[0, "alpha"] == 0.0
