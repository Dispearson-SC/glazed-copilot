from datetime import date, timedelta

import pytest

from glazed_backend.metrics.inventory import SkuState, usable_stock
from glazed_backend.metrics.policy import recommend, shelf_class
from glazed_backend.metrics.schedule import first_delivery, parse_delivery_days, supplier_profile
from glazed_backend.metrics.types import DayRow, Product, PurchaseOrder, StoreInfo, SupplierProfile

T = date(2026, 3, 10)  # Tuesday
ALL = frozenset(range(1, 8))


def flat_rows(sold=10, received=10, closing=0, days=56, so=0.0, expired=0):
    return tuple(DayRow(T - timedelta(days=days - 1 - i), received, sold + (i % 2), expired, closing, so)
                 for i in range(days))


def sup(days=ALL, lead=1.0, p90=1.0, on_time=0.9):
    return SupplierProfile("SUP", frozenset(days), lead, p90, on_time)


def state(shelf, closing=0, rows=None, in_transit=(), supplier=None, price=4.0, cost=1.0, case=1):
    prod = Product("SKU", "Item", "SUP", price, cost, case, shelf)
    rows = rows if rows is not None else flat_rows(closing=closing)
    return SkuState(prod, T, rows, tuple(in_transit), supplier or sup(), StoreInfo(18.0))


def test_shelf_class_splits_the_three_policies():
    assert shelf_class(1) == "newsvendor" and shelf_class(0) == "newsvendor"
    assert shelf_class(2) == shelf_class(3) == shelf_class(5) == "order_up_to"
    assert shelf_class(150) == shelf_class(None) == "sS"


def test_delivery_days_parse_and_first_delivery_respects_weekdays_and_closures():
    assert parse_delivery_days("Mon/Thu") == frozenset({1, 4}) and parse_delivery_days("Daily") == ALL
    assert first_delivery(T, 1, frozenset({1, 4}), frozenset()) == date(2026, 3, 12)  # Tue + 1 -> Thu
    assert first_delivery(T, 1, ALL, frozenset({date(2026, 3, 11)})) == date(2026, 3, 12)  # closed Wed


def test_supplier_profile_uses_only_orders_received_by_t():
    pos = [PurchaseOrder("a", "S", date(2026, 3, 1), date(2026, 3, 2), date(2026, 3, 2), 5, 5),
           PurchaseOrder("b", "S", date(2026, 3, 3), date(2026, 3, 4), date(2026, 3, 6), 5, 5),
           PurchaseOrder("c", "S", date(2026, 3, 9), date(2026, 3, 10), date(2026, 3, 20), 5, 5)]  # not yet at T
    p = supplier_profile("SUP", pos, T, ALL, std_lead=1, min_order_value=100.0)
    assert p.lead_mean == pytest.approx(2.0) and p.on_time_rate == pytest.approx(0.5)
    assert p.lead_p90 == pytest.approx(2.8)
    empty = supplier_profile("SUP", [], T, ALL, std_lead=3)
    assert empty.lead_mean == 3 and empty.lead_p90 > 3


def test_usable_stock_excludes_units_that_expire_before_they_sell():
    # 2-day shelf life: yesterday's lot (10) expires after tomorrow, 5 on hand are all from yesterday.
    receipts = [(T - timedelta(days=1), 10), (T, 0)]
    # mean demand 1/day -> of 5 units on hand only 2 sell before the lot expires (lot sellable T-1..T)
    assert usable_stock(5, receipts, shelf_life=2, ref=T, daily_mean=lambda d: 1.0, until=T + timedelta(days=3)) == 0
    # a lot received today is sellable today and tomorrow: 2 of 5 usable at 1/day
    assert usable_stock(5, [(T, 5)], 2, T, lambda d: 1.0, T + timedelta(days=3)) == pytest.approx(1.0)


