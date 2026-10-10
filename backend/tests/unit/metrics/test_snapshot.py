from datetime import date, timedelta

from glazed_backend.metrics.snapshot import StoreSnapshot
from glazed_backend.metrics.types import DayRow, Product, PurchaseOrder, StoreInfo

T = date(2026, 3, 10)


def snap():
    rows = {"A": [DayRow(T - timedelta(days=59 - i), 10, 8, 0, 2) for i in range(60)]}
    pos = [PurchaseOrder("p1", "A", T - timedelta(days=1), T, None, 12),            # in transit at T
           PurchaseOrder("p2", "A", T - timedelta(days=5), T - timedelta(days=4), T - timedelta(days=4), 10, 10),
           PurchaseOrder("p3", "A", T - timedelta(days=3), T - timedelta(days=2), T + timedelta(days=1), 20, 20)]
    return StoreSnapshot(StoreInfo(18.0), {"A": Product("A", "Item", "SUP", 4.0, 1.0, 6, 3)}, rows, pos,
                         {"SUP": (frozenset(range(1, 8)), 1, 100.0)}, {"SUP": "Supplier"})


def test_state_at_cuts_history_and_in_transit_at_the_decision_day():
    s = snap().state_at("A", T - timedelta(days=2))
    assert s.rows[-1].date == T - timedelta(days=2) and len(s.rows) == 56
    assert {q for _, q in s.in_transit} == {20}  # p3 ordered T-3 and not received by T-2; p1 not ordered yet
    now = snap().state_at("A", T)
    assert sorted(q for _, q in now.in_transit) == [12, 20]  # p3 received T+1 is still unknown at T


def test_supplier_profile_is_cut_at_t_and_typical_order_uses_past_orders():
    sn = snap()
    assert sn.state_at("A", T).supplier.lead_mean == 1.0
    assert sn.typical_order_qty("A", T) == 12.0  # median of 12, 10, 20
