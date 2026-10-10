"""GET /api/v1/cases/{id}/expiring and /internal/v1/expiring: lots about to expire, waste as a range, no look-ahead."""
from datetime import timedelta

import pytest

from tests.fakes import make_series
from tests.unit.manager_support import AS_OF, START, build, dates_after, prod


def fresh(sku, cost):
    return make_series(sku, 5.0, START, AS_OF, lambda d: 10, shelf_life=2,
                       closing=lambda d: 30 if d == AS_OF else 50, received=lambda d: 20 if AS_OF - timedelta(days=1) <= d <= AS_OF else 0)


def configure(m):
    m.series = [fresh("A", 2.0), fresh("CHEAP", 0.5),
                make_series("DRY", 5.0, START, AS_OF, lambda d: 10, shelf_life=None, closing=lambda d: 80)]
    m.catalog = {"A": prod("Sandwich", cost=2.0, life=2), "CHEAP": prod("Cookie", cost=0.5, life=2), "DRY": prod("Rice", life=None)}


def get(client, cid, **params):
    r = client.get(f"/api/v1/cases/{cid}/expiring", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_shape_sorting_and_totals():
    client, cid, _ = build(configure)
    out = get(client, cid)
    assert out["as_of"] == "2026-07-19" and out["store_id"] == "S030" and out["source"] and out["store_display_name"]
    assert out["days"] == 7
    assert {i["sku"] for i in out["items"]} == {"A", "CHEAP"}  # DRY has no shelf life
    mids = [i["waste_usd"]["mid"] for i in out["items"]]
    assert mids == sorted(mids, reverse=True) and out["items"][0]["sku"] == "A"
    first = out["items"][0]
    assert first["lot_age_inferred"] is True and first["product_name"] == "Sandwich" and first["shelf_life_days"] == 2
    assert first["waste_usd"]["low"] <= first["waste_usd"]["mid"] <= first["waste_usd"]["high"]
    assert [d["date"] for d in out["by_day"]] == ["2026-07-20", "2026-07-21"]
    assert out["total_waste_usd"]["mid"] == pytest.approx(sum(i["waste_usd"]["mid"] for i in out["items"]))
    assert out["total_waste_usd"]["mid"] == pytest.approx(sum(d["waste_usd"]["mid"] for d in out["by_day"]))


def test_days_window_limit_and_validation():
    client, cid, _ = build(configure)
    assert {i["expiry_date"] for i in get(client, cid, days=1)["items"]} == {"2026-07-20"}
    assert len(get(client, cid, limit=1)["items"]) == 1
    for bad in (0, 31):
        assert client.get(f"/api/v1/cases/{cid}/expiring", params={"days": bad}).status_code == 400


def test_projected_dates_are_flagged_and_nothing_else_is_after_as_of():
    client, cid, _ = build(configure)
    out = get(client, cid)
    assert all(i["projected"] is True for i in out["items"]) and all(d["projected"] is True for d in out["by_day"])
    assert dates_after(out) == []


def test_no_look_ahead_even_if_the_adapter_leaks():
    def leaky(m):
        configure(m)
        m.leak = True
        extra = make_series("A", 5.0, AS_OF + timedelta(days=1), AS_OF + timedelta(days=10), lambda d: 0, shelf_life=2,
                            closing=lambda d: 999, received=lambda d: 999)
        m.series = [type(m.series[0])("A", 5.0, 2, m.series[0].rows + extra.rows)] + m.series[1:]
    client, cid, _ = build(leaky)
    clean_client, clean_cid, _ = build(configure)
    assert get(client, cid)["items"] == get(clean_client, clean_cid)["items"]


def test_internal_route_matches_public_and_asserts_store_and_as_of():
    client, cid, _ = build(configure)
    h = {"X-Glazed-Case": cid}
    r = client.get("/internal/v1/expiring", headers=h, params={"days": 3})
    assert r.status_code == 200 and r.json() == get(client, cid, days=3)
    assert client.get("/internal/v1/expiring", headers=h, params={"store_id": "S001"}).status_code == 400
    assert client.get("/internal/v1/expiring", headers=h, params={"as_of": "2026-07-18"}).status_code == 400
