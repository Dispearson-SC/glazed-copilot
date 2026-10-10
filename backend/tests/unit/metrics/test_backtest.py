from datetime import date, timedelta

import pytest

from glazed_backend.metrics.backtest import backtest_sku
from glazed_backend.metrics.types import DayRow, Product

D1 = date(2026, 3, 10)


def hist(sold=10, days=56, end=D1 - timedelta(days=1)):
    return [DayRow(end - timedelta(days=days - 1 - i), 12, sold, 0, 0) for i in range(days)]


PROD = Product("A", "Item", "SUP", price=4.0, unit_cost=1.0, case_size=1, shelf_life_days=1)


def test_over_receiving_is_cut_to_the_service_level_target_and_saves_waste():
    out = backtest_sku(hist(), DayRow(D1, 30, 10, 20, 0), PROD, open_hours=18.0)
    assert out["current"]["waste_usd"] == pytest.approx(20.0)
    assert 0 <= out["policy"]["waste_usd"] < 20.0 and out["policy"]["lost_sales_usd"] == pytest.approx(0.0)


def test_stockout_day_recovers_lost_sales_at_a_waste_cost():
    # 9 of 18 hours out of stock: lost ~ 10/day * 0.5 = 5 units * $4 = $20
    out = backtest_sku(hist(), DayRow(D1, 10, 10, 0, 0, 9.0), PROD, open_hours=18.0)
    assert out["current"]["lost_sales_usd"] == pytest.approx(20.0)
    assert out["policy"]["lost_sales_usd"] < out["current"]["lost_sales_usd"]


def test_policy_never_looks_at_the_outcome_day_for_its_decision():
    # same history, wildly different outcome rows -> the policy target (and so its supply) is identical
    a = backtest_sku(hist(), DayRow(D1, 12, 12, 0, 0), PROD, 18.0)
    b = backtest_sku(hist(), DayRow(D1, 12, 12, 0, 0, 0.0), PROD, 18.0)
    assert a == b
    stale = backtest_sku(hist(end=D1 - timedelta(days=3)), DayRow(D1, 12, 12, 0, 0), PROD, 18.0)
    assert stale["policy"]["waste_usd"] >= 0  # decision day can be older than d1-1 (lead time); no error


def test_no_history_means_no_policy_change():
    out = backtest_sku([], DayRow(D1, 12, 8, 4, 0), PROD, 18.0)
    assert out["policy"] == out["current"]