def test_non_perishable_stock_is_fully_usable():
    assert usable_stock(40, [], None, T, lambda d: 1.0, T + timedelta(days=5)) == 40


def test_one_day_items_use_the_newsvendor_quantile_of_next_day_demand():
    s = state(shelf=1)  # demand ~10-11 every day, CR = 3/4
    r = recommend(s, service=0.74)
    assert r.method == "newsvendor" and r.cover_days == [T + timedelta(days=1)]
    assert 10 <= r.qty_raw <= 13 and r.usable == 0


def test_in_transit_arriving_on_the_cover_day_reduces_a_newsvendor_order():
    base = recommend(state(1), 0.74).qty_raw
    s = state(1, in_transit=[(T + timedelta(days=1), 6)])
    assert recommend(s, 0.74).qty_raw == pytest.approx(base - 6, abs=1e-6)


def test_multi_day_items_cover_demand_until_the_next_delivery_minus_usable_and_in_transit():
    thu_only = sup(days={4})  # delivers Thursday: order today arrives Thu 12th, next delivery Thu 19th
    s = state(3, closing=0, supplier=thu_only)
    r = recommend(s, 0.74)
    assert r.method == "order_up_to"
    assert r.cover_days[0] == T + timedelta(days=1)
    assert r.cover_days[-1] == date(2026, 3, 14)  # capped by shelf life: Thu + 3 - 1 = Sat
    with_stock = recommend(state(3, closing=6, rows=flat_rows(closing=6, received=0), supplier=thu_only), 0.74)
    assert with_stock.qty_raw < r.qty_raw and with_stock.usable > 0
    with_po = recommend(state(3, supplier=thu_only, in_transit=[(date(2026, 3, 12), 8)]), 0.74)
    assert with_po.qty_raw == pytest.approx(r.qty_raw - 8)


def test_a_higher_service_level_orders_more():
    s = state(3)
    assert recommend(s, 0.85).qty_raw > recommend(s, 0.60).qty_raw


def test_non_perishables_use_s_S_and_only_order_below_the_reorder_point():
    rich = recommend(state(None, closing=500, rows=flat_rows(closing=500)), 0.95)
    assert rich.method == "sS" and rich.qty_raw == 0
    poor = recommend(state(None, closing=3, rows=flat_rows(closing=3)), 0.95)
    assert poor.qty_raw > 0 and poor.reorder_point > 0 and poor.order_up_to > poor.reorder_point


def test_p_late_adds_safety_stock_to_the_reorder_point():
    punctual = recommend(state(None, 3, supplier=sup(on_time=1.0, lead=2.0, p90=2.0)), 0.95)
    flaky = recommend(state(None, 3, supplier=sup(on_time=0.6, lead=2.0, p90=2.0)), 0.95)
    assert flaky.reorder_point > punctual.reorder_point


def test_loss_units_balance_overage_and_underage():
    from glazed_backend.metrics.policy import loss_units
    over, under = loss_units(10.0, 10.0, 2.0)
    assert over == pytest.approx(under) and under == pytest.approx(0.7979, abs=1e-3)
    assert loss_units(5.0, 5.0, 0.0) == (0.0, 0.0)


def test_rounding_evaluates_both_losses_and_does_not_always_round_up():
    from glazed_backend.metrics.policy import round_to_cases
    # cheap shortage (Cu 1) vs costly leftover (Co 9): 11 units needed, cases of 12 would add waste -> floor 0
    assert round_to_cases(2.0, 12, base=8.0, mean=8.0, sd=1.0, cu=1.0, co=9.0) == 0
    # costly shortage: round up to the full case
    assert round_to_cases(2.0, 12, base=8.0, mean=10.0, sd=2.0, cu=9.0, co=1.0) == 12
    assert round_to_cases(24.0, 12, 0.0, 24.0, 3.0, 3.0, 1.0) == 24
    assert round_to_cases(0.0, 12, 0.0, 0.0, 1.0, 1.0, 1.0) == 0
