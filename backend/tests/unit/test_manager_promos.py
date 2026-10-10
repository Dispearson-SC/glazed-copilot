"""GET /api/v1/cases/{id}/promos and /internal/v1/promos: promo list with audit verdict and evaluation of finished ones."""
from datetime import date

from tests.unit.manager_support import AS_OF, build, dates_after


def promo(pid, start, end, dept="Beverage", pct=15.0):
    return {"promo_id": pid, "promo_name": f"Promo {pid}", "department": dept, "category": "Coffee", "discount_pct": pct,
            "start_date": date.fromisoformat(start), "end_date": date.fromisoformat(end), "region_scope": "ALL"}


def configure(m):
    m.promos = [promo("PAST", "2026-07-01", "2026-07-10"), promo("EDGE", "2026-07-06", "2026-07-19", "Bakery"),
                promo("OLD", "2026-03-01", "2026-03-10"), promo("ACT", "2026-07-10", "2026-07-25"),
                promo("NEXT", "2026-07-25", "2026-08-01", "Dairy"), promo("FAR", "2026-09-01", "2026-09-05")]
    m.evals = {"PAST": {"promo_id": "PAST", "uplift_pct": 12.5, "status": "finished", "confidence": "low", "caveat": "naive"},
               "EDGE": {"promo_id": "EDGE", "uplift_pct": -3.0, "status": "finished", "confidence": "low"},
               "ACT": {"promo_id": "ACT", "uplift_pct": 40.0, "status": "running", "confidence": "low"}}
    m.audit_verdicts = {"Bakery": "allow", "Dairy": "insufficient_evidence"}


def get(client, cid, **params):
    r = client.get(f"/api/v1/cases/{cid}/promos", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_all_statuses_in_the_window_sorted_and_shaped():
    client, cid, _ = build(configure)
    out = get(client, cid)
    assert out["as_of"] == "2026-07-19" and out["store_id"] == "S030" and out["source"] and out["store_display_name"]
    assert [i["promo_id"] for i in out["items"]] == ["ACT", "NEXT", "EDGE", "PAST"]  # OLD and FAR are outside 14 days
    act = out["items"][0]
    assert act["name"] == "Promo ACT" and act["department"] == "Beverage" and act["discount_pct"] == 15.0
    assert act["start_date"] == "2026-07-10" and act["end_date"] == "2026-07-25" and act["status"] == "active"
    assert act["audit_verdict"] == "block"


def test_status_filter_and_days_and_limit():
    client, cid, _ = build(configure)
    assert [i["promo_id"] for i in get(client, cid, status="past")["items"]] == ["EDGE", "PAST"]
    assert [i["promo_id"] for i in get(client, cid, status="upcoming")["items"]] == ["NEXT"]
    assert [i["promo_id"] for i in get(client, cid, status="past", days=200)["items"]] == ["EDGE", "PAST", "OLD"]
    assert len(get(client, cid, limit=2)["items"]) == 2
    for bad in ({"status": "bogus"}, {"days": 0}, {"days": 366}):
        assert client.get(f"/api/v1/cases/{cid}/promos", params=bad).status_code == 400


def test_evaluation_only_for_promos_that_ended_on_or_before_as_of():
    client, cid, m = build(configure)
    items = {i["promo_id"]: i for i in get(client, cid)["items"]}
    assert items["PAST"]["evaluation"]["uplift_pct"] == 12.5
    assert items["EDGE"]["evaluation"]["uplift_pct"] == -3.0  # ended on as_of
    assert items["ACT"]["evaluation"] is None and items["NEXT"]["evaluation"] is None
    asked = {c[3] for c in m.calls if c[0] == "promo_evaluation"}
    assert "ACT" not in asked and "NEXT" not in asked  # a running promo is never evaluated, whatever the adapter says


def test_audit_verdicts_come_from_promo_audit_as_known_when_the_promo_started():
    client, cid, m = build(configure)
    items = {i["promo_id"]: i for i in get(client, cid)["items"]}
    assert items["EDGE"]["audit_verdict"] == "allow" and items["NEXT"]["audit_verdict"] == "insufficient_evidence"
    audits = {(c[3], c[2]) for c in m.calls if c[0] == "promo_audit"}
    assert ("Bakery", date(2026, 7, 6)) in audits  # EDGE audited as of its own start, not with its own result
    assert ("Dairy", AS_OF) in audits  # an upcoming promo is audited as of today


def test_future_dates_are_flagged_as_projected():
    client, cid, _ = build(configure)
    out = get(client, cid)
    flags = {i["promo_id"]: i["projected"] for i in out["items"]}
    assert flags == {"ACT": True, "NEXT": True, "EDGE": False, "PAST": False}
    assert dates_after(out) == []


def test_internal_route_matches_public_and_asserts_store_and_as_of():
    client, cid, _ = build(configure)
    h = {"X-Glazed-Case": cid}
    r = client.get("/internal/v1/promos", headers=h, params={"status": "past"})
    assert r.status_code == 200 and r.json() == get(client, cid, status="past")
    assert client.get("/internal/v1/promos", headers=h, params={"store_id": "S002"}).status_code == 400
    assert client.get("/internal/v1/promos", headers=h, params={"as_of": "2026-07-01"}).status_code == 400
    assert client.get("/internal/v1/promos/ACT/evaluation", headers=h).status_code == 200  # the old route still works
