from datetime import date

import pytest
from fastapi.testclient import TestClient

from glazed_backend.adapters.driving.app import Container, create_app
from tests.fakes import (FakeClock, FakeCore, FakeMetrics, InMemoryAlerts, InMemoryBacktests, InMemoryCases,
                         InMemoryExecutions, InMemoryProposals, InMemoryTrace)

OPT = {"option_id": "opt-place", "action_type": "place_order", "params": {"sku": "SKU-1", "qty": 12}, "tier": "N1",
       "tier_reasons": ["calibrated"], "net_usd_mid": 20.0}
OPT_NOTHING = {"option_id": "opt-none", "action_type": "do_nothing", "params": {}, "tier": "N0", "tier_reasons": [],
               "net_usd_mid": 0.0}
ISSUE = {"issue_id": "S030|stockout_risk|SKU-1", "kind": "stockout_risk", "severity_usd": 50.0, "sku": "SKU-1",
         "options": [OPT, OPT_NOTHING]}


@pytest.fixture
def env():
    metrics = FakeMetrics({date(2026, 3, 11): [ISSUE]})
    c = Container(metrics=metrics, core=FakeCore(), cases=InMemoryCases(), alerts=InMemoryAlerts(),
                  proposals=InMemoryProposals(), executions=InMemoryExecutions(), backtests=InMemoryBacktests(),
                  trace=InMemoryTrace(), clock=FakeClock())
    return TestClient(create_app(c)), c


def mkcase(client, **kw):
    r = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": "2026-03-10", **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_health(env):
    client, _ = env
    assert client.get("/api/v1/health").json()["status"] == "ok"


def test_case_lifecycle_and_fork(env):
    client, _ = env
    c = mkcase(client, title="x")
    assert client.get(f"/api/v1/cases/{c['case_id']}").json()["store_id"] == "S030"
    assert len(client.get("/api/v1/cases", params={"store_id": "S030"}).json()) == 1
    f = client.post(f"/api/v1/cases/{c['case_id']}/fork", json={"title": "what-if"})
    assert f.status_code == 201 and f.json()["parent_case_id"] == c["case_id"]
    assert client.get("/api/v1/cases/nope").status_code == 404
    assert client.post("/api/v1/cases", json={"store_id": "S", "sim_today": "2026-03-10", "mode": "prod"}).status_code == 400


def test_ask_and_poll_turn(env):
    client, _ = env
    c = mkcase(client)
    r = client.post(f"/api/v1/cases/{c['case_id']}/messages", json={"text": "hola"})
    assert r.status_code == 202
    t = client.get(f"/api/v1/cases/{c['case_id']}/turns/{r.json()['turn_id']}").json()
    assert t["status"] == "done" and t["reply"] == "echo: hola" and t["turn_id"] == r.json()["turn_id"]
    assert client.post(f"/api/v1/cases/{c['case_id']}/messages", json={"text": " "}).status_code == 400


def test_day_summary_and_future_date(env):
    client, _ = env
    c = mkcase(client)
    assert client.get(f"/api/v1/cases/{c['case_id']}/day-summary").json()["date"] == "2026-03-09"
    assert client.get(f"/api/v1/cases/{c['case_id']}/day-summary", params={"date": "2026-03-12"}).status_code == 400


def test_advance_alerts_proposals_decision_flow(env):
    client, _ = env
    c = mkcase(client)
    adv = client.post(f"/api/v1/cases/{c['case_id']}/advance", json={"days": 1}).json()
    assert adv["sim_today"] == "2026-03-11" and len(adv["new_alerts"]) == 1
    alert = client.get("/api/v1/alerts", params={"store_id": "S030"}).json()[0]
    assert alert["state"] == "nueva" and alert["alert_type"] == 2
    prop = client.post("/internal/v1/proposals", headers={"X-Glazed-Case": alert["case_id"], "X-Glazed-Agent": "supply"},
                       json={"issue_id": ISSUE["issue_id"], "option_id": "opt-place", "rationale": "r"})
    assert prop.status_code == 201 and prop.json()["agent_id"] == "supply"
    assert prop.json()["action_type"] == "place_order" and prop.json()["params"]["qty"] == 12 and prop.json()["tier"] == "N1"
    pending = client.get("/api/v1/proposals", params={"case_id": alert["case_id"], "status": "pending"}).json()
    assert len(pending) == 1
    assert client.post(f"/api/v1/proposals/{pending[0]['proposal_id']}/decision",
                       json={"approved": False}).status_code == 400  # reason required
    d = client.post(f"/api/v1/proposals/{pending[0]['proposal_id']}/decision", json={"approved": True, "reason": "ok"})
    assert d.json()["status"] == "executed" and d.json()["source"] == "simulated"
    assert client.get("/api/v1/alerts").json()[0]["state"] == "ejecutada"
    assert len(client.get(f"/api/v1/cases/{alert['case_id']}/executions").json()) == 1


