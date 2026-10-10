"""Repository contract: the same tests run against the in-memory and the Postgres adapters."""
import os
from datetime import date, datetime, timezone

import pytest

from glazed_backend.domain import Alert, AlertState, BacktestRun, Case, Execution, Proposal, TraceEvent
from tests.fakes import (InMemoryAlerts, InMemoryBacktests, InMemoryCases, InMemoryExecutions,
                         InMemoryProposals, InMemoryTrace)

URL = os.environ.get("GLAZED_TEST_DATABASE_URL", "postgresql://glazed_app:glazed_dev@localhost:55432/glazed_test")


def _pg():
    psycopg = pytest.importorskip("psycopg")
    try:
        psycopg.connect(URL, connect_timeout=2).close()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Postgres not reachable: {exc}")
    from glazed_backend.adapters.driven.postgres import PostgresStore
    store = PostgresStore(URL)
    store.migrate()
    store.truncate_all()
    return store


@pytest.fixture(params=["memory", pytest.param("postgres", marks=pytest.mark.integration)])
def repos(request):
    if request.param == "memory":
        class R: cases, alerts, props, execs, bt, trace = (InMemoryCases(), InMemoryAlerts(), InMemoryProposals(),
                                                          InMemoryExecutions(), InMemoryBacktests(), InMemoryTrace())
        return R
    s = _pg()
    class R: cases, alerts, props, execs, bt, trace = s.cases, s.alerts, s.proposals, s.executions, s.backtests, s.trace
    return R


def test_cases_roundtrip_update_and_lookups(repos):
    c = Case.new("S030", date(2026, 3, 10), "sandbox", "t", issue_key="k1")
    repos.cases.add(c)
    got = repos.cases.get(c.case_id)
    assert got == c
    got.core_conversation_id, got.sim_today = "conv", date(2026, 3, 11)
    repos.cases.update(got)
    assert repos.cases.get_by_conversation("conv").sim_today == date(2026, 3, 11)
    assert repos.cases.get_by_issue_key("k1").case_id == c.case_id
    assert repos.cases.get("zzz") is None
    repos.cases.add(Case.new("S001", date(2026, 3, 10)))
    assert [x.store_id for x in repos.cases.list("S030")] == ["S030"] and len(repos.cases.list()) == 2


def test_alerts_roundtrip_filter_and_order(repos):
    a1 = Alert.new(2, "S030", "c1", 10.0, {"issue_id": "i1", "x": [1]}, "i1", date(2026, 3, 10))
    a2 = Alert.new(1, "S030", "c2", 99.0, {"issue_id": "i2"}, "i2", date(2026, 3, 10))
    repos.alerts.add(a1); repos.alerts.add(a2)
    assert repos.alerts.get(a1.alert_id) == a1
    assert [a.alert_id for a in repos.alerts.list("S030")] == [a2.alert_id, a1.alert_id]
    a1.advance(AlertState.VISTA); repos.alerts.update(a1)
    assert [a.alert_id for a in repos.alerts.list(state=AlertState.VISTA)] == [a1.alert_id]
    assert repos.alerts.get_by_issue_key("i2").alert_id == a2.alert_id


def test_proposals_and_executions(repos):
    p = Proposal.new("c1", "S030", "i1", "place_order", {"sku": "A", "qty": 2}, "N2", "why", "supply")
    repos.props.add(p)
    assert repos.props.get(p.proposal_id) == p
    p.decide(True, "ok"); repos.props.update(p)
    assert repos.props.list(case_id="c1", status="approved")[0].reason == "ok"
    assert repos.props.list(case_id="other") == []
    e = Execution.new(p.proposal_id, "c1", "simulated", "executed", "d")
    repos.execs.add(e)
    assert repos.execs.list("c1") == [e] and repos.execs.list("c2") == []


def test_proposal_idempotency_key_lookup_and_uniqueness(repos):
    a = Proposal.new("c1", "S030", "i1", "place_order", {}, "N2", "why", "supply")
    a.idempotency_key = "k" * 32
    repos.props.add(a)
    assert repos.props.find_by_idempotency_key("c1", "k" * 32).proposal_id == a.proposal_id
    assert repos.props.find_by_idempotency_key("c2", "k" * 32) is None
    assert repos.props.find_by_idempotency_key("c1", "zzz") is None
    b = Proposal.new("c2", "S030", "i1", "place_order", {}, "N2", "why", "supply")
    b.idempotency_key = "k" * 32  # same key in another case is allowed
    repos.props.add(b)
    repos.props.add(Proposal.new("c1", "S030", "i1", "place_order", {}, "N2", "why"))  # NULL keys never collide
    repos.props.add(Proposal.new("c1", "S030", "i1", "place_order", {}, "N2", "why"))


def test_backtests(repos):
    r = BacktestRun("r1", "c1", "S030", date(2026, 3, 1), date(2026, 3, 3), "simple_v0",
                    {"days": 3}, datetime(2026, 3, 4, tzinfo=timezone.utc))
    repos.bt.add(r)
    assert repos.bt.get("r1") == r and repos.bt.list("c1") == [r] and repos.bt.list("zz") == []


def test_trace_is_upserted_by_event_id_and_filtered(repos):
    t = TraceEvent("c1", "S030", datetime(2026, 3, 1, tzinfo=timezone.utc), "a", "b", "message", {"k": 1}, "e1")
    repos.trace.record(t); repos.trace.record(t)
    repos.trace.record(TraceEvent("c2", "S001", datetime(2026, 3, 2, tzinfo=timezone.utc), "a", "b", "tool_call", {}, "e2"))
    assert repos.trace.list(case_id="c1") == [t]
    assert len(repos.trace.list(store_id="S001")) == 1 and len(repos.trace.list()) == 2


def test_assistant_repository_roundtrip():
    from glazed_backend.adapters.driven.memory import InMemoryAssistants
    for repo in (InMemoryAssistants(), _pg().assistants):
        assert repo.get("S030") is None
        repo.set("S030", "a1"); repo.set("S030", "a2")
        assert repo.get("S030") == "a2"


def test_turns_roundtrip_upsert_and_order():
    from glazed_backend.adapters.driven.memory import InMemoryTurns
    from glazed_backend.domain import TurnRecord
    for repo in (InMemoryTurns(), _pg().turns):
        t2 = TurnRecord("t2", "c1", "S030", datetime(2026, 3, 2, tzinfo=timezone.utc), "second")
        t1 = TurnRecord("t1", "c1", "S030", datetime(2026, 3, 1, tzinfo=timezone.utc), "first")
        repo.add(t2); repo.add(t1); repo.add(TurnRecord("t3", "c2", "S030", datetime(2026, 3, 3, tzinfo=timezone.utc), "x"))
        assert [t.turn_id for t in repo.list("c1")] == ["t1", "t2"] and repo.get("zz") is None
        t1.status, t1.reply = "done", "full reply"
        repo.add(t1)
        got = repo.get("t1")
        assert got == t1 and got.final and got.reply_meta is None
