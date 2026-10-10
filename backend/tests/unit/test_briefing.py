import time
from datetime import date, timedelta

from fastapi.testclient import TestClient

from glazed_backend.adapters.driving.app import Container, create_app
from tests.fakes import (FakeClock, FakeCore, InMemoryAlerts, InMemoryBacktests, InMemoryCases, InMemoryExecutions,
                         InMemoryProposals, InMemoryTrace)
from tests.unit.snapshot_support import AS_OF, RichMetrics, env, mkcase, snap  # noqa: F401


def test_briefing_shape_and_code_computed_headline(env):
    client, _, _ = env
    b = client.get("/internal/v1/briefing", headers={"X-Glazed-Case": mkcase(client)}).json()
    assert set(b) == {"snapshot", "headline", "suggested_focus"}
    h = b["headline"]
    assert 1 <= len(h) <= 5 and all(set(f) >= {"key", "text", "value", "unit", "source"} for f in h)
    by = {f["key"]: f for f in h}
    assert by["waste_7d"]["value"] == 1429.6 and by["waste_7d"]["unit"] == "USD"
    assert by["lost_sales"]["text"].startswith("Venta perdida estimada $37") and "$503" in by["lost_sales"]["text"]
    assert by["orders_due_today"]["value"] == 2
    assert "Costa" in by["worst_supplier"]["text"] and by["worst_supplier"]["value"] == 71.0
    assert by["top_issue"]["value"] == 100.0
    assert b["suggested_focus"][:3] == [i["issue_id"] for i in b["snapshot"]["top_issues"][:3]]


def test_briefing_is_cached_per_case_and_sim_day(env):
    client, _, m = env
    cid = mkcase(client)
    h = {"X-Glazed-Case": cid}
    first = client.get("/internal/v1/briefing", headers=h).json()
    calls = dict(m.counts)
    m.sleep = 0.5  # any recompute would now be slow and visible in the counters
    t0 = time.perf_counter()
    again = client.get("/internal/v1/briefing", headers=h).json()
    assert time.perf_counter() - t0 < 0.05
    assert m.counts == calls and again["headline"] == first["headline"]
    assert again["snapshot"]["generated_at"] == first["snapshot"]["generated_at"]


def test_cache_age_is_recorded(env):
    client, c, _ = env
    cid = mkcase(client)
    snap(client, cid)
    c.clock._now = c.clock._now + timedelta(seconds=42)
    assert snap(client, cid)["cache_age_s"] == 42


def test_advance_recomputes_for_the_new_day_in_the_background(env):
    client, c, m = env
    cid = mkcase(client)
    snap(client, cid)
    client.post(f"/api/v1/cases/{cid}/advance", json={"days": 1})
    c.briefings.wait_idle()
    m.sleep = 0.5
    t0 = time.perf_counter()
    s = snap(client, cid)
    assert s["as_of"] == "2026-03-11" and time.perf_counter() - t0 < 0.1  # served from the refreshed cache


def test_create_and_fork_refresh_in_the_background(env):
    client, c, m = env
    cid = mkcase(client)
    c.briefings.wait_idle()
    n = m.counts["order_plan"]
    assert n >= 1
    fork = client.post(f"/api/v1/cases/{cid}/fork", json={}).json()["case_id"]
    c.briefings.wait_idle()
    assert m.counts["order_plan"] == n + 1 or (fork, AS_OF) in c.briefings.keys()


def test_reads_are_traced_as_tool_calls(env):
    client, c, _ = env
    cid = mkcase(client)
    snap(client, cid, **{"X-Glazed-Agent": "present"})
    client.get("/internal/v1/briefing", headers={"X-Glazed-Case": cid, "X-Glazed-Agent": "orchestrator"})
    tools = [(e.from_agent, e.payload["tool"]) for e in c.trace.list(case_id=cid) if e.kind == "tool_call"]
    assert ("present", "snapshot") in tools and ("orchestrator", "briefing") in tools


def test_public_briefing_mirror(env):
    client, _, _ = env
    cid = mkcase(client)
    r = client.get(f"/api/v1/cases/{cid}/briefing")
    assert r.status_code == 200 and set(r.json()) == {"snapshot", "headline", "suggested_focus"}
    assert client.get("/api/v1/cases/nope/briefing").status_code == 404


def test_a_failing_background_refresh_never_raises(env):
    client, c, m = env
    m.issues = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    cid = mkcase(client)
    c.briefings.wait_idle()
    assert client.get("/api/v1/health").status_code == 200


def test_warm_recent_precomputes_distinct_recent_cases(env):
    client, c, m = env
    a = mkcase(client)
    c.briefings.wait_idle()
    c.briefings.clear()
    m.counts.clear()
    c.briefings.warm_recent(limit=3)
    c.briefings.wait_idle()
    assert (a, AS_OF) in c.briefings.keys()



def test_startup_warm_up_does_not_block_and_survives_failures():
    metrics = RichMetrics()
    metrics.sleep = 0.5
    c = Container(metrics=metrics, core=FakeCore(), cases=InMemoryCases(), alerts=InMemoryAlerts(),
                  proposals=InMemoryProposals(), executions=InMemoryExecutions(), backtests=InMemoryBacktests(),
                  trace=InMemoryTrace(), clock=FakeClock(), warm_on_startup=True)
    from glazed_backend.domain import Case
    c.cases.add(Case.new("S030", AS_OF, "live", "t"))

    class Boom:
        def warm(self):
            raise RuntimeError("no network")
    c.memory = Boom()
    t0 = time.perf_counter()
    with TestClient(create_app(c)) as client:
        assert time.perf_counter() - t0 < 0.3  # the 4+ slow metric calls run in the background
        assert client.get("/api/v1/health").status_code == 200
        c.briefings.wait_idle()
        assert len(c.briefings.keys()) == 1


def test_backboard_warm_builds_the_client_without_network_and_skips_without_a_key():
    from glazed_backend.adapters.driven.backboard_memory import BackboardMemory
    built = []
    BackboardMemory("k", None, client_factory=lambda: built.append(1)).warm()
    BackboardMemory("", None, client_factory=lambda: built.append(1)).warm()
    assert built == [1]
