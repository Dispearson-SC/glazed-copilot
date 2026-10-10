"""GET /api/v1/cases/{id}/turns: the conversation history with FULL final replies (not rebuilt from /trace)."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from glazed_backend.adapters.driving.app import Container, create_app
from tests.fakes import (FakeClock, FakeCore, FakeMetrics, InMemoryAlerts, InMemoryBacktests, InMemoryCases,
                         InMemoryExecutions, InMemoryProposals, InMemoryTrace)


@pytest.fixture
def env():
    c = Container(metrics=FakeMetrics(), core=FakeCore(), cases=InMemoryCases(), alerts=InMemoryAlerts(),
                  proposals=InMemoryProposals(), executions=InMemoryExecutions(), backtests=InMemoryBacktests(),
                  trace=InMemoryTrace(), clock=FakeClock())
    return TestClient(create_app(c)), c


def mkcase(client):
    return client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": "2026-03-10"}).json()["case_id"]


def ask(client, c, case_id, text, reply=None, status="finished"):
    """Send a message; script what Core will answer for the turn. Each message is one minute after the last."""
    c.clock._now += timedelta(minutes=1)
    tid = client.post(f"/api/v1/cases/{case_id}/messages", json={"text": text}).json()["turn_id"]
    c.core.turns[tid] = {"turn_id": tid, "status": status, "text": reply}
    return tid


def test_history_is_empty_for_a_new_case_and_404_for_an_unknown_one(env):
    client, _ = env
    assert client.get(f"/api/v1/cases/{mkcase(client)}/turns").json() == []
    assert client.get("/api/v1/cases/nope/turns").status_code == 404


def test_turns_come_back_ordered_by_ts_with_the_full_reply_not_clipped(env):
    client, c = env
    cid = mkcase(client)
    long_reply = "Venta del día. " * 400  # ~6,000 chars: well past the 2,000 the trace clips at
    t1 = ask(client, c, cid, "primera", long_reply)
    t2 = ask(client, c, cid, "segunda", "corta")
    client.get(f"/api/v1/cases/{cid}/turns/{t1}"), client.get(f"/api/v1/cases/{cid}/turns/{t2}")
    out = client.get(f"/api/v1/cases/{cid}/turns").json()
    assert [t["turn_id"] for t in out] == [t1, t2]
    assert out[0]["user_text"] == "primera" and out[0]["reply"] == long_reply and len(out[0]["reply"]) > 2000
    assert out[0]["status"] == "done" and out[0]["ts"] < out[1]["ts"]
    assert "reply_meta" not in out[0]


def test_reply_goes_through_the_reply_sanitizer(env):
    client, c = env
    cid = mkcase(client)
    t = ask(client, c, cid, "q", "Compra 12 unidades 订单 hoy.")
    client.get(f"/api/v1/cases/{cid}/turns/{t}")
    (turn,) = client.get(f"/api/v1/cases/{cid}/turns").json()
    assert turn["reply"] == "Compra 12 unidades hoy."


def test_history_resolves_turns_nobody_polled(env):
    client, c = env
    cid = mkcase(client)
    t = ask(client, c, cid, "q", "respuesta")
    (turn,) = client.get(f"/api/v1/cases/{cid}/turns").json()  # no GET /turns/{id} in between
    assert turn["turn_id"] == t and turn["reply"] == "respuesta" and turn["status"] == "done"


def test_running_turns_have_a_null_reply_and_their_status(env):
    client, c = env
    cid = mkcase(client)
    t = ask(client, c, cid, "q", None, status="running")
    (turn,) = client.get(f"/api/v1/cases/{cid}/turns").json()
    assert turn["turn_id"] == t and turn["reply"] is None and turn["status"] == "pending"
    c.core.turns[t] = {"turn_id": t, "status": "finished", "text": "ya"}
    assert client.get(f"/api/v1/cases/{cid}/turns").json()[0]["reply"] == "ya"


def test_failed_turns_keep_their_status_and_no_reply(env):
    client, c = env
    cid = mkcase(client)
    ask(client, c, cid, "q", "boom", status="failed")
    (turn,) = client.get(f"/api/v1/cases/{cid}/turns").json()
    assert turn["status"] == "failed" and turn["reply"] is None and turn["error"] == "boom"


def test_the_final_reply_is_persisted_so_history_survives_core_forgetting_it(env):
    client, c = env
    cid = mkcase(client)
    ask(client, c, cid, "q", "guardada")
    client.get(f"/api/v1/cases/{cid}/turns")
    c.core.turns.clear()
    assert client.get(f"/api/v1/cases/{cid}/turns").json()[0]["reply"] == "guardada"


def test_drafts_and_tool_or_peer_results_never_appear(env):
    client, c = env
    cid = mkcase(client)
    t = ask(client, c, cid, "q", "final")
    c.core.transcript = [
        {"entry_id": "e1", "turn_id": t, "kind": "user_message", "at": "2026-10-10T15:01:00+00:00", "payload": {"content": "q"}},
        {"entry_id": "e2", "turn_id": t, "kind": "agent_message", "at": "2026-10-10T15:01:01+00:00", "payload": {"content": "borrador"}},
        {"entry_id": "e3", "turn_id": t, "kind": "tool_result", "at": "2026-10-10T15:01:02+00:00",
         "payload": {"tool": "x", "result": "<untrusted-tool-output>secreto</untrusted-tool-output>"}},
        {"entry_id": "e4", "turn_id": t, "kind": "peer_exchange", "at": "2026-10-10T15:01:03+00:00",
         "payload": {"target_agent_id": "supply", "question": "q", "answer": "<untrusted-tool-output>peer</untrusted-tool-output>"}}]
    raw = client.get(f"/api/v1/cases/{cid}/turns").text
    assert "borrador" not in raw and "untrusted-tool-output" not in raw and "secreto" not in raw
    assert len(client.get(f"/api/v1/cases/{cid}/turns").json()) == 1


def test_turns_that_only_exist_in_the_core_transcript_are_backfilled(env):
    client, c = env
    cid = mkcase(client)
    case = c.cases.get(cid)
    case.core_conversation_id = cid
    c.cases.update(case)
    c.core.turns["old1"] = {"turn_id": "old1", "status": "finished", "text": "vieja"}
    c.core.transcript = [{"entry_id": "e1", "turn_id": "old1", "kind": "user_message",
                          "at": "2026-03-09T10:00:00+00:00", "payload": {"content": "pregunta vieja"}},
                         {"entry_id": "e2", "turn_id": "old1", "kind": "agent_message",
                          "at": "2026-03-09T10:00:05+00:00", "payload": {"content": "borrador"}}]
    (turn,) = client.get(f"/api/v1/cases/{cid}/turns").json()
    assert turn == {"turn_id": "old1", "ts": turn["ts"], "user_text": "pregunta vieja", "reply": "vieja", "status": "done"}
    assert turn["ts"].startswith("2026-03-09T10:00:00")


def test_trace_message_events_carry_the_turn_id(env):
    client, c = env
    cid = mkcase(client)
    case = c.cases.get(cid)
    case.core_conversation_id = cid
    c.cases.update(case)
    c.core.transcript = [{"entry_id": "e1", "turn_id": "tA", "kind": "user_message", "at": "2026-03-09T10:00:00+00:00",
                          "payload": {"content": "hola"}},
                         {"entry_id": "e2", "turn_id": "tA", "kind": "tool_call", "at": "2026-03-09T10:00:01+00:00",
                          "payload": {"tool": "kpis", "arguments": {}}}]
    events = client.get("/api/v1/trace", params={"case_id": cid}).json()
    assert [e["payload"]["turn_id"] for e in events] == ["tA", "tA"]


def test_a_stored_envelope_user_text_is_shown_as_plain_text(env):
    """Rows back-filled before the envelope fix hold the serialized envelope; history shows its content."""
    import json
    from datetime import datetime, timezone

    from glazed_backend.domain.models import TurnRecord

    client, c = env
    cid = mkcase(client)
    env_text = json.dumps({"kind": "request", "parts": [{"content": "¿Qué pido hoy?"}]})
    c.turns.add(TurnRecord("t-old", cid, "S030", datetime(2026, 3, 9, tzinfo=timezone.utc), env_text))
    (turn,) = client.get(f"/api/v1/cases/{cid}/turns").json()
    assert turn["user_text"] == "¿Qué pido hoy?"
