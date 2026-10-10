from datetime import date

import pytest
from fastapi.testclient import TestClient

from glazed_backend.adapters.driving.app import Container, create_app
from tests.fakes import (FakeClock, FakeCore, FakeMetrics, InMemoryAlerts, InMemoryBacktests, InMemoryCases,
                         InMemoryExecutions, InMemoryProposals, InMemoryTrace)
from tests.unit.test_sentinel_api import ISSUE, ISSUE_X


@pytest.fixture
def env():
    metrics = FakeMetrics({date(2026, 3, 11): [ISSUE_X], date(2026, 3, 12): [ISSUE_X]})
    c = Container(metrics=metrics, core=FakeCore(), cases=InMemoryCases(), alerts=InMemoryAlerts(),
                  proposals=InMemoryProposals(), executions=InMemoryExecutions(), backtests=InMemoryBacktests(),
                  trace=InMemoryTrace(), clock=FakeClock())
    return TestClient(create_app(c)), c


def decided(client, mode="live", approve=True, sim="2026-03-11"):
    case = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": sim, "mode": mode}).json()
    h = {"X-Glazed-Case": case["case_id"]}
    client.get("/internal/v1/issues", headers=h)
    pid = client.post("/internal/v1/proposals", headers=h, json={"issue_id": ISSUE["issue_id"], "option_id": "opt-place",
                                                                   "rationale": "cover the gap"}).json()["proposal_id"]
    client.post(f"/api/v1/proposals/{pid}/decision", json={"approved": approve, "reason": "" if approve else "too expensive"})
    return case["case_id"], pid


def test_history_adds_the_decision_log_to_the_weekly_series(env):
    client, _ = env
    case_id, pid = decided(client)
    h = client.get("/internal/v1/history", headers={"X-Glazed-Case": case_id}).json()
    assert h["as_of"] and "decision_log" in h
    (d,) = h["decision_log"]
    assert d["decision_id"] == pid and d["status"] == "approved" and d["action_type"] == "place_order" and d["scope"] == "case"
    assert d["kind"] == "stockout_risk" and d["sku"] == "SKU-1" and d["rationale"] == "cover the gap"
    assert d["executions"][0]["status"] == "executed" and d["executions"][0]["source"] == "simulated"
    assert d["outcome"] is None  # the horizon has not passed at sim_today


def test_rejected_decisions_carry_their_reason_and_no_outcome(env):
    client, _ = env
    case_id, pid = decided(client, approve=False)
    (d,) = client.get("/internal/v1/history", headers={"X-Glazed-Case": case_id}).json()["decision_log"]
    assert d["status"] == "rejected" and d["reason"] == "too expensive" and d["outcome"] is None


def test_outcome_appears_once_the_horizon_passed(env):
    client, c = env
    case_id, pid = decided(client)
    client.post(f"/api/v1/cases/{case_id}/advance", json={"days": 4})
    (d,) = client.get("/internal/v1/history", headers={"X-Glazed-Case": case_id}).json()["decision_log"]
    assert d["outcome"]["diagnosis"] == "within_range" and d["outcome"]["label"] == "backtest"


def test_store_history_includes_other_live_cases_but_never_sandbox_ones(env):
    client, _ = env
    live_case, live_pid = decided(client)
    sandbox_case, sandbox_pid = decided(client, mode="sandbox")
    other, other_pid = decided(client, sim="2026-03-12")  # decided later than this case's date
    log = client.get("/internal/v1/history", headers={"X-Glazed-Case": live_case}).json()["decision_log"]
    ids = {d["decision_id"]: d["scope"] for d in log}
    assert ids == {live_pid: "case"}
    log2 = client.get("/internal/v1/history", headers={"X-Glazed-Case": other}).json()["decision_log"]
    assert {d["decision_id"]: d["scope"] for d in log2} == {other_pid: "case", live_pid: "store"}
    log3 = client.get("/internal/v1/history", headers={"X-Glazed-Case": sandbox_case}).json()["decision_log"]
    assert {d["decision_id"] for d in log3} == {sandbox_pid}
