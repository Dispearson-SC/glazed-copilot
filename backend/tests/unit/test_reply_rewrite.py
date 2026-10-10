"""Q3: a contaminated final reply gets ONE rewrite request in the same conversation; the better answer wins."""
from datetime import date, timedelta

import pytest

from glazed_backend.adapters.driven.memory import InMemoryTurns
from glazed_backend.application import AskAgent, GetTurn, ListTurns, StartCase, TurnTracker
from tests.fakes import FakeClock, FakeCore, InMemoryCases

DIRTY = "No tengo acceso a los archivos, necesito que me pases los datos reales. Vendimos 12."
CLEAN = "Vendimos 12 cajas hoy."


@pytest.fixture
def env():
    class E: ...
    e = E()
    e.cases, e.core, e.clock, e.turns, e.tracker = InMemoryCases(), FakeCore(), FakeClock(), InMemoryTurns(), TurnTracker()
    e.ask = AskAgent(e.cases, e.core, e.tracker, e.clock, e.turns)
    e.get = GetTurn(e.cases, e.core, e.tracker, e.clock, turns=e.turns)
    e.case = StartCase(e.cases).execute(store_id="S030", sim_today=date(2026, 3, 10))
    e.tid = e.ask.execute(e.case.case_id, "hola")
    e.core.turns[e.tid] = {"turn_id": e.tid, "status": "finished", "text": DIRTY}
    return e


def test_clean_reply_is_not_rewritten_but_records_sanitized_meta(env):
    env.core.turns[env.tid]["text"] = CLEAN
    out = env.get.execute(env.case.case_id, env.tid)
    assert out["status"] == "done" and out["reply"] == CLEAN and "reply_meta" not in out
    assert len(env.core.sent) == 1
    assert env.turns.get(env.tid).reply_meta == {"sanitized": True}


def test_contaminated_reply_asks_the_core_once_in_the_same_conversation(env):
    out = env.get.execute(env.case.case_id, env.tid)
    assert out["status"] == "pending" and out["rewriting"] is True
    assert len(env.core.sent) == 2
    conv, store, text = env.core.sent[1]
    assert conv == env.cases.get(env.case.case_id).core_conversation_id and store == "S030"
    assert "Rewrite your previous answer" in text and "no drafts" in text
    env.get.execute(env.case.case_id, env.tid)  # polling again never sends another rewrite
    assert len(env.core.sent) == 2


def test_the_cleaner_rewrite_replaces_the_reply(env):
    env.get.execute(env.case.case_id, env.tid)
    env.core.turns["turn-2"] = {"turn_id": "turn-2", "status": "finished", "text": CLEAN}
    out = env.get.execute(env.case.case_id, env.tid)
    assert out["status"] == "done" and out["reply"] == CLEAN and out["reply_meta"]["rewritten"] is True
    meta = env.turns.get(env.tid).reply_meta
    assert meta["rewritten"] is True and meta["sanitized"] is True
    assert len(env.core.sent) == 2
    assert env.get.execute(env.case.case_id, env.tid)["reply"] == CLEAN  # final: stable and no new rewrite
    assert len(env.core.sent) == 2


def test_a_worse_rewrite_keeps_the_original(env):
    env.get.execute(env.case.case_id, env.tid)
    worse = DIRTY + " " + DIRTY
    env.core.turns["turn-2"] = {"turn_id": "turn-2", "status": "finished", "text": worse + "\n\n## A\n## A"}
    out = env.get.execute(env.case.case_id, env.tid)
    assert out["status"] == "done" and out["reply"].startswith("No tengo acceso") and "rewritten" not in out.get("reply_meta", {})
    assert env.turns.get(env.tid).reply_meta["sanitized"] is True
    assert env.turns.get(env.tid).reply_meta["rewritten"] is False


def test_failed_or_stuck_rewrite_falls_back_to_the_original(env):
    env.get.execute(env.case.case_id, env.tid)
    env.core.turns["turn-2"] = {"turn_id": "turn-2", "status": "running", "text": None}
    assert env.get.execute(env.case.case_id, env.tid)["status"] == "pending"
    env.clock._now += timedelta(seconds=400)
    out = env.get.execute(env.case.case_id, env.tid)
    assert out["status"] == "done" and out["reply"].startswith("No tengo acceso")
    assert len(env.core.sent) == 2


def test_the_rewrite_request_never_shows_up_in_the_history(env):
    env.get.execute(env.case.case_id, env.tid)
    env.core.turns["turn-2"] = {"turn_id": "turn-2", "status": "finished", "text": CLEAN}
    from glazed_backend.application import ListTurns
    env.core.transcript = [
        {"entry_id": "a", "turn_id": env.tid, "kind": "user_message", "at": "2026-03-10T10:00:00+00:00", "payload": {"text": "hola"}},
        {"entry_id": "b", "turn_id": "turn-2", "kind": "user_message", "at": "2026-03-10T10:01:00+00:00",
         "payload": {"text": env.core.sent[1][2]}}]
    items = ListTurns(env.cases, env.core, env.turns, env.get, env.tracker).execute(env.case.case_id)
    assert [i["turn_id"] for i in items] == [env.tid]
    assert items[0]["reply"] == CLEAN and items[0]["reply_meta"]["rewritten"] is True
