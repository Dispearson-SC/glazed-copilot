"""C3: GET /cases/{id}/decisions/pending."""
from tests.unit.copilot_support import plan_line, stockout_issue, with_issues

WARN = {"min_order_value": 300.0, "order_value_usd": 106.1, "suggestion": "Below the supplier minimum"}


def overstock(sku, tier="N2", net=40.0):
    iss = stockout_issue(sku, kind="overstock_waste", severity=60.0, tier=tier)
    iss["options"][0].update(action_type="skip_order", net_usd_mid=net, params={"sku": sku, "supplier_id": "SUP01"})
    return iss


def pending(client, cid):
    r = client.get(f"/api/v1/cases/{cid}/decisions/pending")
    assert r.status_code == 200, r.text
    return r.json()


def test_envelope_and_split_between_approvals_and_technical():
    reorder = stockout_issue("R1")
    over = overstock("O1")
    n1 = stockout_issue("N1X", tier="N1")
    n1["options"][0]["tier"] = "N1"
    def conf(m):
        m.plan = {"suppliers": [], "lines": [plan_line("R1", reorder)]}
    client, cid, _ = with_issues(reorder, over, n1, configure=conf)
    out = pending(client, cid)
    assert out["as_of"] == "2026-07-19" and out["store_id"] == "S030" and out["source"] and out["store_display_name"]
    ids = [a["issue_id"] for a in out["approvals"]]
    assert "S030|overstock_waste|O1" in ids and "S030|stockout_risk|R1" not in ids  # a plan line is a technical item
    a = next(a for a in out["approvals"] if a["issue_id"].endswith("|O1"))
    assert a["tier"] == "N2" and a["recommendation"]["action_type"] == "skip_order" and a["impact_usd"]["mid"] == 40.0
    assert [t["sku"] for t in out["technical"]] == ["R1", "N1X"]  # plan lines first, then N1 options
    t = out["technical"][0]
    assert t["sku"] == "R1" and t["product_name"] == "Prod R1" and t["supplier_name"] == "Northfield Bakery"
    assert t["qty"] == 20 and t["expected_delivery"] == "2026-07-21" and t["issue_id"] == "S030|stockout_risk|R1"
    assert t["option_id"] == "bestR1" and t["deadline"] == "2026-07-19" and t["confidence"] == 0.82
    assert t["cost_usd"]["mid"] == 30.0 and t["cost_usd"]["low"] < 30.0 < t["cost_usd"]["high"]
    assert t["why"] and t["impact_chips"] and all(isinstance(c, str) for c in t["impact_chips"]) and "warning" not in t


def test_n1_issue_outside_the_plan_is_technical_and_integrity_is_never_an_approval():
    n1 = stockout_issue("N1X", tier="N1")
    integ = stockout_issue("I1", kind="sku_key_mismatch")
    integ["category"] = "integrity"
    client, cid, _ = with_issues(n1, integ)
    out = pending(client, cid)
    assert out["approvals"] == []
    assert [t["issue_id"] for t in out["technical"]] == ["S030|stockout_risk|N1X"]


def test_warnings_below_minimum_and_deadline_passed_are_warnings_not_blocks():
    a, b = stockout_issue("W1"), stockout_issue("W2")
    def conf(m):
        m.plan = {"suppliers": [], "lines": [plan_line("W1", a, warn=WARN), plan_line("W2", b, status="deadline_passed")]}
    client, cid, _ = with_issues(a, b, configure=conf)
    by = {t["sku"]: t for t in pending(client, cid)["technical"]}
    assert "mínimo" in by["W1"]["warning"] and "$106" in by["W1"]["warning"] and "$300" in by["W1"]["warning"]
    assert "fecha límite" in by["W2"]["warning"] and by["W2"]["deadline"] is None
    assert by["W1"]["option_id"] and by["W2"]["option_id"]  # still decidable


def test_items_already_decided_in_this_case_are_excluded():
    reorder, over = stockout_issue("R1"), overstock("O1")
    def conf(m):
        m.plan = {"suppliers": [], "lines": [plan_line("R1", reorder)]}
    client, cid, _ = with_issues(reorder, over, configure=conf)
    for iid, oid, ok in (("S030|stockout_risk|R1", "bestR1", True), ("S030|overstock_waste|O1", "bestO1", False)):
        p = client.post("/api/v1/proposals", json={"case_id": cid, "issue_id": iid, "option_id": oid}).json()
        client.post(f"/api/v1/proposals/{p['proposal_id']}/decision", json={"approved": ok, "reason": "" if ok else "no"})
    out = pending(client, cid)
    assert out["approvals"] == [] and out["technical"] == []


def test_a_pending_proposal_does_not_hide_the_item():
    over = overstock("O1")
    client, cid, _ = with_issues(over)
    client.post("/api/v1/proposals", json={"case_id": cid, "issue_id": over["issue_id"], "option_id": "bestO1"})
    assert len(pending(client, cid)["approvals"]) == 1


def test_do_nothing_winner_is_not_an_approval():
    iss = overstock("O2")
    iss["options"][0]["net_usd_mid"] = -3.0
    client, cid, _ = with_issues(iss)
    assert pending(client, cid)["approvals"] == []
