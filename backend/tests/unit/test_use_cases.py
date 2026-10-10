from datetime import date, datetime, timezone

import pytest

from glazed_backend.application import (
    AdvanceSimClock, AskAgent, DecideProposal, ForkCase, GetAgentTrace, GetDaySummary, GetTurn,
    ListAlerts, ListCases, RecordEvent, ResumeCase, RunBacktest, StartCase, SubmitProposal,
)
from glazed_backend.domain import AlertState, DomainError, FutureDate, NotFound
from tests.fakes import (FakeClock, FakeCore, FakeMetrics, InMemoryAlerts, InMemoryBacktests, InMemoryCases,
                         InMemoryExecutions, InMemoryProposals, InMemoryTrace)

D = date(2026, 3, 10)


@pytest.fixture
def w():
    class W: ...
    w = W()
    w.cases, w.alerts, w.props = InMemoryCases(), InMemoryAlerts(), InMemoryProposals()
    w.execs, w.bt, w.trace = InMemoryExecutions(), InMemoryBacktests(), InMemoryTrace()
    w.core, w.clock = FakeCore(), FakeClock()
    w.metrics = FakeMetrics()
    return w


def start(w, **kw):
    return StartCase(w.cases).execute(store_id="S030", sim_today=D, **kw)


def test_start_case_persists(w):
    c = start(w, title="t")
    assert w.cases.get(c.case_id).store_id == "S030" and c.mode == "live" and c.title == "t"


def test_list_and_resume(w):
    c = start(w)
    start(w)
    assert len(ListCases(w.cases).execute()) == 2
    assert ResumeCase(w.cases).execute(c.case_id).case_id == c.case_id
    with pytest.raises(NotFound):
        ResumeCase(w.cases).execute("nope")


def test_fork_copies_store_date_and_decisions_but_isolates(w):
    c = start(w)
    p = SubmitProposal(w.cases, w.props).execute(c.case_id, "i1", "place_order", {"sku": "A"}, "N2", "why")
    DecideProposal(w.cases, w.props, w.execs, w.alerts).execute(p.proposal_id, True, "ok")
    child = ForkCase(w.cases, w.props, w.execs).execute(c.case_id, title="what-if")
    assert child.parent_case_id == c.case_id and child.store_id == "S030" and child.sim_today == D
    assert child.case_id != c.case_id and child.core_conversation_id is None
    copied = w.props.list(case_id=child.case_id)
    assert len(copied) == 1 and copied[0].status == "approved" and copied[0].proposal_id != p.proposal_id
    assert len(w.execs.list(child.case_id)) == 1
    # isolation: deciding in the child leaves the parent untouched
    assert len(w.props.list(case_id=c.case_id)) == 1


def test_ask_creates_conversation_once_and_reuses(w):
    c = start(w)
    ask = AskAgent(w.cases, w.core)
    t1 = ask.execute(c.case_id, "hello")
    t2 = ask.execute(c.case_id, "again")
    assert w.core.created == [c.case_id]
    assert w.cases.get(c.case_id).core_conversation_id == f"conv-{c.case_id}"
    assert [s[0] for s in w.core.sent] == [f"conv-{c.case_id}"] * 2 and t1 != t2
    assert w.core.sent[0][1] == "S030"
    assert GetTurn(w.cases, w.core).execute(c.case_id, t1)["text"] == "echo: hello"


def test_ask_rejects_blank_text(w):
    c = start(w)
    with pytest.raises(DomainError):
        AskAgent(w.cases, w.core).execute(c.case_id, "  ")


def test_day_summary_uses_case_as_of_and_defaults_to_previous_day(w):
    c = start(w)
    out = GetDaySummary(w.cases, w.metrics).execute(c.case_id)
    assert out["date"] == "2026-03-09"
    with pytest.raises(FutureDate):
        GetDaySummary(w.cases, w.metrics).execute(c.case_id, date(2026, 3, 11))


ISSUE = {"issue_id": "S030|stockout_risk|SKU-1|2026-03-11", "kind": "stockout_risk", "severity_usd": 120.0,
         "sku": "SKU-1"}


def test_advance_clock_creates_alerts_and_cases_idempotently(w):
    c = start(w)
    w.metrics.issues_by_date[date(2026, 3, 11)] = [ISSUE]
    adv = AdvanceSimClock(w.cases, w.alerts, w.metrics)
    r = adv.execute(c.case_id, days=1)
    assert r["sim_today"] == date(2026, 3, 11) and len(r["alerts"]) == 1
    alert = r["alerts"][0]
    assert alert.alert_type == 2 and alert.severity_usd == 120.0 and alert.state is AlertState.NUEVA
    opened = w.cases.get(alert.case_id)
    assert opened.issue_key == ISSUE["issue_id"] and opened.parent_case_id == c.case_id
    assert w.cases.get(c.case_id).sim_today == date(2026, 3, 11)
    # re-detecting the same issue (fork of the clock) must not duplicate
    again = adv.detect(c.case_id)
    assert again[0].alert_id == alert.alert_id and len(w.alerts.list()) == 1 and len(w.cases.list()) == 2


