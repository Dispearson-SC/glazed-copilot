from datetime import date

import pytest
from fastapi.testclient import TestClient

from glazed_backend.adapters.driving.app import Container, create_app
from tests.fakes import (FakeClock, FakeCore, FakeMetrics, InMemoryAlerts, InMemoryBacktests, InMemoryCases,
                         InMemoryExecutions, InMemoryProposals, InMemoryTrace)

ISSUE = {"issue_id": "S030|stockout_risk|SKU-1", "kind": "stockout_risk", "severity_usd": 50.0, "sku": "SKU-1"}


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
                       json={"issue_id": ISSUE["issue_id"], "action_type": "place_order", "params": {"sku": "SKU-1"},
                             "tier": "N2", "rationale": "r"})
    assert prop.status_code == 201 and prop.json()["agent_id"] == "supply"
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
    assert [(e["from_agent"], e["case_id"]) for e in trace] == [("supply", c["case_id"])]
    bad = client.get("/internal/v1/history", headers={"X-Glazed-Case": "peer~nope~u"})
    assert bad.status_code == 400


def test_proposal_agent_is_stored_as_canonical_id(env):
    client, _ = env
    c = mkcase(client)
    r = client.post("/internal/v1/proposals", headers={"X-Glazed-Case": c["case_id"], "X-Glazed-Agent": "glazed_supply"},
                    json={"issue_id": "S030|stockout_risk|SKU-1", "action_type": "place_order", "tier": "N1"})
    assert r.status_code == 201, r.text
    assert "glazed_supply" not in r.text


def test_proposal_from_core_tool_shape_without_tier(env):
    client, _ = env
    c = mkcase(client)
    r = client.post("/internal/v1/proposals", headers={"X-Glazed-Case": c["case_id"], "X-Glazed-Agent": "glazed_orchestrator"},
                    json={"issue_id": "S030|stockout_risk|SKU-1", "option_id": "A", "action_type": "place_order",
                          "params": {"sku": "SKU-1"}, "rationale": "r"})
    assert r.status_code == 201, r.text
    assert r.json()["tier"] == "N2" and r.json()["agent_id"] == "orchestrator"


def test_record_event_from_core_tool_shape(env):
    client, _ = env
    c = mkcase(client)
    r = client.post("/internal/v1/events", headers={"X-Glazed-Case": c["case_id"], "X-Glazed-Agent": "glazed_sentinel"},
                    json={"type": "holiday", "date_from": "2026-03-08", "date_to": "2026-03-09", "note": "closed"})
    assert r.status_code == 201, r.text
    ev = r.json()
    assert (ev["from_agent"], ev["kind"]) == ("sentinel", "message")
    assert "holiday" in ev["payload"]["text"] and ev["payload"]["note"] == "closed"
