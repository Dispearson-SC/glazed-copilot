"""GET /api/v1/cases/{id}/inventory and /internal/v1/inventory: stock, cover and turnover with no look-ahead."""
from datetime import timedelta

import pytest

from tests.fakes import make_series
from tests.unit.manager_support import AS_OF, START, build, dates_after, prod


def configure(m):
    flat = lambda d: 10  # noqa: E731
    m.series = [
        make_series("A", 4.0, START, AS_OF, flat, closing=lambda d: 20),          # 2 days of cover
        make_series("B", 3.0, START, AS_OF, lambda d: 2, closing=lambda d: 400),  # slow: 200 days of cover
        make_series("C", 3.0, START, AS_OF, flat, closing=lambda d: 100),         # 10 days of cover
        make_series("OLD", 3.0, START, AS_OF - timedelta(days=60), flat),         # inactive: dropped
    ]
    m.catalog = {"A": prod("Alpha", cost=1.0), "B": prod("Bravo", "Dry", cost=2.0), "C": prod("Charlie", cost=1.0),
                 "OLD": prod("Old")}
    m.selling = {"A", "B", "C", "X1", "X2"}  # X1, X2 sell without inventory data
    m.projections = {"A": {"sku": "A", "projected_stockout_date": "2026-07-21", "horizon": 14}}


def get(client, cid, **params):
    r = client.get(f"/api/v1/cases/{cid}/inventory", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_envelope_coverage_and_item_shape():
    client, cid, _ = build(configure)
    out = get(client, cid)
    assert out["as_of"] == "2026-07-19" and out["store_id"] == "S030" and out["source"]
    assert out["store_display_name"] == "Bayfront Municipal Airport · Gate Area West"
    assert out["coverage"] == {"skus_with_inventory": 3, "skus_selling": 5}
    a = next(i for i in out["items"] if i["sku"] == "A")
    assert a["product_name"] == "Alpha" and a["on_hand"] == 20 and a["days_of_cover"] == pytest.approx(2.0)
    assert a["inventory_value_usd"] == pytest.approx(20.0) and a["slow_mover"] is False
    assert a["projected_stockout_date"] == "2026-07-21" and a["projected"] is True
    assert {"avg_daily_demand", "turnover_28d", "weeks_of_supply", "last_sale_date", "department"} <= set(a)
    c = next(i for i in out["items"] if i["sku"] == "C")
    assert c["projected_stockout_date"] is None and "OLD" not in {i["sku"] for i in out["items"]}


def test_sorts_and_limit():
    client, cid, _ = build(configure)
    assert [i["sku"] for i in get(client, cid, sort="days_of_cover")["items"]] == ["A", "C", "B"]
    assert [i["sku"] for i in get(client, cid, sort="slow")["items"]][0] == "B"
    assert len(get(client, cid, limit=2)["items"]) == 2
    assert client.get(f"/api/v1/cases/{cid}/inventory", params={"sort": "bogus"}).status_code == 400


def test_projection_is_only_asked_for_skus_close_to_a_stockout():
    client, cid, m = build(configure)
    get(client, cid)
    asked = {c[3] for c in m.calls if c[0] == "inventory_projection"}
    assert asked == {"A", "C"}  # B has 200 days of cover


def test_no_look_ahead_even_if_the_adapter_leaks():
    def leaky(m):
        configure(m)
        m.leak = True
        m.series = [make_series("A", 4.0, START, AS_OF + timedelta(days=20), lambda d: 10, closing=lambda d: 20 if d <= AS_OF else 999)]
    client, cid, _ = build(leaky)
    out = get(client, cid)
    assert out["items"][0]["on_hand"] == 20 and out["items"][0]["last_sale_date"] == "2026-07-19"
    flagged = [p for p in dates_after(out) if not p.endswith("projected_stockout_date")]
    assert flagged == []


def test_internal_route_matches_public_and_asserts_store_and_as_of():
    client, cid, _ = build(configure)
    pub = get(client, cid, sort="turnover", limit=5)
    h = {"X-Glazed-Case": cid}
    internal = client.get("/internal/v1/inventory", headers=h, params={"sort": "turnover", "limit": 5})
    assert internal.status_code == 200 and internal.json() == pub
    assert client.get("/internal/v1/inventory", headers=h, params={"store_id": "S001"}).status_code == 400
    assert client.get("/internal/v1/inventory", headers=h, params={"as_of": "2026-07-20"}).status_code == 400
    assert client.get("/internal/v1/inventory", headers=h, params={"store_id": "S030", "as_of": "2026-07-19"}).status_code == 200
