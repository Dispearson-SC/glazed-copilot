from datetime import date, timedelta

import pytest

from glazed_backend.metrics.losses import lost_sales_window
from glazed_backend.metrics.types import DayRow

MON = date(2026, 2, 2)


def mk(i, sold, so=0.0):
    return DayRow(MON + timedelta(days=i), 10, sold, 0, 0, so)


def test_lost_sales_is_stockout_hours_times_hourly_rate_times_price():
    # normal Mondays sell 18 units over 18 open hours -> 1 unit/hour; 4 stockout hours at $5 -> $20
    rows = [mk(0, 18), mk(7, 18), mk(14, 18), mk(21, 6, so=4.0)]
    out = lost_sales_window(rows, price=5.0, open_hours=18.0, date_from=MON + timedelta(days=21), date_to=MON + timedelta(days=21))
    assert out["mid"] == pytest.approx(20.0) and out["low"] == pytest.approx(20.0) and out["high"] >= out["mid"]


def test_low_counts_only_partial_day_stockouts():
    rows = [mk(0, 18), mk(7, 18), mk(14, 18), mk(21, 0, so=18.0)]  # fully out all day
    out = lost_sales_window(rows, 5.0, 18.0, MON + timedelta(days=21), MON + timedelta(days=21))
    assert out["low"] == 0.0 and out["mid"] == pytest.approx(90.0)


def test_high_uses_a_higher_demand_rate_than_mid():
    rows = [mk(0, 9), mk(7, 18), mk(14, 27), mk(21, 5, so=6.0), mk(28, 0, so=18.0)]
    out = lost_sales_window(rows, 2.0, 18.0, MON + timedelta(days=21), MON + timedelta(days=28))
    assert out["high"] > out["mid"] > out["low"] > 0


def test_days_outside_the_window_are_ignored_and_no_reference_means_zero():
    rows = [mk(0, 18), mk(7, 4, so=9.0)]
    assert lost_sales_window(rows, 5.0, 18.0, MON, MON)["mid"] == 0.0
    assert lost_sales_window([mk(7, 0, so=9.0)], 5.0, 18.0, MON + timedelta(days=7), MON + timedelta(days=7))["mid"] == 0.0
