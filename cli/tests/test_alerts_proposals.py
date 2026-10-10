import json

from glazed_cli.state import State

ALERT = {"alert_id": "a1", "alert_type": 2, "store_id": "S030", "case_id": "c1", "severity_usd": 150.0,
         "state": "nueva", "issue": {}, "issue_key": "k1", "as_of": "2026-03-10"}
PROP = {"proposal_id": "p1", "case_id": "c1", "store_id": "S030", "issue_id": "i1",
        "action_type": "place_order", "params": {"qty": 5}, "tier": "N2", "rationale": "stockout",
        "status": "pending"}


def test_alerts_filters_in_query(api, run):
    api.on("GET", "/api/v1/alerts", [ALERT])
    r = run("alerts", "--store", "S030", "--state", "nueva")
    q = api.last().url.params
    assert q["store_id"] == "S030" and q["state"] == "nueva"
    assert "a1" in r.output and "150.00" in r.output


def test_alerts_no_filters_sends_none(api, run):
    api.on("GET", "/api/v1/alerts", [])
    r = run("alerts")
    assert dict(api.last().url.params) == {} and "No alerts" in r.output


def test_alert_seen_patches_state(api, run):
    api.on("PATCH", "/api/v1/alerts/a1", {**ALERT, "state": "vista"})
    r = run("alert", "seen", "a1")
    assert api.last().method == "PATCH" and api.last_json() == {"state": "vista"}
    assert "vista" in r.output


def test_proposals_defaults_to_current_case_and_status(api, run):
    State(current_case="c1").save()
    api.on("GET", "/api/v1/proposals", [PROP])
    r = run("proposals", "--status", "pending")
    q = api.last().url.params
    assert q["case_id"] == "c1" and q["status"] == "pending"
    assert "p1" in r.output and "place_order" in r.output


def test_proposals_without_case_lists_all(api, run):
    api.on("GET", "/api/v1/proposals", [])
    r = run("proposals")
    assert r.exit_code == 0 and "case_id" not in api.last().url.params


def test_decide_approve(api, run):
    api.on("POST", "/api/v1/proposals/p1/decision",
           {"execution_id": "e1", "proposal_id": "p1", "case_id": "c1", "source": "simulated",
            "status": "executed", "detail": "order placed"})
    r = run("decide", "p1", "--approve")
    assert api.last_json() == {"approved": True}
    assert "executed" in r.output and "simulated" in r.output


def test_decide_reject_with_reason(api, run):
    api.on("POST", "/api/v1/proposals/p1/decision",
           {"execution_id": "e1", "proposal_id": "p1", "case_id": "c1", "source": "simulated",
            "status": "not_executed", "detail": ""})
    run("decide", "p1", "--reject", "--reason", "too much stock")
    assert api.last_json() == {"approved": False, "reason": "too much stock"}


def test_decide_reject_requires_reason_locally(api, run):
    r = run("decide", "p1", "--reject")
    assert r.exit_code == 1 and "reason" in r.output and not api.calls


def test_decide_requires_exactly_one_flag(api, run):
    assert run("decide", "p1").exit_code == 1
    assert run("decide", "p1", "--approve", "--reject", "--reason", "x").exit_code == 1
    assert not api.calls


def test_decide_conflict_is_friendly(api, run):
    api.on("POST", "/api/v1/proposals/p1/decision", {"detail": "proposal already approved"}, 409)
    r = run("decide", "p1", "--approve")
    assert r.exit_code == 1 and "already approved" in r.output
