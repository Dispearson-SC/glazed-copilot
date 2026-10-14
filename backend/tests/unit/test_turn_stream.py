"""P5: the backend follows a Core turn's SSE feed (`GET /turns/{id}/events`) instead of polling it for its text.

THE RULES UNDER TEST. The stream keeps the ROOT turn's streamed text (snapshot `reply_text`, then `delta` events;
never a peer's) and when the first text arrived; `finished`/`failed` of the root or `end` closes it; an error, a
raise or a stream that closes early marks it broken. While a stream is live, GetTurn answers `pending` with the
cleaned `partial_reply` and `first_text_ms` without asking the Core more often than `core_check_s`; once it finished
GetTurn reads the final reply from `GET /turns/{id}` as before and keeps `first_text_ms` (also on stored reads); a
broken stream, or no stream at all, is plain polling exactly as before.
"""
from __future__ import annotations

from datetime import date, timedelta

import httpx
import pytest

from glazed_backend.adapters.driven.agent_core_http import AgentCoreHttp
from glazed_backend.adapters.driven.memory import InMemoryTurns
from glazed_backend.application import AskAgent, GetTurn, StartCase, TurnTracker
from glazed_backend.application.turn_stream import TurnStreams
from tests.fakes import FakeClock, FakeCore, InMemoryCases


def _snapshot(turn_id: str, reply_text: str = "", state: str = "running") -> dict:
    return {"root_turn_id": turn_id, "turns": [
        {"turn_id": turn_id, "agent": "glazed_orchestrator", "state": state, "reply_text": reply_text},
        {"turn_id": "peer-1", "agent": "glazed_supply", "state": "running", "reply_text": "secreto del par"},
    ]}


class StreamingCore(FakeCore):
    def __init__(self, frames=None, error: Exception | None = None) -> None:
        super().__init__()
        self.frames, self.error, self.gets = list(frames or []), error, 0
        self.streamed: list[tuple[str, str]] = []

    def stream_turn(self, turn_id, store_id):
        self.streamed.append((turn_id, store_id))
        yield from self.frames
        if self.error is not None:
            raise self.error

    def get_turn(self, turn_id, store_id):
        self.gets += 1
        return super().get_turn(turn_id, store_id)


@pytest.fixture
def world():
    class W: ...
    w = W()
    w.cases, w.clock, w.turns, w.tracker = InMemoryCases(), FakeClock(), InMemoryTurns(), TurnTracker()
    w.core = StreamingCore()
    w.streams = TurnStreams(w.core, w.clock, spawn=lambda fn: None)  # tests feed frames by hand
    w.case = StartCase(w.cases).execute(store_id="S030", sim_today=date(2026, 3, 10))
    w.ask = AskAgent(w.cases, w.core, w.tracker, w.clock, w.turns, streams=w.streams)
    w.get = GetTurn(w.cases, w.core, w.tracker, w.clock, turns=w.turns, streams=w.streams, core_check_s=5.0)
    w.tid = w.ask.execute(w.case.case_id, "¿cómo vamos hoy?")
    w.core.turns[w.tid] = {"turn_id": w.tid, "status": "running", "text": None}
    return w


def _later(w, seconds: float) -> None:
    w.clock._now = w.clock._now + timedelta(seconds=seconds)


# ---- the stream itself ----

def test_the_stream_keeps_only_the_root_turns_text_and_when_it_first_arrived():
    clock = FakeClock()
    streams = TurnStreams(None, clock)
    streams.begin("t1")
    streams.feed("t1", "snapshot", _snapshot("t1"))
    assert streams.state("t1").text == "" and streams.state("t1").first_text_at is None
    clock._now = clock._now + timedelta(seconds=2)
    streams.feed("t1", "delta", {"turn_id": "t1", "text": "Hoy "})
    streams.feed("t1", "delta", {"turn_id": "peer-1", "text": "nunca al gerente"})
    streams.feed("t1", "delta", {"turn_id": "t1", "text": "vendiste 12."})
    state = streams.state("t1")
    assert state.text == "Hoy vendiste 12." and state.first_text_at == clock.now() and state.live
    streams.feed("t1", "finished", {"turn_id": "peer-1"})
    assert state.live
    streams.feed("t1", "finished", {"turn_id": "t1"})
    assert state.finished and not state.live


