"""R5: archived (test) cases leave every cross-case view, and cross-case items are dated by their simulated day."""
from datetime import date

import pytest

from glazed_backend.adapters.driven.memory import InMemoryExperienceMemory
from glazed_backend.domain import Experience
from tests.unit.copilot_support import stockout_issue, with_issues
from tests.unit.test_memories import decide, env, memories  # noqa: F401
from tests.unit.test_sentinel_api import approved_decision, env as sentinel_env  # noqa: F401

IID = "S030|stockout_risk|A"


def new_case(client, day="2026-07-19", mode="live"):
    r = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": day, "mode": mode})
    assert r.status_code == 201, r.text
    return r.json()["case_id"]


def archive(client, cid):
    r = client.post(f"/api/v1/cases/{cid}/archive")
    assert r.status_code == 200, r.text
    return r.json()


def test_archive_flags_the_case_and_it_is_idempotent():
    client, cid = env()
    assert client.get(f"/api/v1/cases/{cid}").json()["archived"] is False
    assert archive(client, cid)["archived"] is True and archive(client, cid)["archived"] is True
    assert client.get(f"/api/v1/cases/{cid}").json()["archived"] is True
    assert [c["archived"] for c in client.get("/api/v1/cases").json() if c["case_id"] == cid] == [True]
    assert client.post("/api/v1/cases/nope/archive").status_code == 404


def test_archiving_a_case_keeps_the_shared_issue_cases_and_their_alerts():
    """Issue cases are one per issue key, shared by the whole store: archiving a test case must not hide alerts."""
    client, cid = env(stockout_issue("A"))
    client.post(f"/api/v1/cases/{cid}/advance", json={"days": 0})
    alerts = client.get("/api/v1/alerts").json()
    assert len(alerts) == 1
    child = alerts[0]["case_id"]
    assert child != cid and client.get(f"/api/v1/cases/{child}").json()["parent_case_id"] == cid
    archive(client, cid)
    assert client.get(f"/api/v1/cases/{child}").json()["archived"] is False
    assert len(client.get("/api/v1/alerts").json()) == 1


def test_decision_log_other_case_skips_archived_cases_but_keeps_the_own_one():
    client, a = env(stockout_issue("A"))
    b = new_case(client)
    decide(client, a, True)
    decide(client, b, True)
    log = client.get("/internal/v1/history", headers={"X-Glazed-Case": b}).json()["decision_log"]
    assert {d["scope"] for d in log} == {"this_case", "other_case"}
    archive(client, a)
    log = client.get("/internal/v1/history", headers={"X-Glazed-Case": b}).json()["decision_log"]
    assert {d["scope"] for d in log} == {"this_case"}
    own = client.get("/internal/v1/history", headers={"X-Glazed-Case": a}).json()["decision_log"]
    assert [d["case_id"] for d in own if d["scope"] == "this_case"] == [a]  # an archived case still shows its own decisions


def test_memories_skip_archived_cases():
    client, a = env(stockout_issue("A"))
    b = new_case(client)
    decide(client, a, False, "muy caro")
    assert len(memories(client, b)) == 1
    archive(client, a)
    assert memories(client, b) == [] and len(memories(client, a)) == 1


def test_briefing_pending_count_and_recent_decisions_skip_archived_cases():
    client, a = env(stockout_issue("A"))
    b = new_case(client)
    client.post("/internal/v1/proposals", headers={"X-Glazed-Case": a}, json={"issue_id": IID, "option_id": "bestA"})
    decide(client, a, True, iid=IID, oid="altA")
    s = client.get("/internal/v1/snapshot", headers={"X-Glazed-Case": b}).json()
    assert s["other_cases_pending_count"] == 1 and len(s["recent_decisions"]) == 1
    archive(client, a)
    s = client.get("/internal/v1/snapshot", headers={"X-Glazed-Case": b}).json()
    assert s["other_cases_pending_count"] == 0 and s["recent_decisions"] == []


def test_memories_are_dated_by_the_simulated_day_not_the_wall_clock():
    client, cid = env(stockout_issue("A"), stockout_issue("B"))
    decide(client, cid, True, iid=IID, oid="altA")
    decide(client, cid, False, "muy caro", iid="S030|stockout_risk|B", oid="bestB")
    got = memories(client, cid)
    assert len(got) == 2 and all(m["created_at"].startswith("2026-07-19") for m in got)  # the wall clock is 2026-10-10
    assert all(m["new"] is True for m in got)  # `new` still reads the moment the record was written


def test_a_decision_made_after_this_case_date_is_not_visible_but_an_earlier_one_is_even_if_its_case_moved_on():
    client, a = env(stockout_issue("A"), stockout_issue("B"))
    client.container.metrics.issues_by_date[date(2026, 7, 25)] = [stockout_issue("A"), stockout_issue("B")]
    b = new_case(client)
    decide(client, b, False, "muy caro", iid=IID, oid="bestA")  # decided on 2026-07-19
    client.post(f"/api/v1/cases/{b}/advance", json={"days": 6})  # b now stands on 2026-07-25
    decide(client, b, False, "demasiado caro", iid="S030|stockout_risk|B", oid="bestB")  # decided on 2026-07-25
    seen = [m["text"] for m in memories(client, a)]
    assert len(seen) == 1 and "muy caro" in seen[0]
    log = client.get("/internal/v1/history", headers={"X-Glazed-Case": a}).json()["decision_log"]
    assert [d["decided_as_of"] for d in log] == ["2026-07-19"]


def test_experiences_tied_to_archived_cases_are_excluded_everywhere():
    client, a = env(stockout_issue("A"))
    b = new_case(client)
    decide(client, a, True, iid=IID, oid="altA")
    pid = client.get("/api/v1/proposals", params={"case_id": a}).json()[0]["proposal_id"]
    mem = InMemoryExperienceMemory()
    mem.remember("S030", Experience("[S030 · outcome · place_order] measured: ok", "outcome", "S030", pid))
    mem.remember("S030", Experience("promo evaluation", "promo_evaluation", "S030", None, ref="PR1"))
    client.container.memory = mem
    h = {"X-Glazed-Case": b}
    assert len(client.get("/internal/v1/experiences", headers=h).json()) == 2
    archive(client, a)
    got = client.get("/internal/v1/experiences", headers=h).json()
    assert [g["kind"] for g in got] == ["promo_evaluation"]
    assert [m["source"] for m in memories(client, b) if m["source"] == "backboard"] == ["backboard"]  # only the promo one


@pytest.mark.parametrize("archived,alerts", [(True, 0), (False, 1)])
def test_sentinel_deviations_of_archived_cases_do_not_raise_alerts(sentinel_env, archived, alerts):  # noqa: F811
    client, _ = sentinel_env
    a, pid = approved_decision(client)
    client.post(f"/api/v1/cases/{a}/inject", json={"execution": {"proposal_id": pid, "status": "partial"}})
    b = new_case(client, "2026-03-11")
    if archived:
        archive(client, a)
    adv = client.post(f"/api/v1/cases/{b}/advance", json={"days": 1}).json()
    assert len([x for x in adv["new_alerts"] if x["issue"]["kind"] == "compliance_deviation"]) == alerts
