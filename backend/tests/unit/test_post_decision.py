"""C4: POST /cases/{id}/decisions creates the proposal and records the decision in one call."""
from tests.unit.copilot_support import stockout_issue, with_issues

IID = "S030|stockout_risk|A"


def post(client, cid, key=None, **body):
    h = {"Idempotency-Key": key} if key else {}
    return client.post(f"/api/v1/cases/{cid}/decisions", json=body, headers=h)


def test_approve_creates_proposal_and_decision_atomically():
    client, cid, _ = with_issues(stockout_issue("A"))
    r = post(client, cid, "k1", issue_id=IID, option_id="bestA", approved=True)
    assert r.status_code == 201
    out = r.json()
    assert out["status"] == "approved" and out["decision_id"] == out["proposal_id"]
    (p,) = client.get(f"/api/v1/proposals?case_id={cid}").json()
    assert p["status"] == "approved" and p["issue_id"] == IID and p["params"]["option_id"] == "bestA"
    assert p["action_type"] == "place_order" and p["tier"] == "N2"  # copied from the option, never from the caller
    log = client.get(f"/api/v1/cases/{cid}/decisions").json()
    assert any(row["kind"] == "decision" and row["decision_id"] == out["proposal_id"] for row in log)


def test_reject_with_reason_and_label():
    client, cid, _ = with_issues(stockout_issue("A"))
    r = post(client, cid, "k2", issue_id=IID, option_id="bestA", approved=False, reason="El proveedor siempre llega tarde")
    assert r.status_code == 201 and r.json()["status"] == "rejected"
    (p,) = client.get(f"/api/v1/proposals?case_id={cid}").json()
    assert p["status"] == "rejected" and p["reason"] == "El proveedor siempre llega tarde"


def test_reject_without_reason_is_400_and_creates_nothing():
    client, cid, _ = with_issues(stockout_issue("A"))
    assert post(client, cid, "k3", issue_id=IID, option_id="bestA", approved=False).status_code == 400
    assert client.get(f"/api/v1/proposals?case_id={cid}").json() == []


def test_unknown_issue_404_unknown_option_400_nothing_created():
    client, cid, _ = with_issues(stockout_issue("A"))
    assert post(client, cid, issue_id="S030|stockout_risk|NO", option_id="x", approved=True).status_code == 404
    assert post(client, cid, issue_id=IID, option_id="zz", approved=True).status_code == 400
    assert client.get(f"/api/v1/proposals?case_id={cid}").json() == []


def test_same_idempotency_key_replays_the_original_and_never_decides_twice():
    client, cid, _ = with_issues(stockout_issue("A"))
    first = post(client, cid, "same", issue_id=IID, option_id="bestA", approved=True).json()
    again = post(client, cid, "same", issue_id=IID, option_id="bestA", approved=False, reason="cambié de opinión")
    assert again.status_code == 200 and again.json()["proposal_id"] == first["proposal_id"]
    assert again.json()["status"] == "approved"
    assert len(client.get(f"/api/v1/proposals?case_id={cid}").json()) == 1
    assert len(client.container.executions.list(cid)) == 1


def test_an_agent_proposal_for_the_same_option_is_reused_not_duplicated():
    client, cid, _ = with_issues(stockout_issue("A"))
    prop = client.post("/api/v1/proposals", json={"case_id": cid, "issue_id": IID, "option_id": "bestA"}).json()
    out = post(client, cid, "k9", issue_id=IID, option_id="bestA", approved=True).json()
    assert out["proposal_id"] == prop["proposal_id"]
    assert len(client.get(f"/api/v1/proposals?case_id={cid}").json()) == 1


def test_deciding_an_already_decided_issue_without_a_key_is_a_409_style_error():
    client, cid, _ = with_issues(stockout_issue("A"))
    post(client, cid, issue_id=IID, option_id="bestA", approved=True)
    r = post(client, cid, issue_id=IID, option_id="bestA", approved=True)
    assert r.status_code == 409