def test_clock_cannot_go_backwards(w):
    c = start(w)
    with pytest.raises(DomainError):
        AdvanceSimClock(w.cases, w.alerts, w.metrics).execute(c.case_id, to=date(2026, 3, 1))


def test_list_alerts_by_store_sorted_by_severity(w):
    c = start(w)
    w.metrics.issues_by_date[date(2026, 3, 11)] = [ISSUE, {**ISSUE, "issue_id": "x", "severity_usd": 500.0}]
    AdvanceSimClock(w.cases, w.alerts, w.metrics).execute(c.case_id, days=1)
    got = ListAlerts(w.alerts).execute(store_id="S030")
    assert [a.severity_usd for a in got] == [500.0, 120.0]


def test_decide_approve_creates_simulated_execution_and_moves_alert(w):
    c = start(w)
    w.metrics.issues_by_date[date(2026, 3, 11)] = [ISSUE]
    r = AdvanceSimClock(w.cases, w.alerts, w.metrics).execute(c.case_id, days=1)
    alert = r["alerts"][0]
    p = SubmitProposal(w.cases, w.props).execute(alert.case_id, ISSUE["issue_id"], "place_order",
                                                 {"sku": "SKU-1", "qty": 2}, "N2", "stockout risk")
    ex = DecideProposal(w.cases, w.props, w.execs, w.alerts).execute(p.proposal_id, True, "go")
    assert ex.source == "simulated" and ex.status == "executed" and ex.case_id == alert.case_id
    assert w.props.get(p.proposal_id).status == "approved"
    assert w.alerts.get(alert.alert_id).state is AlertState.EJECUTADA


def test_decide_reject_requires_reason_and_records_not_executed(w):
    c = start(w)
    p = SubmitProposal(w.cases, w.props).execute(c.case_id, "i", "skip_order", {}, "N2", "r")
    d = DecideProposal(w.cases, w.props, w.execs, w.alerts)
    with pytest.raises(DomainError):
        d.execute(p.proposal_id, False, "")
    ex = d.execute(p.proposal_id, False, "not now")
    assert ex.status == "not_executed"
    with pytest.raises(DomainError):
        d.execute(p.proposal_id, True, "")


def test_submit_proposal_validates_case_and_action(w):
    with pytest.raises(NotFound):
        SubmitProposal(w.cases, w.props).execute("nope", "i", "place_order", {}, "N2", "r")
    c = start(w)
    with pytest.raises(DomainError):
        SubmitProposal(w.cases, w.props).execute(c.case_id, "i", "hack", {}, "N2", "r")


def test_backtest_replays_each_day_and_labels_results(w):
    c = start(w)
    run = RunBacktest(w.cases, w.metrics, w.bt, w.clock).execute(c.case_id, date(2026, 3, 1), date(2026, 3, 3))
    assert run.label == "backtest" and run.policy == "simple_v0"
    assert [x[2] for x in w.metrics.calls if x[0] == "backtest_day"] == [date(2026, 3, d) for d in (1, 2, 3)]
    r = run.results
    assert r["days"] == 3 and r["waste_usd"] == {"current": 30.0, "policy": 18.0, "delta": -12.0}
    assert r["lost_sales_usd"]["delta"] == -15.0
    assert r["net_usd"] == {"current": 90.0, "policy": 63.0, "delta": -27.0}  # waste + lost sales
    assert w.bt.get(run.run_id).run_id == run.run_id


def test_backtest_rejects_inverted_range(w):
    c = start(w)
    with pytest.raises(DomainError):
        RunBacktest(w.cases, w.metrics, w.bt, w.clock).execute(c.case_id, date(2026, 3, 5), date(2026, 3, 1))


def test_trace_merges_core_transcript_and_recorded_events(w):
    c = start(w)
    AskAgent(w.cases, w.core).execute(c.case_id, "hi")
    w.core.transcript = [
        {"entry_id": "e1", "turn_id": "t", "kind": "user_message", "at": "2026-03-10T10:00:00+00:00",
         "payload": {"text": "hi"}},
        {"entry_id": "e2", "turn_id": "t", "kind": "tool_call", "at": "2026-03-10T10:00:01+00:00",
         "payload": {"tool": "glazed_kpis"}},
    ]
    RecordEvent(w.cases, w.trace, w.clock).execute(c.case_id, "orchestrator", "present", "message", {"t": "x"})
    uc = GetAgentTrace(w.cases, w.core, w.trace)
    events = uc.execute(case_id=c.case_id)
    assert {e.kind for e in events} == {"message", "tool_call"}
    assert len(events) == 3
    assert len(uc.execute(case_id=c.case_id)) == 3  # refresh is idempotent
    assert len(uc.execute(store_id="S030")) == 3
