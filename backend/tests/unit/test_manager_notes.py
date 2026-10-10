"""P1: manager notes become a memory, a Backboard experience and an operational event, written by code."""
from datetime import date

from glazed_backend.adapters.driven.memory import InMemoryExperienceMemory
from glazed_backend.application.sentinel import CheckCompliance
from tests.unit.manager_support import AS_OF, build


class DownMemory:
    def remember(self, store_id, exp):
        raise RuntimeError("backboard down")

    def recall(self, store_id, query, limit=5):
        raise RuntimeError("backboard down")


def env(memory=None):
    client, cid, _ = build()
    client.container.memory = memory if memory is not None else InMemoryExperienceMemory()
    return client, cid, {"X-Glazed-Case": cid}


def test_note_is_saved_as_memory_experience_and_event():
    client, cid, h = env()
    r = client.post("/internal/v1/notes", json={"text": "  Hoy se venderá menos: cierran la calle  "}, headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["saved"] is True and body["category"] == "eventos"
    assert body["date_from"] == body["date_to"] == AS_OF.isoformat()
    (m,) = [x for x in client.get(f"/api/v1/cases/{cid}/memories").json() if x["memory_id"] == body["memory_id"]]
    assert m["source"] == "gerente" and m["verified"] is True and m["category"] == "eventos"
    assert m["text"] == "Hoy se venderá menos: cierran la calle" and m["created_at"].startswith(AS_OF.isoformat())
    assert len([x for x in client.get(f"/api/v1/cases/{cid}/memories").json()]) == 1  # Backboard copy is not duplicated
    (e,) = client.container.trace.list(case_id=cid)
    assert e.payload["type"] == "nota_gerente" and e.event_id == body["event_id"]
    exp = client.get("/internal/v1/experiences", params={"query": "calle"}, headers=h).json()
    assert len(exp) == 1 and exp[0]["kind"] == "note" and "cierran la calle" in exp[0]["text"]


def test_note_is_in_the_briefing_only_inside_its_range_and_cited_by_compliance_events():
    client, cid, h = env()
    client.post("/internal/v1/notes", json={"text": "Feria en la plaza", "date_from": "2026-07-19", "date_to": "2026-07-21"}, headers=h)
    client.post("/internal/v1/notes", json={"text": "Obra pasada", "date_from": "2026-07-01", "date_to": "2026-07-02"}, headers=h)
    client.post("/internal/v1/notes", json={"text": "Obra futura", "date_from": "2026-07-25", "date_to": "2026-07-26"}, headers=h)
    for url in (f"/api/v1/cases/{cid}/briefing", "/internal/v1/briefing"):
        b = client.get(url, headers=h).json()
        assert [n["text"] for n in b["manager_notes"]] == ["Feria en la plaza"], url
        assert [n["text"] for n in b["snapshot"]["manager_notes"]] == ["Feria en la plaza"]
    c = client.container
    ev = CheckCompliance(c.cases, c.proposals, c.executions, c.metrics, c.trace, c.outcomes).events("S030")
    assert {e["type"] for e in ev} == {"nota_gerente"} and len(ev) == 3


def test_validation_and_resilience():
    client, cid, h = env(DownMemory())
    assert client.post("/internal/v1/notes", json={"text": "   "}, headers=h).status_code == 400
    assert client.post("/internal/v1/notes", json={"text": "x" * 501}, headers=h).status_code == 400
    assert client.post("/internal/v1/notes", json={"text": "ok", "category": "otra"}, headers=h).status_code == 400
    assert client.post("/internal/v1/notes", json={"text": "ok", "date_from": "2026-07-20", "date_to": "2026-07-19"}, headers=h).status_code == 400
    ok = client.post(f"/api/v1/cases/{cid}/notes", json={"text": "Llueve", "category": "demanda", "impact": "menos_venta"})
    assert ok.status_code == 201 and ok.json()["category"] == "demanda"  # Backboard down: still saved locally
    assert [m["text"] for m in client.get(f"/api/v1/cases/{cid}/memories", params={"category": "demanda"}).json()] == ["Llueve"]
    assert client.get("/internal/v1/experiences", headers=h).json()[0]["kind"] == "note"


def test_backboard_copy_without_metadata_is_not_listed_twice():
    mem = InMemoryExperienceMemory()
    client, cid, h = env(mem)
    client.post("/internal/v1/notes", json={"text": "Llueve fuerte"}, headers=h)
    (exp,) = mem.recall("S030", "")
    from glazed_backend.domain import Experience
    mem._d["S030"] = [Experience(exp.text, "memory", "S030")]  # what Backboard returns: kind and ref are lost
    assert [m["text"] for m in client.get(f"/api/v1/cases/{cid}/memories").json()] == ["Llueve fuerte"]
