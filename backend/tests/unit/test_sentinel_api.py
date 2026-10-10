from datetime import date

import pytest
from fastapi.testclient import TestClient

from glazed_backend.adapters.driving.app import Container, create_app
from tests.fakes import (FakeClock, FakeCore, FakeMetrics, InMemoryAlerts, InMemoryBacktests, InMemoryCases,
                         InMemoryExecutions, InMemoryProposals, InMemoryTrace)
from tests.unit.test_api import ISSUE

ISSUE_X = {**ISSUE, "options": [{**ISSUE["options"][0], "expected_benefit_usd": {"low": 14.0, "mid": 30.0, "high": 40.0},
                                  "cost_usd": 10.0, "net_usd_mid": 20.0}, ISSUE["options"][1]]}


@pytest.fixture
def env():
    metrics = FakeMetrics({date(2026, 3, 11): [ISSUE_X]})
    c = Container(metrics=metrics, core=FakeCore(), cases=InMemoryCases(), alerts=InMemoryAlerts(),
                  proposals=InMemoryProposals(), executions=InMemoryExecutions(), backtests=InMemoryBacktests(),
                  trace=InMemoryTrace(), clock=FakeClock())
    return TestClient(create_app(c)), c


def approved_decision(client):
    """A case on 2026-03-11 with one approved proposal. Returns (case_id, proposal_id)."""
    case = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": "2026-03-11"}).json()
    h = {"X-Glazed-Case": case["case_id"]}
    client.get("/internal/v1/issues", headers=h)
    pid = client.post("/internal/v1/proposals", headers=h, json={"issue_id": ISSUE["issue_id"], "option_id": "opt-place"}).json()["proposal_id"]
    client.post(f"/api/v1/proposals/{pid}/decision", json={"approved": True, "reason": "ok"})
    return case["case_id"], pid


def test_proposal_records_the_decision_date_and_the_simulated_range(env):
    client, _ = env
    case_id, pid = approved_decision(client)
    p = client.get("/api/v1/proposals", params={"case_id": case_id}).json()[0]
    assert p["params"]["decision_as_of"] == "2026-03-11"
    assert p["params"]["expected"] == {"net_usd_mid": 20.0, "net_usd_low": 4.0, "net_usd_high": 30.0, "cost_usd": 10.0}


def test_compliance_of_an_executed_decision_is_pending_until_the_horizon_passes(env):
    client, _ = env
    case_id, pid = approved_decision(client)
    r = client.get("/internal/v1/compliance", headers={"X-Glazed-Case": case_id}, params={"decision_id": pid})
    assert r.status_code == 200
    body = r.json()
    assert body["execution_status"] == "executed" and body["execution"]["source"] == "simulated"
    assert body["horizon"]["passed"] is False and body["diagnosis"] is None and body["observed"] is None
    listed = client.get("/internal/v1/compliance", headers={"X-Glazed-Case": case_id}).json()
    assert [d["decision_id"] for d in listed] == [pid]
    assert client.get("/internal/v1/compliance", headers={"X-Glazed-Case": case_id}, params={"decision_id": "nope"}).status_code == 404


def test_injected_not_executed_changes_the_compliance_and_is_tagged_demo_injected(env):
    client, _ = env
    case_id, pid = approved_decision(client)
    inj = client.post(f"/api/v1/cases/{case_id}/inject",
                      json={"execution": {"proposal_id": pid, "status": "not_executed", "detail": "supplier call skipped"}})
    assert inj.status_code == 201 and inj.json()["execution"]["source"] == "demo_injected"
    body = client.get(f"/api/v1/cases/{case_id}/compliance").json()[0]
    assert body["execution_status"] == "not_executed" and body["diagnosis"] == "not_executed"
    assert client.post(f"/api/v1/cases/{case_id}/inject", json={"execution": {"proposal_id": pid, "status": "executed"}}).status_code == 400
    assert client.post(f"/api/v1/cases/{case_id}/inject", json={"execution": {"proposal_id": "ghost", "status": "partial"}}).status_code == 404
    assert client.post(f"/api/v1/cases/{case_id}/inject", json={}).status_code == 400


