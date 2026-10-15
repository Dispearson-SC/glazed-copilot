"""P5: the backend follows a Core turn's SSE feed (`GET /turns/{id}/events`) instead of polling it for its text.

THE RULES UNDER TEST. The stream keeps the ROOT turn's streamed text (snapshot `reply_text`, then `delta` events;
never a peer's) and when the first text arrived; `finished`/`failed` of the root or `end` closes it; an error, a
raise or a stream that closes early marks it broken. While a stream is live, GetTurn answers `pending` with the
cleaned `partial_reply` and `first_text_ms` without asking the Core more often than `core_check_s`; once it finished
GetTurn reads the final reply from `GET /turns/{id}` as before and keeps `first_text_ms` (also on stored reads); a
broken stream, or no stream at all, is plain polling exactly as before.

P11 (Core's chunk identity). A delta's `detail` is `<run>:<response>:<index>`: a chunk of another run or response
starts the text over (the model answered again after a tool call, the step was retried, or the Core took a cut
draft back with ONE empty chunk before the turn fell back). A withdrawn text keeps the first-text time and GetTurn
answers `partial_reply: ""` so the client clears the draft it shows. A delta without a `detail` still appends.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import httpx
import pytest

from glazed_backend.adapters.driven.agent_core_http import AgentCoreHttp
from glazed_backend.domain.models import CoreError
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


def _chunk(turn_id: str, detail: str, text: str) -> dict:
    return {"turn_id": turn_id, "detail": detail, "text": text}


def test_a_chunk_of_a_new_response_or_run_starts_the_text_over():
    clock = FakeClock()
    streams = TurnStreams(None, clock)
    streams.begin("t1")
    streams.feed("t1", "delta", _chunk("t1", "r1:0:0", "Déjame revisar. "))
    first = streams.state("t1").first_text_at
    streams.feed("t1", "delta", _chunk("t1", "r1:0:1", "Un momento."))
    assert streams.state("t1").text == "Déjame revisar. Un momento."
    clock._now = clock._now + timedelta(seconds=3)
    streams.feed("t1", "delta", _chunk("t1", "r1:1:0", "Hoy vendiste 12. "))  # after a tool call
    assert streams.state("t1").text == "Hoy vendiste 12. "
    streams.feed("t1", "delta", _chunk("t1", "r2:0:0", "Hoy vendiste 12 cajas."))  # a retried step
    assert streams.state("t1").text == "Hoy vendiste 12 cajas."
    assert streams.state("t1").first_text_at == first, "the first text time is the first chunk's"


def test_the_cores_empty_chunk_takes_a_cut_draft_back():
    clock = FakeClock()
    streams = TurnStreams(None, clock)
    streams.begin("t1")
    streams.feed("t1", "delta", _chunk("t1", "r1:0:0", "Producto A tiene 3. "))
    first = streams.state("t1").first_text_at
    streams.feed("t1", "delta", _chunk("t1", "r1:1:0", ""))
    state = streams.state("t1")
    assert state.text == "" and state.first_text_at == first and state.live
    streams.feed("t1", "delta", _chunk("t1", "r9:0:0", "Respuesta completa."))
    assert state.text == "Respuesta completa."


def test_an_empty_chunk_as_the_first_text_is_no_first_text():
    streams = TurnStreams(None, FakeClock())
    streams.begin("t1")
    streams.feed("t1", "delta", _chunk("t1", "r1:1:0", ""))
    assert streams.state("t1").text == "" and streams.state("t1").first_text_at is None


def test_after_a_snapshot_the_rest_of_its_response_appends_and_a_new_one_starts_over():
    streams = TurnStreams(None, FakeClock())
    streams.begin("t1")
    streams.feed("t1", "snapshot", _snapshot("t1", "Hoy vendiste"))
    streams.feed("t1", "delta", _chunk("t1", "r1:0:3", " 12 cajas."))
    assert streams.state("t1").text == "Hoy vendiste 12 cajas."
    streams.feed("t1", "delta", _chunk("t1", "r1:1:0", ""))
    assert streams.state("t1").text == ""
    streams.feed("t1", "snapshot", _snapshot("t1", ""))  # a reconnect after the withdrawal
    assert streams.state("t1").text == ""


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


def test_a_stream_the_registry_stops_following_is_closed_at_once():
    """Slice gm6: closing is what gives a capped stream's slot (and its connection) back; the registry
    closes the stream when the turn ends instead of leaving it to the garbage collector."""
    closed = []

    class Closing(StreamingCore):
        def __init__(self) -> None:
            super().__init__()
            self.made = []  # another holder (a pool, a debugger): the collector will not close it

        def stream_turn(self, turn_id, store_id):
            def frames():
                try:
                    yield ("snapshot", _snapshot(turn_id, "Hola", state="finished"))
                    yield ("delta", {"turn_id": turn_id, "text": "never read"})
                finally:
                    closed.append(turn_id)

            self.made.append(frames())
            return self.made[-1]

    events = []
    core = Closing()
    streams = TurnStreams(core, FakeClock(), spawn=lambda fn: events.append(fn))
    streams.watch("t1", "S030")

    events[0]()

    assert closed == ["t1"] and streams.state("t1").finished


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


def _sse_core(max_streams: int, requests: list | None = None) -> AgentCoreHttp:
    body = b"event: delta\ndata: {\"turn_id\": \"t1\", \"text\": \"Hola\"}\n\nevent: end\ndata: {}\n\n"

    def handler(req: httpx.Request):
        if requests is not None:
            requests.append(req.url.path)
        if req.url.path.endswith("/events"):
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})
        return httpx.Response(200, json={"turn_id": "t1", "status": "running"})

    return AgentCoreHttp("http://core", max_streams=max_streams,
                         client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://core"))


def test_streams_past_the_cap_are_refused_at_once_so_the_turn_polls_instead():
    """Slice gm6: every stream holds a pooled connection for the length of a turn. Past
    `max_streams` open streams a new one is refused immediately (CoreError: the registry marks it
    broken and GetTurn polls), so streams can never take the connections polling and sending need."""
    requests: list[str] = []
    core = _sse_core(2, requests)
    first, second = core.stream_turn("t1", "S030"), core.stream_turn("t2", "S030")
    assert next(first)[0] == "delta" and next(second)[0] == "delta"  # two streams are open

    with pytest.raises(CoreError, match="stream"):
        next(core.stream_turn("t3", "S030"))
    assert "/turns/t3/events" not in requests, "a refused stream never takes a connection"
    assert core.get_turn("t3", "S030")["status"] == "running", "polling still has its connections"

    first.close()  # a finished (or abandoned) stream gives its slot back
    assert next(core.stream_turn("t4", "S030"))[0] == "delta"


def test_a_stream_that_fails_gives_its_slot_back():
    core = AgentCoreHttp("http://core", max_streams=1, client=httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(503)), base_url="http://core"))
    for _ in range(3):
        with pytest.raises(CoreError, match="503"):
            list(core.stream_turn("t1", "S030"))


@pytest.mark.parametrize("env, cap", [({}, 16), ({"GLAZED_CORE_MAX_STREAMS": "4"}, 4)])
def test_the_stream_cap_is_set_from_the_environment(env, cap):
    assert AgentCoreHttp.from_env("http://core", env).max_streams == cap


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


def test_a_withdrawn_draft_answers_an_empty_partial_reply_so_the_client_clears_it(world):
    world.get.execute(world.case.case_id, world.tid)
    _later(world, 1.0)
    world.streams.feed(world.tid, "delta", _chunk(world.tid, "r1:0:0", "Producto A tiene 3."))
    assert world.get.execute(world.case.case_id, world.tid)["partial_reply"] == "Producto A tiene 3."
    world.streams.feed(world.tid, "delta", _chunk(world.tid, "r1:1:0", ""))

    out = world.get.execute(world.case.case_id, world.tid)

    assert out["status"] == "pending" and out["partial_reply"] == "" and out["first_text_ms"] == 1000


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


def _partial(world, text):
    world.get.execute(world.case.case_id, world.tid)
    world.streams.feed(world.tid, "delta", {"turn_id": world.tid, "text": text})
    return world.get.execute(world.case.case_id, world.tid)


def test_a_partial_the_final_guard_would_rewrite_is_never_exposed(world):
    """Slice gm6: the partial reply passes the SAME quality guard as the final one; a draft the final
    reply would send back for a rewrite (meta talk, restarts) is withheld, the turn stays pending."""
    out = _partial(world, "No tengo acceso a los datos. Let me think about the order.")

    assert out["status"] == "pending"
    assert "partial_reply" not in out
    assert out["first_text_ms"] is not None, "the first-text time is a measurement, not text"


def test_a_partial_still_reasoning_inside_an_open_think_block_is_never_exposed(world):
    """The final sanitizer keeps the text of an unclosed think block (the model forgot to close it);
    mid-stream it is reasoning that has not ended yet, so nothing is shown."""
    out = _partial(world, "<think>el gerente quiere saber las ventas, reviso get_kpis")

    assert out["status"] == "pending" and "partial_reply" not in out


def test_a_clean_partial_is_exposed_cleaned_as_before(world):
    out = _partial(world, "Hoy vendiste 12 cajas de glaseadas")

    assert out["partial_reply"] == "Hoy vendiste 12 cajas de glaseadas"


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


def test_end_to_end_a_routed_turn_streamed_by_a_fake_core_sse_carries_first_text_ms():
    """P11, offline end to end: the real Core adapter over HTTP (a fake Core: POST /turns, the SSE feed, GET
    /turns/{id}), the real stream registry and the public API. The Core streams a routed turn's draft, takes it
    back, streams the fallback reply and finishes; the manager's turn read carries `first_text_ms` from the first
    chunk (2.3 s after the message was sent) and the final reply from GET /turns/{id}."""
    from fastapi.testclient import TestClient

    from glazed_backend.adapters.driving.app import Container, create_app
    from tests.fakes import (FakeMetrics, InMemoryAlerts, InMemoryBacktests, InMemoryExecutions, InMemoryProposals,
                             InMemoryTrace)

    clock = FakeClock()
    tid = "00000000-0000-4000-8000-0000000000aa"
    frames = [
        ("snapshot", {"root_turn_id": tid, "turns": [{"turn_id": tid, "state": "running", "reply_text": ""}]}),
        ("delta", {"turn_id": tid, "detail": "r1:0:0", "text": "Producto A tiene 3. "}),
        ("delta", {"turn_id": tid, "detail": "r1:1:0", "text": ""}),
        ("delta", {"turn_id": tid, "detail": "r2:0:0", "text": "Tienes 2 unidades de glaseadas."}),
        ("finished", {"turn_id": tid}),
        ("end", {}),
    ]
    body = "".join(f"event: {kind}\ndata: {json.dumps(data)}\n\n" for kind, data in frames).encode()
    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(f"{req.method} {req.url.path}")
        if req.method == "POST" and req.url.path == "/turns":
            return httpx.Response(200, json={"turn_id": tid})
        if req.url.path == f"/turns/{tid}/events":
            clock._now = clock._now + timedelta(seconds=2.3)  # the first chunk arrives 2.3 s after the send
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})
        if req.url.path == f"/turns/{tid}":
            return httpx.Response(200, json={"turn_id": tid, "status": "finished",
                                             "text": "Tienes 2 unidades de glaseadas."})
        return httpx.Response(404)

    core = AgentCoreHttp("http://core", max_streams=4,
                         client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://core"))
    streams = TurnStreams(core, clock, spawn=lambda fn: fn())  # consume the feed at once, in order
    c = Container(metrics=FakeMetrics(), core=core, cases=InMemoryCases(), alerts=InMemoryAlerts(),
                  proposals=InMemoryProposals(), executions=InMemoryExecutions(), backtests=InMemoryBacktests(),
                  trace=InMemoryTrace(), clock=clock, turn_streams=streams)
    client = TestClient(create_app(c))
    case = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": "2026-03-10"}).json()
    sent = client.post(f"/api/v1/cases/{case['case_id']}/messages", json={"text": "¿cuántas glaseadas tengo?"})
    assert sent.json()["turn_id"] == tid and f"GET /turns/{tid}/events" in seen

    t = client.get(f"/api/v1/cases/{case['case_id']}/turns/{tid}").json()

    assert t["status"] == "done" and t["reply"] == "Tienes 2 unidades de glaseadas."
    assert t["first_text_ms"] == 2300
    assert "partial_reply" not in t


@pytest.mark.parametrize("env, on", [({}, True), ({"GLAZED_CORE_STREAM": "false"}, False),
                                     ({"GLAZED_CORE_STREAM": "0"}, False), ({"GLAZED_CORE_STREAM": "true"}, True)])
def test_streaming_is_on_by_default_and_off_with_glazed_core_stream_false(env, on):
    from glazed_backend.adapters.driving.app import build_turn_streams

    streams = build_turn_streams(env, StreamingCore(), FakeClock())
    assert (streams is not None) is on


# ---- opening a stream before the Core knows the turn (L18: first_text null on every turn) ----

def _core_answering(*statuses: int, sleeps: list | None = None) -> tuple[AgentCoreHttp, list]:
    body = b"event: delta\ndata: {\"turn_id\": \"t1\", \"text\": \"Hola\"}\n\nevent: end\ndata: {}\n\n"
    answers, seen = list(statuses), []

    def handler(req: httpx.Request):
        seen.append(req.url.path)
        status = answers.pop(0) if answers else 200
        if status == 200:
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})
        return httpx.Response(status)

    core = AgentCoreHttp("http://core", client=httpx.Client(transport=httpx.MockTransport(handler),
                                                             base_url="http://core"),
                         sleep=(sleeps.append if sleeps is not None else (lambda s: None)))
    return core, seen


def test_a_stream_opened_before_the_core_knows_the_turn_is_retried_briefly_on_404():
    """Right after POST /turns the Core may not have the turn yet (its route step runs first): a 404
    on the events route is retried a few times, quickly, before the turn falls back to polling."""
    sleeps: list = []
    core, seen = _core_answering(404, 404, sleeps=sleeps)

    frames = list(core.stream_turn("t1", "S030"))

    assert frames == [("delta", {"turn_id": "t1", "text": "Hola"}), ("end", {})]
    assert seen == ["/turns/t1/events"] * 3
    assert sleeps == list(AgentCoreHttp.STREAM_OPEN_RETRY_DELAYS_S[:2])
    # L24: the route step (800 ms router deadline) and the queue pick-up run before the turn exists;
    # a window of about 1 s missed it after a restart and the whole turn was shown only when done.
    assert 2.5 <= sum(AgentCoreHttp.STREAM_OPEN_RETRY_DELAYS_S) <= 3.5, "a short wait, then polling"


def test_a_turn_still_unknown_after_the_retries_breaks_the_stream_and_other_errors_never_retry():
    core, seen = _core_answering(*([404] * 10))
    with pytest.raises(CoreError, match="404"):
        list(core.stream_turn("t1", "S030"))
    assert len(seen) == len(AgentCoreHttp.STREAM_OPEN_RETRY_DELAYS_S) + 1

    core, seen = _core_answering(503)
    with pytest.raises(CoreError, match="503"):
        list(core.stream_turn("t1", "S030"))
    assert seen == ["/turns/t1/events"]
