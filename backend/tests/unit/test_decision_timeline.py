"""GET /api/v1/cases/{id}/decisions: proposals, decisions, executions and outcomes stitched for one case."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from glazed_backend.adapters.driving.app import Container, create_app
from tests.fakes import (FakeClock, FakeCore, FakeMetrics, InMemoryAlerts, InMemoryBacktests, InMemoryCases,
                         InMemoryExecutions, InMemoryProposals, InMemoryTrace)
from tests.unit.test_sentinel_api import ISSUE, ISSUE_X


@pytest.fixture
def env():
    metrics = FakeMetrics({date(2026, 3, 11): [ISSUE_X], date(2026, 3, 12): [ISSUE_X]})
    metrics.observed = {"net_usd": 18.0, "window": ["2026-03-12", "2026-03-14"], "waste_usd": 2.5,
                        "lost_sales_usd": 1.25, "censored": True}
    c = Container(metrics=metrics, core=FakeCore(), cases=InMemoryCases(), alerts=InMemoryAlerts(),
                  proposals=InMemoryProposals(), executions=InMemoryExecutions(), backtests=InMemoryBacktests(),
                  trace=InMemoryTrace(), clock=FakeClock())
    return TestClient(create_app(c)), c


def propose(client, c, approve=None, reason="", sim="2026-03-11"):
    case = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": sim}).json()
    h = {"X-Glazed-Case": case["case_id"]}
    client.get("/internal/v1/issues", headers=h)
    c.clock._now += timedelta(minutes=1)
    pid = client.post("/internal/v1/proposals", headers=h, json={"issue_id": ISSUE["issue_id"], "option_id": "opt-place",
                                                                   "rationale": "r"}).json()["proposal_id"]
    if approve is not None:
        c.clock._now += timedelta(minutes=1)
        client.post(f"/api/v1/proposals/{pid}/decision", json={"approved": approve, "reason": reason})
    return case["case_id"], pid


def timeline(client, cid, **params):
    r = client.get(f"/api/v1/cases/{cid}/decisions", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_empty_for_a_case_without_proposals_and_404_for_unknown(env):
    client, c = env
    cid = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": "2026-03-11"}).json()["case_id"]
    assert timeline(client, cid) == []
    assert client.get("/api/v1/cases/nope/decisions").status_code == 404


def test_a_pending_proposal_is_one_proposal_row_with_its_action_fields(env):
    client, c = env
    cid, pid = propose(client, c)
    (row,) = timeline(client, cid)
    assert row["kind"] == "proposal" and row["decision_id"] == pid and row["status"] == "proposed"
    assert row["issue_id"] == ISSUE["issue_id"] and row["action_type"] == "place_order"
    assert row["sku"] == "SKU-1" and row["qty"] == 12 and "outcome" not in row and row["ts"]


def test_approval_adds_decision_and_execution_rows_in_ts_order(env):
    client, c = env
    cid, pid = propose(client, c, approve=True, reason="ok")
    rows = timeline(client, cid)
    assert [r["kind"] for r in rows] == ["proposal", "decision", "execution"]
    assert [r["status"] for r in rows] == ["proposed", "approved", "executed"]
    assert [r["ts"] for r in rows] == sorted(r["ts"] for r in rows) and {r["decision_id"] for r in rows} == {pid}


def test_rejection_keeps_reason_and_category_and_has_no_execution_row(env):
    client, c = env
    cid, pid = propose(client, c, approve=False, reason="too expensive")
    rows = timeline(client, cid)
    assert [r["kind"] for r in rows] == ["proposal", "decision"]
    assert rows[1]["status"] == "rejected" and rows[1]["reason"] == "too expensive"
    assert "reason_category" not in rows[1]  # no classifier configured here: absent, never null


def test_injected_not_executed_is_a_real_execution_row(env):
    client, c = env
    cid, pid = propose(client, c, approve=True, reason="ok")
    client.post(f"/api/v1/cases/{cid}/inject", json={"execution": {"proposal_id": pid, "status": "not_executed",
                                                                    "detail": "supplier call skipped"}})
    ex = [r for r in timeline(client, cid) if r["kind"] == "execution"]
    assert sorted(r["status"] for r in ex) == ["executed", "not_executed"]
    assert any(r.get("reason") == "supplier call skipped" for r in ex)


def test_outcome_row_names_realized_fields_expected_range_and_censoring(env):
    client, c = env
    cid, pid = propose(client, c, approve=True, reason="ok")
    client.post(f"/api/v1/cases/{cid}/advance", json={"days": 4})
    rows = timeline(client, cid)
    out = next(r for r in rows if r["kind"] == "outcome")
    o = out["outcome"]
    assert o["label"] == "backtest"
    assert o["observed"]["net_usd"] == 18.0 and o["observed"]["waste_usd"] == 2.5
    assert o["observed"]["lost_sales_usd"] == 1.25 and o["observed"]["censored"] is True
    assert o["simulated"] == {"net_usd_low": 4.0, "net_usd_mid": 20.0, "net_usd_high": 30.0, "label": "simulated"}
    assert o["score"]["within_expected_range"] is True and o["score"]["error_vs_mid_usd"] == -2.0
    assert rows[-1]["kind"] == "outcome" and out["as_of"] == "2026-03-14"  # sorted after its decision


def test_no_outcome_row_before_the_horizon_passes(env):
    client, c = env
    cid, _ = propose(client, c, approve=True, reason="ok")
    assert all(r["kind"] != "outcome" for r in timeline(client, cid))


def test_from_and_to_filter_on_the_date_of_each_row(env):
    client, c = env
    cid, _ = propose(client, c, approve=True, reason="ok")
    today = c.clock.now().date().isoformat()
    assert len(timeline(client, cid, **{"from": today, "to": today})) == 3
    assert timeline(client, cid, **{"from": "2030-01-01"}) == []
    assert timeline(client, cid, to="2000-01-01") == []


def test_other_cases_decisions_do_not_leak(env):
    client, c = env
    cid, _ = propose(client, c, approve=True, reason="ok")
    other, _ = propose(client, c, approve=True, reason="ok")
    assert {r["decision_id"] for r in timeline(client, cid)} != {r["decision_id"] for r in timeline(client, other)}
