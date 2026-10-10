"""GET /api/v1/cases/{id}/deliveries and /internal/v1/deliveries: open POs and scheduled supplier slots, no look-ahead."""
from datetime import timedelta

from tests.unit.manager_support import AS_OF, build, dates_after


def line(po_id, expected, sup="SUP01", sku="A", qty=10, received=None):
    return {"po_id": po_id, "supplier_id": sup, "supplier_name": f"Name {sup}", "sku": sku, "product_name": "Alpha", "qty": qty,
            "unit_cost": 2.0, "order_date": AS_OF - timedelta(days=2), "expected_date": expected, "received_date": received}


def configure(m):
    m.pos = [line("PO1", AS_OF + timedelta(days=2)), line("PO2", AS_OF - timedelta(days=1)),
             line("PO3", AS_OF, received=AS_OF), line("PO4", AS_OF + timedelta(days=10))]
    m.suppliers_sched = [{"supplier_id": "SUP07", "supplier_name": "Name SUP07", "delivery_days": [2, 5]}]


def get(client, cid, **params):
    r = client.get(f"/api/v1/cases/{cid}/deliveries", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_envelope_days_and_delivery_shape():
    client, cid, _ = build(configure)
    out = get(client, cid)
    assert out["as_of"] == "2026-07-19" and out["store_id"] == "S030" and out["source"] and out["store_display_name"]
    assert out["window_days"] == 7
    dates = [d["date"] for d in out["days"]]
    assert dates == ["2026-07-19"] + [f"2026-07-{n}" for n in range(20, 27)]
    today = out["days"][0]["deliveries"]
    assert {(d["po_id"], d["status"]) for d in today} == {("PO2", "late"), ("PO3", "on_time")}
    tue = next(d for d in out["days"] if d["date"] == "2026-07-21")["deliveries"]
    po1 = next(d for d in tue if d["po_id"] == "PO1")
    assert po1["kind"] == "open_po" and po1["status"] == "expected" and po1["value_usd"] == 20.0
    assert po1["lines"] == [{"sku": "A", "product_name": "Alpha", "qty": 10}]
    assert any(d["kind"] == "scheduled" and d["supplier_id"] == "SUP07" for d in tue)
    assert "PO4" not in str(out)  # expected beyond the window


def test_days_validation_and_default():
    client, cid, _ = build(configure)
    assert len(get(client, cid, days=2)["days"]) == 3
    for bad in (0, 15):
        assert client.get(f"/api/v1/cases/{cid}/deliveries", params={"days": bad}).status_code == 400


def test_future_dates_are_flagged_projected_and_nothing_else_is_after_as_of():
    client, cid, _ = build(configure)
    out = get(client, cid)
    assert dates_after(out) == []
    assert all(d["projected"] is True for d in out["days"][1:]) and out["days"][0]["projected"] is False


def test_receipts_after_as_of_are_not_visible_even_if_the_adapter_leaks():
    def leaky(m):
        configure(m)
        m.pos = m.pos + [line("PO5", AS_OF + timedelta(days=1), received=AS_OF + timedelta(days=1))]
    client, cid, _ = build(leaky)
    out = get(client, cid)
    po5 = next(d for day in out["days"] for d in day["deliveries"] if d["po_id"] == "PO5")
    assert po5["status"] == "expected" and "received_date" not in po5
    assert dates_after(out) == []


def test_internal_route_matches_public_and_asserts_store_and_as_of():
    client, cid, _ = build(configure)
    h = {"X-Glazed-Case": cid}
    r = client.get("/internal/v1/deliveries", headers=h, params={"days": 3})
    assert r.status_code == 200 and r.json() == get(client, cid, days=3)
    assert client.get("/internal/v1/deliveries", headers=h, params={"store_id": "S009"}).status_code == 400
    assert client.get("/internal/v1/deliveries", headers=h, params={"as_of": "2026-07-25"}).status_code == 400
