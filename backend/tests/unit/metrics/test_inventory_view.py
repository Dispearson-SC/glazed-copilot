from datetime import date, timedelta

import pytest

from glazed_backend.metrics.inventory_view import SLOW_COVER_DAYS, inventory_item, sort_items
from glazed_backend.metrics.types import DayRow

AS_OF = date(2026, 7, 19)
PRODUCT = {"product_name": "Croissant", "department": "Bakery", "unit_cost": 1.5, "price": 4.0, "shelf_life_days": 2}


def rows(sold, closing, days=40, end=AS_OF):
    return [DayRow(end - timedelta(days=days - 1 - i), 0, sold(i), 0, closing(i), 0.0) for i in range(days)]


def test_item_basics_cover_turnover_value_and_last_sale():
    it = inventory_item("SKU1", PRODUCT, rows(lambda i: 10, lambda i: 30), AS_OF, 12.0)
    assert it["sku"] == "SKU1" and it["product_name"] == "Croissant" and it["department"] == "Bakery"
    assert it["on_hand"] == 30 and it["avg_daily_demand"] == pytest.approx(10.0)
    assert it["days_of_cover"] == pytest.approx(3.0) and it["weeks_of_supply"] == pytest.approx(0.43, abs=0.01)
    assert it["turnover_28d"] == pytest.approx(280 / 30, abs=0.01)  # units sold 28d / mean on hand
    assert it["inventory_value_usd"] == pytest.approx(45.0) and it["last_sale_date"] == AS_OF.isoformat()
    assert it["slow_mover"] is False


def test_slow_mover_when_cover_exceeds_the_threshold_or_no_sale_in_28_days():
    over = inventory_item("S", PRODUCT, rows(lambda i: 1, lambda i: 500), AS_OF, 12.0)
    assert over["days_of_cover"] > SLOW_COVER_DAYS and over["slow_mover"] is True
    stale = inventory_item("S", PRODUCT, rows(lambda i: 5 if i < 5 else 0, lambda i: 4), AS_OF, 12.0)
    assert stale["avg_daily_demand"] == 0 and stale["days_of_cover"] is None and stale["slow_mover"] is True
    assert stale["last_sale_date"] == (AS_OF - timedelta(days=35)).isoformat()


def test_nothing_after_as_of_is_read_and_inactive_skus_are_dropped():
    leaky = rows(lambda i: 10, lambda i: 30, days=40, end=AS_OF + timedelta(days=10))
    it = inventory_item("S", PRODUCT, leaky, AS_OF, 12.0)
    assert it["on_hand"] == 30 and it["last_sale_date"] == AS_OF.isoformat()
    old = rows(lambda i: 10, lambda i: 30, days=40, end=AS_OF - timedelta(days=30))
    assert inventory_item("S", PRODUCT, old, AS_OF, 12.0) is None  # no row in the last 28 days


def test_stockouts_are_uncensored_in_the_demand():
    rs = rows(lambda i: 10, lambda i: 20)
    rs[-1] = DayRow(AS_OF, 0, 5, 0, 0, 6.0)  # half the day out of stock: demand ~ 10
    it = inventory_item("S", PRODUCT, rs, AS_OF, 12.0)
    assert it["avg_daily_demand"] > 9.9 and it["on_hand"] == 0 and it["inventory_value_usd"] == 0


ITEMS = [
    {"sku": "A", "days_of_cover": 5.0, "turnover_28d": 2.0, "slow_mover": False, "inventory_value_usd": 10.0},
    {"sku": "B", "days_of_cover": 1.0, "turnover_28d": 9.0, "slow_mover": False, "inventory_value_usd": 5.0},
    {"sku": "C", "days_of_cover": None, "turnover_28d": 0.0, "slow_mover": True, "inventory_value_usd": 90.0},
    {"sku": "D", "days_of_cover": 60.0, "turnover_28d": 0.4, "slow_mover": True, "inventory_value_usd": 200.0},
]


def skus(order):
    return [i["sku"] for i in order]


def test_sort_orders():
    assert skus(sort_items(ITEMS, "days_of_cover")) == ["B", "A", "D", "C"]  # lowest cover first, unknown last
    assert skus(sort_items(ITEMS, "turnover")) == ["B", "A", "D", "C"]  # fastest first
    assert skus(sort_items(ITEMS, "slow")) == ["D", "C", "A", "B"]  # slow movers by value tied up, then the rest
    with pytest.raises(ValueError):
        sort_items(ITEMS, "bogus")
