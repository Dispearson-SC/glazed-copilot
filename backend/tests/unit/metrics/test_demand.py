from datetime import date, timedelta

import pytest

from glazed_backend.metrics.demand import horizon_demand, quantile, uncensor, weekday_stats
from glazed_backend.metrics.types import DayRow

START = date(2026, 2, 2)  # a Monday


def row(i, sold, so=0.0):
    return DayRow(START + timedelta(days=i), received=10, sold=sold, expired=0, closing=0, stockout_hours=so)


def test_quantile_interpolates_linearly():
    assert quantile([1, 2, 3, 4], 0.5) == pytest.approx(2.5)
    assert quantile([5], 0.9) == 5
    assert quantile([], 0.9) == 0.0


def test_uncensored_days_keep_their_sales():
    out = uncensor([row(0, 6), row(7, 8)], open_hours=18)
    assert out.demand[START] == 6 and out.censored_share == 0.0


def test_partial_stockout_scales_up_sales_by_open_fraction():
    # 9 of 18 hours out of stock and 4 sold -> demand 4 / (1 - 0.5) = 8, below the p90 of normal Mondays
    rows = [row(i * 7, 10) for i in range(0, 4)] + [row(28, 4, so=9.0)]
    out = uncensor(rows, open_hours=18)
    assert out.demand[START + timedelta(days=28)] == pytest.approx(8.0)
    assert out.censored_share == pytest.approx(1 / 5)


def test_estimate_is_capped_at_p90_of_uncensored_same_weekday_days():
    rows = [row(i * 7, 10) for i in range(0, 4)] + [row(28, 5, so=16.0)]  # 5 / (1 - 16/18) = 45 -> cap
    out = uncensor(rows, open_hours=18)
    assert out.demand[START + timedelta(days=28)] == pytest.approx(10.0)


def test_fully_out_of_stock_day_takes_the_cap_not_infinity():
    rows = [row(i * 7, 12) for i in range(0, 3)] + [row(21, 0, so=18.0)]
    assert uncensor(rows, open_hours=18).demand[START + timedelta(days=21)] == pytest.approx(12.0)


def test_without_any_uncensored_reference_sales_are_kept():
    out = uncensor([row(0, 3, so=18.0)], open_hours=18)
    assert out.demand[START] == 3 and out.censored_share == 1.0


def test_weekday_stats_use_same_weekday_samples_with_a_noise_floor():
    demand = {START + timedelta(days=7 * k): float(v) for k, v in enumerate([4, 6, 5, 5, 5, 5, 5, 5])}
    ref = START + timedelta(days=7 * 7)
    mean, sd = weekday_stats(demand, ref, weekday=1)
    assert mean == pytest.approx(5.0) and sd > 0
    flat = {START + timedelta(days=7 * k): 4.0 for k in range(8)}
    assert weekday_stats(flat, ref, 1)[1] == pytest.approx(0.5 * 4.0 ** 0.5)  # floor: half the Poisson sd


def test_weekday_stats_fall_back_to_pooled_days_when_few_samples():
    demand = {START + timedelta(days=i): 3.0 for i in range(1, 15)}  # no Mondays except none before ref
    mean, _ = weekday_stats(demand, START + timedelta(days=14), weekday=1)
    assert mean == pytest.approx(3.0)


def test_horizon_demand_sums_means_and_adds_variances():
    demand = {START + timedelta(days=i): 5.0 + (i % 2) for i in range(56)}
    ref = START + timedelta(days=55)
    days = [ref + timedelta(days=k) for k in (1, 2)]
    m1, s1 = weekday_stats(demand, ref, days[0].isoweekday())
    m2, s2 = weekday_stats(demand, ref, days[1].isoweekday())
    m, s = horizon_demand(demand, ref, days)
    assert m == pytest.approx(m1 + m2) and s == pytest.approx((s1 ** 2 + s2 ** 2) ** 0.5)