def test_a_reconnect_snapshot_replaces_the_text_and_a_settled_tree_ends_the_stream():
    streams = TurnStreams(None, FakeClock())
    streams.begin("t1")
    streams.feed("t1", "delta", {"turn_id": "t1", "text": "Hoy"})
    streams.feed("t1", "snapshot", _snapshot("t1", "Hoy vendiste"))
    assert streams.state("t1").text == "Hoy vendiste"
    streams.feed("t1", "end", {})
    assert streams.state("t1").finished


@pytest.mark.parametrize("frames, error", [
    ([("snapshot", _snapshot("t1"))], RuntimeError("connection reset")),
    ([("snapshot", _snapshot("t1"))], None),  # the server closed without saying the turn ended
    ([("error", {"error": "snapshot_unavailable"})], None),
])
def test_a_stream_that_fails_or_closes_early_is_broken(frames, error):
    core = StreamingCore(frames, error)
    streams = TurnStreams(core, FakeClock(), spawn=lambda fn: fn())
    streams.watch("t1", "S030")
    assert core.streamed == [("t1", "S030")]
    assert streams.state("t1").broken and not streams.state("t1").live


def test_a_core_without_a_stream_is_never_watched():
    streams = TurnStreams(FakeCore(), FakeClock(), spawn=lambda fn: fn())
    streams.watch("t1", "S030")
    assert streams.state("t1") is None


def test_the_registry_forgets_the_oldest_turns_past_its_bound():
    streams = TurnStreams(None, FakeClock(), max_tracked=2)
    for t in ("a", "b", "c"):
        streams.begin(t)
    assert streams.state("a") is None and streams.state("c") is not None


# ---- the adapter ----

def test_the_core_adapter_reads_the_sse_frames_with_the_turns_identity():
    body = (b"event: snapshot\nid: 3\ndata: {\"turns\": []}\n\n: keepalive\n\n"
            b"event: delta\nid: 4\ndata: {\"turn_id\": \"t1\", \"text\": \"Hola\"}\n\nevent: end\ndata: {}\n\n")
    seen = {}

    def handler(req: httpx.Request):
        seen["req"] = req
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    core = AgentCoreHttp("http://core", client=httpx.Client(transport=httpx.MockTransport(handler),
                                                             base_url="http://core"))
    frames = list(core.stream_turn("t1", "S030"))

    assert frames == [("snapshot", {"turns": []}), ("delta", {"turn_id": "t1", "text": "Hola"}), ("end", {})]
    req = seen["req"]
    assert req.url.path == "/turns/t1/events" and req.headers["x-tenant-id"] == "S030"
    assert req.headers["x-roles"] == "glazed-manager" and req.headers["accept"] == "text/event-stream"


def test_the_core_adapter_raises_on_an_http_error_so_the_stream_is_broken():
    core = AgentCoreHttp("http://core", client=httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(503)), base_url="http://core"))
    with pytest.raises(Exception):
        list(core.stream_turn("t1", "S030"))


# ---- GetTurn over a stream ----

def test_asking_starts_following_the_turn(world):
    assert world.streams.state(world.tid) is not None


def test_a_live_stream_answers_pending_with_the_partial_reply_and_first_text_time(world):
    world.get.execute(world.case.case_id, world.tid)  # the first read asks the Core (404 grace, status)
    gets = world.core.gets
    _later(world, 1.5)
    world.streams.feed(world.tid, "delta", {"turn_id": world.tid, "text": "<think>x</think>Hoy vendiste 12 cajas"})
    _later(world, 1.0)

    out = world.get.execute(world.case.case_id, world.tid)

    assert out["status"] == "pending"
    assert out["partial_reply"] == "Hoy vendiste 12 cajas"
    assert out["first_text_ms"] == 1500
    assert world.core.gets == gets, "a live stream does not poll the Core within core_check_s"


def test_a_live_stream_still_asks_the_core_after_core_check_s(world):
    world.get.execute(world.case.case_id, world.tid)
    gets = world.core.gets
    _later(world, 6)
    world.core.turns[world.tid] = {"turn_id": world.tid, "status": "failed", "error": "boom"}

    out = world.get.execute(world.case.case_id, world.tid)

    assert world.core.gets == gets + 1 and out["status"] == "failed"