def test_advance_raises_a_sentinel_alert_for_a_decision_that_was_not_executed(env):
    client, _ = env
    case_id, pid = approved_decision(client)
    client.post(f"/api/v1/cases/{case_id}/inject", json={"execution": {"proposal_id": pid, "status": "partial"}})
    adv = client.post(f"/api/v1/cases/{case_id}/advance", json={"days": 1}).json()
    sentinel = [a for a in adv["new_alerts"] if a["issue"]["kind"] == "compliance_deviation"]
    assert len(sentinel) == 1 and sentinel[0]["alert_type"] == 21
    iss = sentinel[0]["issue"]
    assert iss["issue_id"] == f"S030|compliance|{pid}" and iss["options"][-1]["action_type"] == "do_nothing"
    assert iss["compliance"]["diagnosis"] == "not_executed"
    again = client.post(f"/api/v1/cases/{case_id}/advance", json={"days": 1}).json()
    assert len([a for a in again["new_alerts"] if a["issue"]["kind"] == "compliance_deviation"]) == 1  # same alert, no duplicate
    assert len([a for a in client.get("/api/v1/alerts").json() if a["issue"]["kind"] == "compliance_deviation"]) == 1


def test_advance_stays_quiet_when_the_decision_was_executed_and_in_range(env):
    client, c = env
    case_id, pid = approved_decision(client)
    c.metrics.observed = {"net_usd": 20.0}
    adv = client.post(f"/api/v1/cases/{case_id}/advance", json={"days": 4}).json()
    assert not [a for a in adv["new_alerts"] if a["issue"]["kind"] == "compliance_deviation"]
    body = client.get(f"/api/v1/cases/{case_id}/compliance").json()[0]
    assert body["diagnosis"] == "within_range" and body["observed"]["label"] == "backtest"
    assert ("observed_outcome", "S030", date(2026, 3, 15), "place_order") in c.metrics.calls


def test_deviation_after_the_horizon_is_attributed_to_an_injected_event(env):
    client, c = env
    case_id, pid = approved_decision(client)
    c.metrics.observed = {"net_usd": -50.0}
    ev = client.post(f"/api/v1/cases/{case_id}/inject",
                     json={"event": {"type": "bloqueo", "date_from": "2026-03-12", "date_to": "2026-03-13", "note": "road blocked"}})
    assert ev.status_code == 201 and ev.json()["event"]["type"] == "bloqueo"
    assert client.post(f"/api/v1/cases/{case_id}/inject", json={"event": {"type": "alien"}}).status_code == 400
    client.post(f"/api/v1/cases/{case_id}/advance", json={"days": 4})
    body = client.get(f"/api/v1/cases/{case_id}/compliance").json()[0]
    assert body["diagnosis"] == "external_event" and body["events"][0]["type"] == "bloqueo"
    alerts = [a for a in client.get("/api/v1/alerts").json() if a["issue"]["kind"] == "compliance_deviation"]
    assert len(alerts) == 1 and alerts[0]["issue"]["compliance"]["diagnosis"] == "external_event"


def test_public_promo_audit_uses_the_case_store_and_clock(env):
    client, c = env
    case = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": "2026-03-11"}).json()
    r = client.post("/api/v1/promos/audit", json={"case_id": case["case_id"], "department": "Bakery", "discount_pct": 15})
    assert r.status_code == 200
    assert ("promo_audit", "S030", date(2026, 3, 11), "Bakery", 15.0) in c.metrics.calls


def test_public_promo_audit_unknown_case_is_404(env):
    client, _ = env
    r = client.post("/api/v1/promos/audit", json={"case_id": "nope", "department": "Bakery", "discount_pct": 15})
    assert r.status_code == 404
