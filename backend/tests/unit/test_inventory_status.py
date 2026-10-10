"""C7: /inventory items carry forecast outflow, scheduled inbound, next delivery and a critical|watch|ok status."""
from datetime import timedelta

import pytest

from tests.fakes import make_series
from tests.unit.manager_support import AS_OF, START, build, dates_after, prod

D = lambda n: AS_OF + timedelta(days=n)  # noqa: E731


def po(sku, qty, when, received=None, ordered=None):
    return {"po_id": f"PO-{sku}", "supplier_id": "SUP01", "supplier_name": "North", "sku": sku, "product_name": sku, "qty": qty,
            "unit_cost": 1.0, "order_date": ordered or AS_OF - timedelta(days=2), "expected_date": when, "received_date": received}


def configure(m):
    flat = lambda d: 10  # noqa: E731
    m.series = [make_series("A", 4.0, START, AS_OF, flat, closing=lambda d: 20),     # cover 2.0
                make_series("B", 4.0, START, AS_OF, flat, closing=lambda d: 35),     # cover 3.5
                make_series("C", 4.0, START, AS_OF, flat, closing=lambda d: 100),    # cover 10
                make_series("D", 4.0, START, AS_OF, flat, closing=lambda d: 100)]    # cover 10, supplier calendar only
    m.catalog = {"A": prod("Alpha"), "B": prod("Bravo"), "C": prod("Charlie"), "D": prod("Delta", supplier="SUP09")}
    m.pos = [po("A", 60, D(3)), po("B", 60, D(3)), po("C", 40, D(1), received=AS_OF),   # C's order already received
             po("A", 5, D(9))]
    m.suppliers_sched = [{"supplier_id": "SUP09", "supplier_name": "Nine", "delivery_days": [D(2).isoweekday()]}]


def items(client, cid, **params):
    r = client.get(f"/api/v1/cases/{cid}/inventory", params=params)
    assert r.status_code == 200, r.text
    out = r.json()
    return out, {i["sku"]: i for i in out["items"]}


def test_outflow_inbound_and_next_delivery_default_three_days():
    client, cid, _ = build(configure)
    out, by = items(client, cid)
    a = by["A"]
    assert a["forecast_outflow_units"] == pytest.approx(30.0) and out["outflow_days"] == 3
    assert a["scheduled_in_units"] == 60 and a["next_delivery_date"] == D(3).isoformat()  # the D+9 order is outside 3 days
    assert by["C"]["scheduled_in_units"] == 0  # already received: it is in the closing stock
    assert by["D"]["next_delivery_date"] == D(2).isoformat() and by["D"]["scheduled_in_units"] == 0


def test_days_param_changes_the_window():
    client, cid, _ = build(configure)
    _, by = items(client, cid, days=10)
    assert by["A"]["forecast_outflow_units"] == pytest.approx(100.0) and by["A"]["scheduled_in_units"] == 65
    assert client.get(f"/api/v1/cases/{cid}/inventory", params={"days": 0}).status_code == 400


def test_status_rule_critical_watch_ok_and_reason_states_the_rule():
    client, cid, _ = build(configure)
    out, by = items(client, cid)
    assert by["A"]["status"] == "critical" and "antes de la próxima entrega" in by["A"]["status_reason"]
    assert by["B"]["status"] == "watch" and "menos de 1 día" in by["B"]["status_reason"]
    assert by["C"]["status"] == "ok" and by["D"]["status"] == "ok"
    assert "critical" in out["status_rule"] and "watch" in out["status_rule"]
    assert "2026-07-22" in by["A"]["status_reason"]


def test_no_known_delivery_uses_the_window_as_reference():
    def conf(m):
        configure(m)
        m.pos, m.suppliers_sched = [], []
    client, cid, _ = build(conf)
    _, by = items(client, cid)
    assert by["A"]["next_delivery_date"] is None and by["A"]["status"] == "critical"
    assert "sin entrega conocida" in by["A"]["status_reason"] and by["C"]["status"] == "ok"


def test_projected_flag_covers_the_future_dates_and_no_look_ahead_on_leaks():
    def conf(m):
        configure(m)
        m.leak = True
        m.pos.append(po("A", 999, D(1), ordered=D(1)))  # placed after the case date: unknown at as_of
    client, cid, _ = build(conf)
    out, by = items(client, cid)
    assert by["A"]["scheduled_in_units"] == 60
    assert all(i["projected"] is True for i in out["items"] if i["next_delivery_date"] or i["projected_stockout_date"])
    assert dates_after(out) == []


def test_internal_twin_has_the_same_fields():
    client, cid, _ = build(configure)
    r = client.get("/internal/v1/inventory", headers={"X-Glazed-Case": cid}, params={"days": 3})
    assert r.status_code == 200
    a = next(i for i in r.json()["items"] if i["sku"] == "A")
    assert a["status"] == "critical" and a["forecast_outflow_units"] == pytest.approx(30.0)
