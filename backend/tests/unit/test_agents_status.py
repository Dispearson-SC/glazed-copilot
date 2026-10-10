"""C11: GET /api/v1/agents/status probes the Core with a short timeout and caches the answer for about 15 s."""
from datetime import timedelta

from fastapi.testclient import TestClient

from glazed_backend.adapters.driving.app import Container, create_app
from glazed_backend.domain.models import AGENT_IDS
from tests.fakes import (FakeClock, FakeCore, FakeMetrics, InMemoryAlerts, InMemoryBacktests, InMemoryCases,
                         InMemoryExecutions, InMemoryProposals, InMemoryTrace)


def env(core=None):
    c = Container(metrics=FakeMetrics(), core=core or FakeCore(), cases=InMemoryCases(), alerts=InMemoryAlerts(),
                  proposals=InMemoryProposals(), executions=InMemoryExecutions(), backtests=InMemoryBacktests(),
                  trace=InMemoryTrace(), clock=FakeClock())
    return TestClient(create_app(c)), c


def status(client):
    r = client.get("/api/v1/agents/status")
    assert r.status_code == 200, r.text
    return r.json()


def test_reachable_core_reports_every_agent_up_with_spanish_names():
    client, _ = env()
    out = status(client)
    assert out["connected"] is True
    assert [a["agent_id"] for a in out["agents"]] == list(AGENT_IDS)
    assert {a["status"] for a in out["agents"]} == {"up"}
    names = {a["agent_id"]: a["display_name_es"] for a in out["agents"]}
    assert names["supply"] == "Analista de abastecimiento" and names["sentinel"] == "Centinela" and names["orchestrator"] == "Copiloto"


def test_unreachable_core_is_disconnected_and_everything_is_down():
    core = FakeCore()
    core.health = lambda: (_ for _ in ()).throw(ConnectionError("refused"))
    client, _ = env(core)
    out = status(client)
    assert out["connected"] is False and {a["status"] for a in out["agents"]} == {"down"}


def test_a_slow_core_is_degraded():
    core = FakeCore()
    core.health = lambda: {"ok": True, "latency_ms": 4200.0}
    client, _ = env(core)
    out = status(client)
    assert out["connected"] is True and {a["status"] for a in out["agents"]} == {"degraded"}


def test_answer_is_cached_for_fifteen_seconds():
    core = FakeCore()
    calls = []
    core.health = lambda: calls.append(1) or {"ok": True, "latency_ms": 5.0}
    client, c = env(core)
    status(client), status(client)
    assert len(calls) == 1
    c.clock._now += timedelta(seconds=16)
    status(client)
    assert len(calls) == 2


def test_missing_core_url_is_disconnected():
    client, c = env()
    from glazed_backend.adapters.driving.app import _NoCore
    c.core = _NoCore()
    assert status(client)["connected"] is False
