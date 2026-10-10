from datetime import date, timedelta

import pytest

from glazed_backend.metrics import transfers as xf
from glazed_backend.metrics.inventory import SkuState
from glazed_backend.metrics.types import DayRow, Product, StoreInfo, SupplierProfile

AS_OF = date(2026, 7, 19)  # a Sunday


def state(sold, closing, life=3, received_last=0, price=4.0, cost=1.0, next_delivery_days=frozenset({4})):
    rows = tuple(DayRow(AS_OF - timedelta(days=59 - i), received_last if i == 59 else 0, sold, 0, closing if i == 59 else 40, 0.0)
                 for i in range(60))
    sup = SupplierProfile("SUP", next_delivery_days, 2.0, 3.0, 1.0)
    return SkuState(Product("SKU1", "Sandwich", "SUP", price, cost, 1, life), AS_OF, rows, (), sup, StoreInfo())


def test_surplus_needs_shelf_life_that_survives_the_transit():
    s = state(sold=2, closing=30, life=1, received_last=30)
    assert xf.sender_surplus(s, lead=1)["eligible"]["mid"] == 0  # expires before it lands
    assert xf.sender_surplus(state(sold=2, closing=30, life=3, received_last=30), lead=1)["eligible"]["mid"] > 5
    assert xf.sender_surplus(state(sold=2, closing=30, life=None), lead=1) is None  # cannot expire


def test_option_qty_cost_and_net_formula():
    sender = state(sold=2, closing=30, life=3, received_last=30)
    rx = xf.Receiver("S2", "Near", True, state(sold=8, closing=0, price=5.0, cost=2.0))
    opt, why = xf.build_option(sender, "Here", "S1", rx, AS_OF)
    assert why == "" and opt["to_store"] == "S2" and opt["confidence"] == {"score": 0.3, "calibrated": False}
    q = opt["qty"]
    assert q >= 1 and q <= opt["surplus_units"] and q <= opt["deficit_units"] + 1
    assert opt["transfer_cost_usd"] == pytest.approx(15 + 0.10 * q)  # same site
    exp = opt["waste_avoided_usd"]["mid"] + opt["lost_sales_avoided_usd"]["mid"] - opt["transfer_cost_usd"]
    assert opt["net_usd"]["mid"] == pytest.approx(exp, abs=0.011) and opt["net_usd"]["mid"] > 0
    assert opt["net_usd"]["low"] <= opt["net_usd"]["mid"] <= opt["net_usd"]["high"]
    cross, _ = xf.build_option(sender, "Here", "S1", xf.Receiver("S3", "Far", False, rx.state), AS_OF)
    assert cross is None or cross["transfer_cost_usd"] == pytest.approx(35 + 0.20 * cross["qty"])


def test_no_option_without_receiver_deficit_or_when_not_profitable():
    sender = state(sold=2, closing=30, life=3, received_last=30)
    full = xf.Receiver("S2", "Full", True, state(sold=1, closing=200))
    assert xf.build_option(sender, "Here", "S1", full, AS_OF) == (None, "no_receiver_deficit")
    tiny = xf.Receiver("S2", "Tiny", False, state(sold=8, closing=0, price=1.2, cost=1.0))
    assert xf.build_option(sender, "Here", "S1", tiny, AS_OF)[1] == "not_profitable"


def test_compute_reports_a_reason_when_nothing_qualifies():
    sender = state(sold=2, closing=30, life=3, received_last=30)
    out = xf.compute({"SKU1": sender}, "S1", "Here", {}, AS_OF)
    assert out["options"] == [] and out["reasons"] == {"SKU1": "no_candidates"} and out["waste"]["SKU1"]["mid"] > 0
