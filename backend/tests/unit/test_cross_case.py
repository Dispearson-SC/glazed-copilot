"""Q4: store-scoped data shown to agents says which case it came from; injected events link to what they explain."""
from tests.unit.test_sentinel_api import approved_decision, env  # noqa: F401 - fixture
from tests.unit.test_snapshot import env as snap_env, mkcase, snap  # noqa: F401 - fixture


def test_briefing_pending_is_this_case_only_and_counts_the_rest(snap_env):  # noqa: F811
    client, _, _ = snap_env
    a, b = mkcase(client), mkcase(client)
    ia, ib = snap(client, a)["top_issues"][0], snap(client, b)["top_issues"][1]
    pa = client.post("/internal/v1/proposals", headers={"X-Glazed-Case": a},
                     json={"issue_id": ia["issue_id"], "option_id": ia["options"][0]["option_id"]}).json()
    client.post("/internal/v1/proposals", headers={"X-Glazed-Case": b},
                json={"issue_id": ib["issue_id"], "option_id": ib["options"][0]["option_id"]})
    s = snap(client, a)
    assert [(p["proposal_id"], p["scope"], p["same_case"], p["case_id"]) for p in s["pending_proposals"]] == [
        (pa["proposal_id"], "this_case", True, a)]
    assert s["other_cases_pending_count"] == 1
    client.post(f"/api/v1/proposals/{pa['proposal_id']}/decision", json={"approved": True, "reason": "ok"})
    s = snap(client, b)
    assert [p["same_case"] for p in s["pending_proposals"]] == [True] and s["other_cases_pending_count"] == 0
    assert [(d["scope"], d["same_case"]) for d in s["recent_decisions"]] == [("other_case", False)]


def test_decision_log_labels_this_case_and_other_case(env):  # noqa: F811
    client, _ = env
    a, pa = approved_decision(client)
    b, pb = approved_decision(client)
    log = client.get("/internal/v1/history", headers={"X-Glazed-Case": b}).json()["decision_log"]
    by = {d["decision_id"]: d for d in log}
    assert by[pb]["scope"] == "this_case" and by[pb]["same_case"] is True and by[pb]["case_id"] == b
    assert by[pa]["scope"] == "other_case" and by[pa]["same_case"] is False and by[pa]["case_id"] == a


def test_experiences_are_labelled_store_memory(env):  # noqa: F811
    from glazed_backend.domain import Experience
    client, c = env
    case_id, pid = approved_decision(client)

    class Mem:
        def recall(self, store_id, query, limit=5):
            return [Experience("rejected", "decision", store_id, pid), Experience("promo", "promo_evaluation", store_id, None, ref="PR1")]
    c.memory = Mem()
    got = client.get("/internal/v1/experiences", headers={"X-Glazed-Case": case_id}, params={"query": "x"}).json()
    assert [(g["scope"], g["case_id"], g["same_case"]) for g in got] == [("store_memory", case_id, True), ("store_memory", None, False)]


def _inject(client, case_id, **event):
    body = {"type": "bloqueo", "date_from": "2026-03-12", "date_to": "2026-03-13", "note": "no llegó el camión", **event}
    r = client.post(f"/api/v1/cases/{case_id}/inject", json={"event": body})
    assert r.status_code == 201, r.text
    return r.json()["event"]


def test_injected_event_links_to_the_given_proposal(env):  # noqa: F811
    client, _ = env
    case_id, pid = approved_decision(client)
    ev = _inject(client, case_id, proposal_id=pid)
    assert ev["proposal_id"] == pid and ev["execution_id"]
    comp = client.get(f"/api/v1/cases/{case_id}/compliance").json()[0]
    assert comp["cause"]["type"] == "bloqueo" and comp["cause"]["note"] == "no llegó el camión"
    assert comp["cause"]["proposal_id"] == pid


def test_injected_event_without_proposal_links_to_the_latest_matching_execution(env):  # noqa: F811
    client, _ = env
    case_id, pid = approved_decision(client)
    ev = _inject(client, case_id, sku="SKU-1")
    assert ev["proposal_id"] == pid and ev["execution_id"]
    ev2 = _inject(client, case_id)  # no sku: the latest execution of the case
    assert ev2["proposal_id"] == pid


def test_event_linked_elsewhere_is_not_the_cause_of_another_decision(env):  # noqa: F811
    client, _ = env
    case_id, pid = approved_decision(client)
    _inject(client, case_id, proposal_id="ghost")  # unknown proposal: the event stays unlinked
    comp = client.get(f"/api/v1/cases/{case_id}/compliance").json()[0]
    assert comp["cause"] is None
    ev = _inject(client, case_id)
    assert ev["proposal_id"] == pid