def test_backtest_run_and_get(env):
    client, _ = env
    c = mkcase(client)
    r = client.post(f"/api/v1/cases/{c['case_id']}/backtests", json={"date_from": "2026-03-01", "date_to": "2026-03-02"})
    assert r.status_code == 201 and r.json()["label"] == "backtest" and r.json()["results"]["days"] == 2
    assert client.get(f"/api/v1/backtests/{r.json()['run_id']}").json()["policy"] == "simple_v0"
    assert len(client.get(f"/api/v1/cases/{c['case_id']}/backtests").json()) == 1


def test_trace_by_case_and_store(env):
    client, _ = env
    c = mkcase(client)
    ev = client.post("/internal/v1/events", headers={"X-Glazed-Case": c["case_id"]},
                     json={"from_agent": "orchestrator", "to_agent": "present", "kind": "message", "payload": {"a": 1}})
    assert ev.status_code == 201
    assert len(client.get("/api/v1/trace", params={"case_id": c["case_id"]}).json()) == 1
    assert len(client.get("/api/v1/trace", params={"store_id": "S030"}).json()) == 1


@pytest.mark.parametrize("path", ["/internal/v1/kpis", "/internal/v1/day-summary?date=2026-03-09", "/internal/v1/issues",
                                  "/internal/v1/order-plan", "/internal/v1/suppliers/performance", "/internal/v1/history",
                                  "/internal/v1/inventory/projection?sku=A", "/internal/v1/promos/PR1/evaluation"])
def test_internal_requires_valid_case(env, path):
    client, _ = env
    assert client.get(path).status_code == 400
    assert client.get(path, headers={"X-Glazed-Case": "ghost"}).status_code == 400


def test_internal_resolves_store_and_as_of_from_case(env):
    client, c = env
    case = mkcase(client)
    h = {"X-Glazed-Case": case["case_id"], "X-Glazed-Agent": "present"}
    k = client.get("/internal/v1/kpis", headers=h, params={"date_from": "2026-03-01", "date_to": "2026-03-07"}).json()
    assert k["store_id"] == "S030"
    assert ("kpis", "S030", date(2026, 3, 10), date(2026, 3, 1), date(2026, 3, 7)) in c.metrics.calls
    assert client.get("/internal/v1/day-summary", headers=h, params={"date": "2026-03-09"}).json()["date"] == "2026-03-09"
    assert client.get("/internal/v1/day-summary", headers=h, params={"date": "2026-03-11"}).status_code == 400
    assert client.get("/internal/v1/kpis", headers=h, params={"date_to": "2026-03-20"}).status_code == 400
    assert client.get("/internal/v1/issues", headers=h, params={"limit": 3}).status_code == 200
    # the Core may send its own session id (= case id) or the stored conversation id
    assert client.get("/internal/v1/history", headers=h).json()["as_of"] == "2026-03-10"


def test_internal_rejects_store_override_params(env):
    client, _ = env
    case = mkcase(client)
    r = client.get("/internal/v1/kpis", headers={"X-Glazed-Case": case["case_id"]},
                   params={"store_id": "S999", "as_of": "2030-01-01"})
    assert r.status_code == 200 and r.json()["store_id"] == "S030"  # ignored, never trusted


def test_stores_listing(env):
    client, _ = env
    s = client.get("/api/v1/stores").json()
    assert s[0].keys() >= {"store_id", "name", "format", "site_id", "region"}


def test_patch_alert_state_and_invalid_transition(env):
    client, _ = env
    c = mkcase(client)
    client.post(f"/api/v1/cases/{c['case_id']}/advance", json={"days": 1})
    a = client.get("/api/v1/alerts").json()[0]
    ok = client.patch(f"/api/v1/alerts/{a['alert_id']}", json={"state": "vista"})
    assert ok.status_code == 200 and ok.json()["state"] == "vista"
    assert client.patch(f"/api/v1/alerts/{a['alert_id']}", json={"state": "medida"}).status_code == 409
    assert client.patch("/api/v1/alerts/zzz", json={"state": "vista"}).status_code == 404