def test_a_finished_stream_reads_the_final_reply_once_and_keeps_the_first_text_time(world):
    _later(world, 0.8)
    world.streams.feed(world.tid, "delta", {"turn_id": world.tid, "text": "Vendimos 12"})
    world.streams.feed(world.tid, "finished", {"turn_id": world.tid})
    world.core.turns[world.tid] = {"turn_id": world.tid, "status": "finished", "text": "Vendimos 12 cajas hoy."}

    out = world.get.execute(world.case.case_id, world.tid)

    assert out["status"] == "done" and out["reply"] == "Vendimos 12 cajas hoy."
    assert out["first_text_ms"] == 800 and "partial_reply" not in out
    stored = world.get.execute(world.case.case_id, world.tid)
    assert stored["reply"] == "Vendimos 12 cajas hoy." and stored["first_text_ms"] == 800


def test_a_broken_stream_polls_the_core_as_before(world):
    world.get.execute(world.case.case_id, world.tid)
    world.streams.state(world.tid).broken = True
    world.core.turns[world.tid] = {"turn_id": world.tid, "status": "finished", "text": "Vendimos 12 cajas hoy."}

    out = world.get.execute(world.case.case_id, world.tid)

    assert out["status"] == "done" and out["reply"] == "Vendimos 12 cajas hoy."


def test_without_streams_get_turn_is_unchanged_polling():
    cases, core, clock, turns = InMemoryCases(), FakeCore(), FakeClock(), InMemoryTurns()
    case = StartCase(cases).execute(store_id="S030", sim_today=date(2026, 3, 10))
    tid = AskAgent(cases, core, TurnTracker(), clock, turns).execute(case.case_id, "hola")

    out = GetTurn(cases, core, TurnTracker(), clock, turns=turns).execute(case.case_id, tid)

    assert out["status"] == "done" and out["reply"] == "echo: hola"
    assert "first_text_ms" not in out and "partial_reply" not in out


def test_a_finished_reply_being_rewritten_is_never_shown_as_partial(world):
    world.streams.feed(world.tid, "delta", {"turn_id": world.tid, "text": "No tengo acceso a los archivos."})
    world.streams.feed(world.tid, "finished", {"turn_id": world.tid})
    world.core.turns[world.tid] = {"turn_id": world.tid, "status": "finished",
                                   "text": "No tengo acceso a los archivos, necesito que me pases los datos reales."}

    out = world.get.execute(world.case.case_id, world.tid)

    assert out["status"] == "pending" and out.get("rewriting") is True
    assert "partial_reply" not in out


# ---- wiring ----

def test_the_public_api_follows_the_turn_and_exposes_the_partial_reply():
    from fastapi.testclient import TestClient

    from glazed_backend.adapters.driving.app import Container, create_app
    from tests.fakes import (FakeMetrics, InMemoryAlerts, InMemoryBacktests, InMemoryExecutions, InMemoryProposals,
                             InMemoryTrace)

    core, clock = StreamingCore(), FakeClock()
    streams = TurnStreams(core, clock, spawn=lambda fn: None)
    c = Container(metrics=FakeMetrics(), core=core, cases=InMemoryCases(), alerts=InMemoryAlerts(),
                  proposals=InMemoryProposals(), executions=InMemoryExecutions(), backtests=InMemoryBacktests(),
                  trace=InMemoryTrace(), clock=clock, turn_streams=streams)
    client = TestClient(create_app(c))
    case = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": "2026-03-10"}).json()
    tid = client.post(f"/api/v1/cases/{case['case_id']}/messages", json={"text": "hola"}).json()["turn_id"]
    core.turns[tid] = {"turn_id": tid, "status": "running"}
    client.get(f"/api/v1/cases/{case['case_id']}/turns/{tid}")
    streams.feed(tid, "delta", {"turn_id": tid, "text": "Hola, gerente"})

    t = client.get(f"/api/v1/cases/{case['case_id']}/turns/{tid}").json()

    assert t["status"] == "pending" and t["partial_reply"] == "Hola, gerente" and t["first_text_ms"] == 0


@pytest.mark.parametrize("env, on", [({}, True), ({"GLAZED_CORE_STREAM": "false"}, False),
                                     ({"GLAZED_CORE_STREAM": "0"}, False), ({"GLAZED_CORE_STREAM": "true"}, True)])
def test_streaming_is_on_by_default_and_off_with_glazed_core_stream_false(env, on):
    from glazed_backend.adapters.driving.app import build_turn_streams

    streams = build_turn_streams(env, StreamingCore(), FakeClock())
    assert (streams is not None) is on
