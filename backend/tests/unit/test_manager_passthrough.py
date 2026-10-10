"""Public pass-throughs of the internal reads (issues, inventory projection, supplier performance, history):
same use case and same shape as /internal/v1/*, scoped by the case."""
from datetime import timedelta

from tests.unit.manager_support import AS_OF, build

ISSUES = [
    {"issue_id": "S030|stockout_risk|A", "kind": "stockout_risk", "category": "operational", "severity_usd": 50.0, "sku": "A"},
    {"issue_id": "S030|expiring|B", "kind": "expiring", "category": "operational", "severity_usd": 30.0, "sku": "B"},
    {"issue_id": "S030|integrity|X", "kind": "sku_mismatch", "category": "integrity", "exposure_usd": 90.0, "severity_usd": 0.0},
]


def configure(m):
    m.issues_by_date = {AS_OF: ISSUES}
    m.projections = {"A": {"sku": "A", "store_id": "S030", "as_of": "2026-07-19", "horizon": 7, "projected_stockout_date": "2026-07-21"}}
    start = AS_OF - timedelta(days=AS_OF.weekday())
    m.history_weeks = [{"week_start": (start - timedelta(weeks=k)).isoformat(), "net_sales": 100.0 + k, "waste_usd": 1.0}
                       for k in range(9, -1, -1)]


def both(client, cid, public, internal=None, **params):
    pub = client.get(f"/api/v1/cases/{cid}/{public}", params=params)
    internal = client.get(f"/internal/v1/{internal or public}", headers={"X-Glazed-Case": cid}, params=params)
    assert pub.status_code == 200 == internal.status_code, (pub.text, internal.text)
    assert pub.json() == internal.json()
    return pub.json()


def test_issues_filters_match_the_internal_route():
    client, cid, _ = build(configure)
    default = both(client, cid, "issues")
    assert [i["kind"] for i in default] == ["stockout_risk", "expiring"]  # integrity excluded by default
    assert [i["kind"] for i in both(client, cid, "issues", kind="expiring")] == ["expiring"]
    assert [i["kind"] for i in both(client, cid, "issues", category="integrity")] == ["sku_mismatch"]
    assert [i["kind"] for i in both(client, cid, "issues", category="all")] == ["sku_mismatch", "stockout_risk", "expiring"]
    assert len(both(client, cid, "issues", limit=1)) == 1
    assert all(i["store_display_name"] for i in default)


def test_served_issues_can_be_proposed_from_the_ui_route():
    client, cid, _ = build(configure)
    assert client.get(f"/api/v1/cases/{cid}/issues").status_code == 200
    assert (cid, "S030|stockout_risk|A") in client.container.served  # registered as served, like the internal route


def test_inventory_projection_passes_sku_and_horizon():
    client, cid, m = build(configure)
    out = both(client, cid, "inventory/projection", sku="A", horizon=14)
    assert out["projected_stockout_date"] == "2026-07-21"
    assert ("inventory_projection", "S030", AS_OF, "A", 14) in m.calls
    assert client.get(f"/api/v1/cases/{cid}/inventory/projection").status_code == 422  # sku is required


def test_supplier_performance_is_the_internal_list():
    client, cid, _ = build(configure)
    assert both(client, cid, "suppliers/performance") == [{"supplier_id": "SUP01", "on_time_pct": 90.0}]


def test_history_weeks_keeps_the_latest_n_and_both_routes_agree():
    client, cid, _ = build(configure)
    full = both(client, cid, "history")
    assert len(full["weeks"]) == 10 and "decision_log" in full
    last3 = both(client, cid, "history", weeks=3)
    assert [w["week_start"] for w in last3["weeks"]] == [w["week_start"] for w in full["weeks"][-3:]]
    assert client.get(f"/api/v1/cases/{cid}/history", params={"weeks": 0}).status_code == 400


def test_history_never_shows_a_week_after_as_of_even_if_the_adapter_leaks():
    def leaky(m):
        configure(m)
        m.leak = True
        m.history_weeks.append({"week_start": (AS_OF + timedelta(days=3)).isoformat(), "net_sales": 1.0, "waste_usd": 0.0})
    client, cid, _ = build(leaky)
    assert max(w["week_start"] for w in both(client, cid, "history")["weeks"]) <= AS_OF.isoformat()


def test_unknown_case_is_404():
    client, _, _ = build(configure)
    assert client.get("/api/v1/cases/nope/issues").status_code == 404