def test_trace_is_ordered_by_ts(env):
    client, _ = env
    c = mkcase(client)
    h = {"X-Glazed-Case": c["case_id"]}
    for k in ("message", "tool_call", "tool_result"):
        client.post("/internal/v1/events", headers=h, json={"from_agent": "a", "to_agent": "b", "kind": k})
    ts = [e["ts"] for e in client.get("/api/v1/trace", params={"store_id": "S030"}).json()]
    assert ts == sorted(ts) and len(ts) == 3


def test_internal_experiences_returns_list_and_degrades(env):
    client, c = env
    case = mkcase(client)
    h = {"X-Glazed-Case": case["case_id"]}
    r = client.get("/internal/v1/experiences", headers=h, params={"query": "x"})
    assert r.status_code == 200 and r.json() == [] and "BACKBOARD" in r.headers["x-glazed-warning"] or r.json() == []
    from glazed_backend.adapters.driven.memory import InMemoryExperienceMemory
    from glazed_backend.domain import Experience
    c.memory = InMemoryExperienceMemory()
    c.memory.remember("S030", Experience("promo uplift was low", "promo_evaluation", "S030", "d7"))
    got = client.get("/internal/v1/experiences", headers=h, params={"query": "promo", "limit": 3}).json()
    assert got[0].keys() >= {"text", "decision_id", "kind", "created_at", "score"} and got[0]["decision_id"] == "d7"
    assert client.get("/internal/v1/experiences").status_code == 400


