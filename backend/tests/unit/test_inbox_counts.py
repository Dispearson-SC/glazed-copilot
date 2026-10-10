"""C12: GET /cases/{id}/inbox-counts."""
from datetime import date

from glazed_backend.domain import Alert, AlertState
from tests.unit.copilot_support import plan_line, stockout_issue, with_issues
from tests.unit.test_pending_decisions import overstock


def test_counts_match_the_pending_decisions_and_the_open_alerts_of_the_store_inbox():
    reorder, over = stockout_issue("R1"), overstock("O1")
    def conf(m):
        m.plan = {"suppliers": [], "lines": [plan_line("R1", reorder)]}
    client, cid, _ = with_issues(reorder, over, configure=conf)
    other = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": "2026-07-19"}).json()["case_id"]
    a = Alert.new(2, "S030", cid, 10.0, reorder, "k1", date(2026, 7, 19))
    done = Alert.new(2, "S030", cid, 10.0, over, "k2", date(2026, 7, 19))
    done.state = AlertState.EJECUTADA
    foreign = Alert.new(2, "S030", other, 10.0, over, "k3", date(2026, 7, 19))
    for x in (a, done, foreign):
        client.container.alerts.add(x)
    out = client.get(f"/api/v1/cases/{cid}/inbox-counts").json()
    pend = client.get(f"/api/v1/cases/{cid}/decisions/pending").json()
    assert out == {"approvals": len(pend["approvals"]), "technical": len(pend["technical"]), "alerts": 2}  # the store inbox, as /alerts shows it
    assert out["approvals"] == 1 and out["technical"] == 1


def test_counts_drop_once_decided_and_unknown_case_is_404():
    over = overstock("O1")
    client, cid, _ = with_issues(over)
    assert client.get(f"/api/v1/cases/{cid}/inbox-counts").json()["approvals"] == 1
    client.post(f"/api/v1/cases/{cid}/decisions", json={"issue_id": over["issue_id"], "option_id": "bestO1", "approved": True})
    assert client.get(f"/api/v1/cases/{cid}/inbox-counts").json() == {"approvals": 0, "technical": 0, "alerts": 0}
    assert client.get("/api/v1/cases/nope/inbox-counts").status_code == 404
