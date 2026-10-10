"""C8: GET /cases/{id}/turns/{turn} reports which specialists the orchestrator is consulting."""
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
    client = TestClient(create_app(c))
    cid = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": "2026-03-10"}).json()["case_id"]
    return client, c, cid


def start(client, c, cid, status="running"):
    tid = client.post(f"/api/v1/cases/{cid}/messages", json={"text": "q"}).json()["turn_id"]
    c.core.turns[tid] = {"turn_id": tid, "status": status, "text": "listo"}
    return tid


def entry(i, tid, kind, payload):
    return {"entry_id": f"e{i}", "turn_id": tid, "kind": kind, "at": f"2026-10-10T15:01:{i:02d}+00:00", "payload": payload}


def progress(client, cid, tid):
    return client.get(f"/api/v1/cases/{cid}/turns/{tid}").json().get("progress")


def test_no_peer_asks_means_empty_progress(env):
    client, c, cid = env
    tid = start(client, c, cid)
    assert progress(client, cid, tid) == []


def test_ask_without_answer_is_consulting_and_answered_is_done(env):
    client, c, cid = env
    tid = start(client, c, cid)
    c.core.transcript = [
        entry(1, tid, "tool_call", {"tool": "ask_peer", "arguments": {"target": "glazed_supply", "question": "x"}}),
        entry(2, tid, "peer_exchange", {"target_agent_id": "glazed_supply", "hop": 1, "question": "x"}),
        entry(3, tid, "tool_call", {"tool": "ask_peer", "arguments": {"target": "glazed_present", "question": "y"}}),
        entry(4, tid, "peer_exchange", {"target_agent_id": "glazed_present", "hop": 1, "question": "y", "answer": "ok", "state": "answered"})]
    assert progress(client, cid, tid) == [
        {"agent_id": "supply", "display_name_es": "Analista de abastecimiento", "state": "consulting"},
        {"agent_id": "present", "display_name_es": "Analista del presente", "state": "done"}]


def test_a_tool_call_alone_is_consulting_and_later_answer_flips_it(env):
    client, c, cid = env
    tid = start(client, c, cid)
    c.core.transcript = [entry(1, tid, "tool_call", {"tool": "ask_peer", "arguments": {"target_agent_id": "glazed_past"}})]
    assert progress(client, cid, tid) == [{"agent_id": "past", "display_name_es": "Analista histórico", "state": "consulting"}]
    c.core.transcript.append(entry(2, tid, "peer_exchange", {"target_agent_id": "glazed_past", "answer": "hecho"}))
    assert progress(client, cid, tid)[0]["state"] == "done"


def test_other_turns_are_ignored_and_a_repeated_target_appears_once(env):
    client, c, cid = env
    tid = start(client, c, cid)
    c.core.transcript = [
        entry(1, "other-turn", "peer_exchange", {"target_agent_id": "glazed_strategist", "answer": "x"}),
        entry(2, tid, "peer_exchange", {"target_agent_id": "glazed_supply", "hop": 1, "answer": "a"}),
        entry(3, tid, "peer_exchange", {"target_agent_id": "glazed_supply", "hop": 2, "question": "b"})]
    assert progress(client, cid, tid) == [{"agent_id": "supply", "display_name_es": "Analista de abastecimiento", "state": "consulting"}]


def test_a_finished_turn_closes_every_consultation_and_keeps_it_on_re_read(env):
    client, c, cid = env
    tid = start(client, c, cid, status="finished")
    c.core.transcript = [entry(1, tid, "peer_exchange", {"target_agent_id": "glazed_auditor", "question": "q"})]
    out = client.get(f"/api/v1/cases/{cid}/turns/{tid}").json()
    assert out["status"] == "done" and out["progress"] == [
        {"agent_id": "sentinel", "display_name_es": "Centinela", "state": "done"}]
    c.core.transcript = []
    assert progress(client, cid, tid)[0]["agent_id"] == "sentinel"  # the auditor is shown as Centinela; stored with the finished turn


def test_a_transcript_failure_does_not_break_the_poll(env):
    client, c, cid = env
    tid = start(client, c, cid)
    c.core.list_transcript = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down"))
    out = client.get(f"/api/v1/cases/{cid}/turns/{tid}").json()
    assert out["status"] == "pending" and out["progress"] == []