def test_cors_allows_the_frontend_dev_origins(env):
    client, _ = env
    for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
        r = client.get("/api/v1/health", headers={"Origin": origin})
        assert r.headers["access-control-allow-origin"] == origin
        pre = client.options("/api/v1/alerts/x", headers={
            "Origin": origin, "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "content-type"})
        assert pre.status_code == 200 and "PATCH" in pre.headers["access-control-allow-methods"]
    assert "access-control-allow-origin" not in client.get(
        "/api/v1/health", headers={"Origin": "http://evil.example"}).headers


def test_cors_origins_are_configurable_via_env():
    from glazed_backend.adapters.driving.app import cors_origins_from_env
    assert cors_origins_from_env({}) == ["http://localhost:5173", "http://127.0.0.1:5173"]
    assert cors_origins_from_env({"GLAZED_CORS_ORIGINS": "https://a.test, https://b.test"}) == [
        "https://a.test", "https://b.test"]


def test_internal_api_resolves_peer_session_ids_to_the_parent_case(env):
    client, _ = env
    c = mkcase(client)
    peer = f"peer~{c['case_id']}~0b1c2d3e-aaaa-bbbb-cccc-1234567890ab"
    h = {"X-Glazed-Case": peer, "X-Glazed-Agent": "glazed_supply"}
    assert client.get("/internal/v1/history", headers=h).status_code == 200
    ev = client.post("/internal/v1/events", headers=h, json={"from_agent": "glazed_supply", "to_agent": "orchestrator"})
    assert ev.status_code == 201 and ev.json()["case_id"] == c["case_id"]
    trace = client.get("/api/v1/trace", params={"case_id": c["case_id"]}).json()
    assert [(e["from_agent"], e["kind"], e["case_id"]) for e in trace] == [
        ("supply", "tool_call", c["case_id"]), ("supply", "message", c["case_id"])]
    bad = client.get("/internal/v1/history", headers={"X-Glazed-Case": "peer~nope~u"})
    assert bad.status_code == 400


def advanced_case(client):
    c = mkcase(client)
    client.post(f"/api/v1/cases/{c['case_id']}/advance", json={"days": 1})
    return client.get("/api/v1/alerts", params={"store_id": "S030"}).json()[0]["case_id"]


def test_proposal_agent_is_stored_as_canonical_id(env):
    client, _ = env
    case_id = advanced_case(client)
    r = client.post("/internal/v1/proposals", headers={"X-Glazed-Case": case_id, "X-Glazed-Agent": "glazed_supply"},
                    json={"issue_id": ISSUE["issue_id"], "option_id": "opt-place", "rationale": "r"})
    assert r.status_code == 201, r.text
    assert "glazed_supply" not in r.text


def test_proposal_copies_action_params_and_tier_from_the_stored_option_ignoring_agent_values(env):
    client, _ = env
    case_id = advanced_case(client)
    r = client.post("/internal/v1/proposals", headers={"X-Glazed-Case": case_id, "X-Glazed-Agent": "glazed_orchestrator"},
                    json={"issue_id": ISSUE["issue_id"], "option_id": "opt-place", "action_type": "transfer_stock",
                          "params": {"sku": "HACK", "qty": 9999}, "tier": "N1", "rationale": "r"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["action_type"] == "place_order"
    assert {k: v for k, v in body["params"].items() if k not in ("decision_as_of", "expected")} == {
        "sku": "SKU-1", "qty": 12, "option_id": "opt-place"}
    assert body["params"]["decision_as_of"] == "2026-03-11" and body["params"]["expected"]["net_usd_mid"] == 20.0
    assert body["tier"] == "N1" and body["agent_id"] == "orchestrator" and body["rationale"] == "r"
    dn = client.post("/internal/v1/proposals", headers={"X-Glazed-Case": case_id},
                     json={"issue_id": ISSUE["issue_id"], "option_id": "opt-none", "rationale": "wait"})
    assert dn.json()["action_type"] == "do_nothing" and dn.json()["tier"] == "N0"


def test_unknown_option_or_issue_is_a_400_and_old_shape_without_option_id_too(env):
    client, _ = env
    case_id = advanced_case(client)
    h = {"X-Glazed-Case": case_id}
    assert client.post("/internal/v1/proposals", headers=h, json={"issue_id": ISSUE["issue_id"], "option_id": "nope"}).status_code == 400
    assert client.post("/internal/v1/proposals", headers=h, json={"issue_id": "S030|x|y", "option_id": "opt-place"}).status_code == 400
    assert client.post("/internal/v1/proposals", headers=h, json={"issue_id": ISSUE["issue_id"], "action_type": "place_order"}).status_code == 400
    assert client.get("/api/v1/proposals").json() == []


def test_options_served_by_issues_are_remembered_for_proposals(env):
    client, c = env
    case = mkcase(client, sim_today="2026-03-11")  # no alert exists for this issue yet
    h = {"X-Glazed-Case": case["case_id"]}
    assert client.get("/internal/v1/issues", headers=h).json()[0]["options"]
    r = client.post("/internal/v1/proposals", headers=h, json={"issue_id": ISSUE["issue_id"], "option_id": "opt-place"})
    assert r.status_code == 201, r.text


def test_public_proposal_route_reuses_the_option_lookup(env):
    client, _ = env
    case_id = advanced_case(client)
    r = client.post("/api/v1/proposals", json={"case_id": case_id, "issue_id": ISSUE["issue_id"],
                                               "option_id": "opt-place", "rationale": "go"})
    assert r.status_code == 201 and r.json()["status"] == "pending" and r.json()["tier"] == "N1"
    bad = client.post("/api/v1/proposals", json={"case_id": case_id, "issue_id": ISSUE["issue_id"], "option_id": "zzz"})
    assert bad.status_code == 400
    assert client.post("/api/v1/proposals", json={"case_id": "nope", "issue_id": "i", "option_id": "o"}).status_code == 404
    pid = r.json()["proposal_id"]
    assert client.post(f"/api/v1/proposals/{pid}/decision", json={"approved": True, "reason": "ok"}).status_code == 200


def test_public_order_plan_and_kpis_routes(env):
    client, _ = env
    c = mkcase(client)
    plan = client.get(f"/api/v1/cases/{c['case_id']}/order-plan").json()
    assert plan["case_id"] == c["case_id"] and plan["store_id"] == "S030" and plan["as_of"] == "2026-03-10"
    assert plan["store_display_name"] and isinstance(plan["lines"], list)
    k = client.get(f"/api/v1/cases/{c['case_id']}/kpis").json()
    assert k["case_id"] == c["case_id"] and k["date_to"] == "2026-03-10" and k["lost_sales_usd"]["mid"] >= 0
    assert client.get(f"/api/v1/cases/{c['case_id']}/kpis", params={"date_to": "2026-03-12"}).status_code == 400
    assert client.get("/api/v1/cases/nope/order-plan").status_code == 404


def test_record_event_from_core_tool_shape(env):
    client, _ = env
    c = mkcase(client)
    r = client.post("/internal/v1/events", headers={"X-Glazed-Case": c["case_id"], "X-Glazed-Agent": "glazed_sentinel"},
                    json={"type": "holiday", "date_from": "2026-03-08", "date_to": "2026-03-09", "note": "closed"})
    assert r.status_code == 201, r.text
    ev = r.json()
    assert (ev["from_agent"], ev["kind"]) == ("sentinel", "message")
    assert "holiday" in ev["payload"]["text"] and ev["payload"]["note"] == "closed"


def test_internal_metrics_explain(env):
    client, _ = env
    c = mkcase(client)
    h = {"X-Glazed-Case": c["case_id"], "X-Glazed-Agent": "glazed_present"}
    ok = client.get("/internal/v1/metrics/explain", headers=h, params={"metric": "net_sales"})
    assert ok.status_code == 200 and ok.json()["value"] == 1000.0 and ok.json()["formula"]
    bad = client.get("/internal/v1/metrics/explain", headers=h, params={"metric": "nope"})
    assert bad.status_code == 400 and "net_sales" in bad.json()["detail"]


def test_internal_data_reads_are_traced_as_agent_tool_calls(env):
    client, _ = env
    case = mkcase(client)
    h = {"X-Glazed-Case": case["case_id"], "X-Glazed-Agent": "glazed_supply"}
    assert client.get("/internal/v1/order-plan", headers=h).status_code == 200
    events = client.get("/api/v1/trace", params={"case_id": case["case_id"]}).json()
    assert len(events) == 1
    e = events[0]
    assert (e["from_agent"], e["to_agent"], e["kind"]) == ("supply", "backend", "tool_call")
    assert e["payload"]["tool"] == "order-plan"
    assert "order-plan" in e["payload"]["text"]
    # no agent header (e.g. a script) -> nothing recorded
    client.get("/internal/v1/order-plan", headers={"X-Glazed-Case": case["case_id"]})
    assert len(client.get("/api/v1/trace", params={"case_id": case["case_id"]}).json()) == 1


NAME = "Bayfront Municipal Airport · Gate Area West"


def test_stores_listing_has_display_name(env):
    client, _ = env
    s = client.get("/api/v1/stores").json()[0]
    assert s["display_name"] == NAME and s["site_name"] and s["site_type"] and s["region"]


def test_public_payloads_carry_store_display_name(env):
    client, _ = env
    c = mkcase(client)
    assert c["store_display_name"] == NAME
    assert client.get(f"/api/v1/cases/{c['case_id']}").json()["store_display_name"] == NAME
    assert client.get("/api/v1/cases").json()[0]["store_display_name"] == NAME
    assert client.get(f"/api/v1/cases/{c['case_id']}/day-summary").json()["store_display_name"] == NAME
    adv = client.post(f"/api/v1/cases/{c['case_id']}/advance", json={"days": 1}).json()
    assert adv["new_alerts"][0]["store_display_name"] == NAME
    assert client.get("/api/v1/alerts").json()[0]["store_display_name"] == NAME


def test_internal_payloads_carry_store_display_name(env):
    client, _ = env
    c = mkcase(client)
    h = {"X-Glazed-Case": c["case_id"]}
    assert client.get("/internal/v1/kpis", headers=h).json()["store_display_name"] == NAME
    assert client.get("/internal/v1/day-summary", headers=h).json()["store_display_name"] == NAME
    assert client.get("/internal/v1/order-plan", headers=h).json()["store_display_name"] == NAME
    client.post(f"/api/v1/cases/{c['case_id']}/advance", json={"days": 1})
    issues = client.get("/internal/v1/issues", headers=h).json()
    assert issues and issues[0]["store_display_name"] == NAME


def test_advance_upgrades_a_legacy_alert_that_has_no_options(env):
    client, c = env
    case = mkcase(client)
    legacy = {k: v for k, v in ISSUE.items() if k != "options"}
    from glazed_backend.domain import Alert
    c.alerts.add(Alert.new(2, "S030", case["case_id"], 50.0, legacy, ISSUE["issue_id"], date(2026, 3, 10)))
    client.post(f"/api/v1/cases/{case['case_id']}/advance", json={"days": 1})
    alert = client.get("/api/v1/alerts", params={"store_id": "S030"}).json()[0]
    assert [o["option_id"] for o in alert["issue"]["options"]] == ["opt-place", "opt-none"]


def test_internal_promo_audit_uses_the_case_store_and_date(env):
    client, c = env
    case = mkcase(client)
    r = client.post("/internal/v1/promos/audit", headers={"X-Glazed-Case": case["case_id"]},
                    json={"department": "bakery", "discount_pct": 15})
    assert r.status_code == 200 and r.json()["verdict"] == "block"
    assert ("promo_audit", "S030", date(2026, 3, 10), "bakery", 15.0) in c.metrics.calls
    assert client.post("/internal/v1/promos/audit", headers={"X-Glazed-Case": case["case_id"]},
                       json={"department": "bakery"}).status_code == 422


def test_internal_issues_can_be_filtered_by_kind_or_integrity_category(env):
    client, c = env
    case = mkcase(client, sim_today="2026-03-11")
    c.metrics.issues_by_date[date(2026, 3, 11)] = [ISSUE, {**ISSUE, "issue_id": "S030|sku_key_mismatch|X", "kind": "sku_key_mismatch",
                                                          "category": "integrity", "integrity": True}]
    h = {"X-Glazed-Case": case["case_id"]}
    assert len(client.get("/internal/v1/issues", headers=h).json()) == 2
    assert [i["kind"] for i in client.get("/internal/v1/issues", headers=h, params={"kind": "sku_key_mismatch"}).json()] == ["sku_key_mismatch"]
    assert [i["kind"] for i in client.get("/internal/v1/issues", headers=h, params={"category": "integrity"}).json()] == ["sku_key_mismatch"]


def test_experiences_expose_ref_and_how_to_re_verify_it(env):
    from glazed_backend.domain import Experience

    class Mem:
        def recall(self, store_id, query, limit=5):
            return [Experience("[S030 · promo_evaluation · PR002] ... ref=PR002", "promo_evaluation", store_id, None, ref="PR002"),
                    Experience("[S030] rejected decision_id=d9", "decision", store_id, "d9")]
    client, c = env
    c.memory = Mem()
    case = mkcase(client)
    got = client.get("/internal/v1/experiences", headers={"X-Glazed-Case": case["case_id"]}, params={"query": "bakery"}).json()
    assert got[0]["ref"] == "PR002" and got[0]["verify"] == {"tool": "evaluate_promo", "promo_id": "PR002"}
    assert got[1]["decision_id"] == "d9" and got[1]["verify"] == {"tool": "history", "decision_id": "d9"}


def test_internal_proposal_idempotency_key_dedupes_per_case(env):
    client, _ = env
    c1, c2 = mkcase(client), mkcase(client)
    for c in (c1, c2):
        client.post(f"/api/v1/cases/{c['case_id']}/advance", json={"days": 1})
    body = {"issue_id": ISSUE["issue_id"], "option_id": "opt-place", "rationale": "r"}

    def post(case, key=None):
        h = {"X-Glazed-Case": case["case_id"], "X-Glazed-Agent": "supply"}
        if key:
            h["Idempotency-Key"] = key
        return client.post("/internal/v1/proposals", headers=h, json=body)

    first = post(c1, "a" * 32)
    again = post(c1, "a" * 32)
    assert first.status_code == 201 and again.status_code == 200
    assert again.json()["proposal_id"] == first.json()["proposal_id"]
    assert len(client.get("/api/v1/proposals", params={"case_id": c1["case_id"]}).json()) == 1
    other = post(c2, "a" * 32)  # same key, different case: a different request
    assert other.status_code == 201 and other.json()["proposal_id"] != first.json()["proposal_id"]
    assert post(c1).status_code == 201 and post(c1).status_code == 201  # no header: current behaviour
    assert len(client.get("/api/v1/proposals", params={"case_id": c1["case_id"]}).json()) == 3


def test_public_proposal_idempotency_key(env):
    client, _ = env
    c = mkcase(client)
    client.post(f"/api/v1/cases/{c['case_id']}/advance", json={"days": 1})
    body = {"case_id": c["case_id"], "issue_id": ISSUE["issue_id"], "option_id": "opt-place"}
    a = client.post("/api/v1/proposals", json=body, headers={"Idempotency-Key": "k1"})
    b = client.post("/api/v1/proposals", json=body, headers={"Idempotency-Key": "k1"})
    assert (a.status_code, b.status_code) == (201, 200) and a.json()["proposal_id"] == b.json()["proposal_id"]
