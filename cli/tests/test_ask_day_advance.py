import json

from conftest import CASE
from glazed_cli.state import State


def _setup(api):
    State(current_case="c1").save()
    api.on("POST", "/api/v1/cases/c1/messages", {"turn_id": "t1"}, 202)


def test_ask_posts_and_polls_until_done(api, run):
    _setup(api)
    api.seq("GET", "/api/v1/cases/c1/turns/t1", [
        {"turn_id": "t1", "status": "pending"},
        {"turn_id": "t1", "status": "pending"},
        {"turn_id": "t1", "status": "done", "reply": "Ventas normales: $12,300."}])
    r = run("ask", "How was a normal day?")
    assert r.exit_code == 0, r.output
    post = [c for c in api.calls if c.method == "POST"][0]
    assert json.loads(post.content) == {"text": "How was a normal day?"}
    assert len([c for c in api.calls if c.method == "GET"]) == 3
    assert "Ventas normales: $12,300." in r.output


def test_ask_failed_turn_exits_1(api, run):
    _setup(api)
    api.on("GET", "/api/v1/cases/c1/turns/t1", {"turn_id": "t1", "status": "failed", "error": "llm down"})
    r = run("ask", "hi")
    assert r.exit_code == 1 and "llm down" in r.output


def test_ask_waiting_approval_shows_pending_proposals(api, run):
    _setup(api)
    api.on("GET", "/api/v1/cases/c1/turns/t1",
           {"turn_id": "t1", "status": "waiting_approval", "reply": "I propose an order."})
    api.on("GET", "/api/v1/proposals", [{
        "proposal_id": "p1", "case_id": "c1", "store_id": "S030", "issue_id": "i1",
        "action_type": "place_order", "params": {"qty": 5}, "tier": "N2",
        "rationale": "stockout risk", "status": "pending"}])
    r = run("ask", "reorder?")
    assert r.exit_code == 0
    assert "waiting for your approval" in r.output.lower()
    assert "p1" in r.output and "place_order" in r.output
    prop = [c for c in api.calls if c.url.path == "/api/v1/proposals"][0]
    assert prop.url.params["case_id"] == "c1" and prop.url.params["status"] == "pending"


def test_ask_timeout(api, run):
    _setup(api)
    api.on("GET", "/api/v1/cases/c1/turns/t1", {"turn_id": "t1", "status": "pending"})
    r = run("ask", "hi", "--timeout", "0")
    assert r.exit_code == 1 and "timed out" in r.output.lower() and "t1" in r.output


def test_ask_with_case_flag_does_not_change_current(api, run):
    State(current_case="c1").save()
    api.on("POST", "/api/v1/cases/c9/messages", {"turn_id": "t9"})
    api.on("GET", "/api/v1/cases/c9/turns/t9", {"turn_id": "t9", "status": "done", "reply": "ok"})
    r = run("ask", "hi", "--case", "c9")
    assert r.exit_code == 0 and State.load().current_case == "c1"


def test_ask_new_creates_isolated_case_first(api, run):
    State(current_case="c1").save()
    api.on("POST", "/api/v1/cases", {**CASE, "case_id": "c5"}, 201)
    api.on("POST", "/api/v1/cases/c5/messages", {"turn_id": "t5"})
    api.on("GET", "/api/v1/cases/c5/turns/t5", {"turn_id": "t5", "status": "done", "reply": "fresh"})
    r = run("ask", "hi", "--new", "--store", "S030", "--date", "2026-03-10")
    assert r.exit_code == 0, r.output
    assert [c.url.path for c in api.calls if c.method == "POST"][:2] == [
        "/api/v1/cases", "/api/v1/cases/c5/messages"]
    assert State.load().current_case == "c5"


def test_ask_new_requires_store_and_date(api, run):
    r = run("ask", "hi", "--new")
    assert r.exit_code == 1 and "--store" in r.output and "--date" in r.output


def test_ask_without_case_is_friendly(api, run):
    r = run("ask", "hi")
    assert r.exit_code == 1 and "case new" in r.output


def test_ask_json_prints_final_turn(api, run):
    _setup(api)
    api.on("GET", "/api/v1/cases/c1/turns/t1", {"turn_id": "t1", "status": "done", "reply": "ok"})
    r = run("--json", "ask", "hi")
    assert json.loads(r.output)["reply"] == "ok"


SUMMARY = {
    "date": "2026-03-09", "store_id": "S030", "sales_usd": 12345.5, "tickets": 210,
    "top_skus": [{"sku": "TAM-01", "units": 40, "sales_usd": 800.0}],
}


def test_day_defaults_to_sim_today_minus_one(api, run):
    State(current_case="c1").save()
    api.on("GET", "/api/v1/cases/c1", CASE)
    api.on("GET", "/api/v1/cases/c1/day-summary", SUMMARY)
    r = run("day")
    assert r.exit_code == 0, r.output
    ds = [c for c in api.calls if c.url.path.endswith("day-summary")][0]
    assert ds.url.params["date"] == "2026-03-09"
    assert "12,345.50" in r.output and "TAM-01" in r.output


def test_day_explicit_date_skips_case_lookup(api, run):
    State(current_case="c1").save()
    api.on("GET", "/api/v1/cases/c1/day-summary", SUMMARY)
    run("day", "--date", "2026-03-01")
    assert len(api.calls) == 1 and api.last().url.params["date"] == "2026-03-01"


def test_advance_days_lists_new_alerts(api, run):
    State(current_case="c1").save()
    api.on("POST", "/api/v1/cases/c1/advance", {"sim_today": "2026-03-13", "new_alerts": [{
        "alert_id": "a1", "alert_type": 2, "store_id": "S030", "case_id": "c1",
        "severity_usd": 150.0, "state": "nueva", "issue": {}, "issue_key": "k", "as_of": "2026-03-13"}]})
    r = run("advance", "--days", "3")
    assert api.last_json() == {"days": 3}
    assert "2026-03-13" in r.output and "a1" in r.output


def test_advance_to_date(api, run):
    State(current_case="c1").save()
    api.on("POST", "/api/v1/cases/c1/advance", {"sim_today": "2026-04-01", "new_alerts": []})
    r = run("advance", "--to", "2026-04-01")
    assert api.last_json() == {"to": "2026-04-01"}
    assert "No new alerts" in r.output


def test_advance_default_one_day(api, run):
    State(current_case="c1").save()
    api.on("POST", "/api/v1/cases/c1/advance", {"sim_today": "2026-03-11", "new_alerts": []})
    run("advance")
    assert api.last_json() == {"days": 1}


def test_advance_rejects_both_days_and_to(api, run):
    State(current_case="c1").save()
    r = run("advance", "--days", "2", "--to", "2026-04-01")
    assert r.exit_code == 1 and not api.calls
