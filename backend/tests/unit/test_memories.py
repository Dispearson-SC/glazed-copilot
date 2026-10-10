"""C9: GET /cases/{id}/memories from the decision log, Backboard experiences and stored rejection reasons."""
from datetime import timedelta

from glazed_backend.adapters.driven.memory import InMemoryExperienceMemory
from glazed_backend.domain import Experience
from tests.unit.copilot_support import stockout_issue, with_issues

IID = "S030|stockout_risk|A"


class Jev:
    def classify(self, kind, text):
        from glazed_backend.ports.classifier import Classification
        return Classification("falla_proveedor" if "proveedor" in text else "precio", 0.9, "stub", True, "stub")


def env(*issues):
    client, cid, m = with_issues(*(issues or (stockout_issue("A"),)))
    client.container.memory = InMemoryExperienceMemory()
    client.container.classifier = Jev()
    client.container.metrics.catalog = {s: {"product_name": f"Prod {s}", "department": "x", "unit_cost": 1.0, "price": 2.0,
                                           "shelf_life_days": None, "supplier_id": "SUP01"} for s in "AB"}
    return client, cid


def decide(client, cid, approved, reason="", iid=IID, oid="bestA", key=None):
    r = client.post(f"/api/v1/cases/{cid}/decisions", json={"issue_id": iid, "option_id": oid, "approved": approved, "reason": reason},
                    headers={"Idempotency-Key": key or f"{iid}{oid}{approved}"})
    assert r.status_code in (200, 201), r.text
    return r.json()


def memories(client, cid, **params):
    r = client.get(f"/api/v1/cases/{cid}/memories", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_rejection_with_reason_creates_a_preferencias_memory():
    client, cid = env()
    d = decide(client, cid, False, "Este proveedor nunca llega a tiempo")
    assert d["reason_category"] == "falla_proveedor"
    (m,) = [x for x in memories(client, cid) if x["source"] == "rejection_reason"]
    assert m["category"] == "preferencias" and "Este proveedor nunca llega a tiempo" in m["text"]
    assert m["text"].startswith("Rechazaste") and "Prod A" in m["text"]
    assert m["verified"] is False and m["new"] is True and m["cases_count"] == 1 and m["created_at"] and m["memory_id"]


def test_legacy_decision_route_also_creates_it():
    client, cid = env()
    p = client.post("/api/v1/proposals", json={"case_id": cid, "issue_id": IID, "option_id": "bestA"}).json()
    client.post(f"/api/v1/proposals/{p['proposal_id']}/decision", json={"approved": False, "reason": "muy caro"})
    assert [m["category"] for m in memories(client, cid) if m["source"] == "rejection_reason"] == ["preferencias"]


def test_approved_decision_comes_from_the_decision_log_and_is_not_duplicated_by_backboard():
    client, cid = env()
    decide(client, cid, True)
    out = memories(client, cid)
    log = [m for m in out if m["source"] == "decision_log"]
    assert len(log) == 1 and log[0]["category"] == "proveedores" and log[0]["verified"] is True
    assert log[0]["text"].startswith("Aprobaste") and "Prod A" in log[0]["text"]
    assert not [m for m in out if m["source"] == "backboard"]  # the experience written for this decision is the same fact


def test_backboard_experiences_without_a_local_decision_are_listed():
    client, cid = env()
    client.container.memory.remember("S030", Experience("[S030 · promo · PR002 · 2026-07-01] promo audit: block", "promo_evaluation",
                                                        "S030", ref="PR002"))
    (m,) = memories(client, cid)
    assert m["source"] == "backboard" and m["category"] == "demanda" and m["verified"] is False and "PR002" in m["text"]


def test_category_filter_text_search_and_validation():
    client, cid = env(stockout_issue("A"), stockout_issue("B"))
    decide(client, cid, True, iid="S030|stockout_risk|A", oid="bestA")
    decide(client, cid, False, "muy caro", iid="S030|stockout_risk|B", oid="bestB")
    assert {m["category"] for m in memories(client, cid, category="preferencias")} == {"preferencias"}
    assert [m["category"] for m in memories(client, cid, category="proveedores")] == ["proveedores"]
    assert memories(client, cid, category="eventos") == []
    assert len(memories(client, cid, q="MUY CARO")) == 1 and len(memories(client, cid)) == 2
    assert client.get(f"/api/v1/cases/{cid}/memories", params={"category": "otra"}).status_code == 400


def test_cases_count_spans_the_cases_of_the_store():
    client, cid = env(stockout_issue("A"))
    other = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": "2026-07-19"}).json()["case_id"]
    decide(client, cid, False, "muy caro")
    decide(client, other, False, "demasiado caro", key="other")
    mine = [m for m in memories(client, cid) if m["source"] == "rejection_reason"]
    assert len(mine) == 2 and {m["cases_count"] for m in mine} == {2}


def test_memories_from_a_later_case_are_not_shown_to_an_earlier_one():
    client, cid = env(stockout_issue("A"))
    later = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": "2026-07-25"}).json()["case_id"]
    client.container.metrics.issues_by_date[__import__("datetime").date(2026, 7, 25)] = [stockout_issue("A")]
    decide(client, later, False, "muy caro")
    assert memories(client, cid) == [] and len(memories(client, later)) == 1


def test_new_flag_expires_after_a_day():
    client, cid = env()
    decide(client, cid, False, "muy caro")
    client.container.clock._now += timedelta(days=2)
    assert memories(client, cid)[0]["new"] is False
