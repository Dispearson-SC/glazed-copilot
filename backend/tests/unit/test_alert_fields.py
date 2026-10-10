"""C10: alerts carry category, agent_id and ts."""
import pytest

from glazed_backend.domain import Alert
from tests.unit.copilot_support import stockout_issue, with_issues


@pytest.mark.parametrize("kind,category,agent", [
    ("stockout_risk", "operacion", "supply"), ("late_delivery", "operacion", "supply"), ("inflated_order", "operacion", "supply"),
    ("overstock_waste", "operacion", "present"), ("expiring", "operacion", "present"), ("calendar_uplift", "operacion", "present"),
    ("misleading_promo", "operacion", "strategist"),
    ("sku_key_mismatch", "integridad", "auditor"), ("orphan_sku", "integridad", "auditor"),
    ("compliance_deviation", "automatica", "sentinel"),
    ("something_new", "operacion", "orchestrator")])
def test_category_and_owning_agent_by_detector(kind, category, agent):
    client, cid, _ = with_issues()
    c = client.container
    issue = stockout_issue("A", kind=kind)
    if category == "integridad":
        issue["category"] = "integrity"
    c.alerts.add(Alert.new(2, "S030", cid, 10.0, issue, issue["issue_id"], __import__("datetime").date(2026, 7, 19)))
    (a,) = client.get("/api/v1/alerts").json()
    assert (a["category"], a["agent_id"]) == (category, agent)
    assert a["ts"] == a["created_at"] and a["ts"].startswith("20")
    assert a["state"] == "nueva" and a["store_display_name"]


def test_patched_alert_keeps_the_fields():
    client, cid, _ = with_issues()
    issue = stockout_issue("A")
    client.container.alerts.add(Alert.new(2, "S030", cid, 10.0, issue, issue["issue_id"], __import__("datetime").date(2026, 7, 19)))
    a = client.get("/api/v1/alerts").json()[0]
    out = client.patch(f"/api/v1/alerts/{a['alert_id']}", json={"state": "vista"}).json()
    assert out["category"] == "operacion" and out["agent_id"] == "supply" and out["ts"]
