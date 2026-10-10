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
    assert GetTurn(w.cases, w.core).execute(c.case_id, t1)["reply"] == "echo: hello"


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


def _trace_for(w, entries):
    c = start(w)
    AskAgent(w.cases, w.core).execute(c.case_id, "hi")
    w.core.transcript = entries
    return GetAgentTrace(w.cases, w.core, w.trace).execute(case_id=c.case_id)


def _entry(i, kind, payload, at="2026-03-10T10:00:0%d+00:00"):
    return {"entry_id": f"e{i}", "turn_id": "t", "kind": kind, "at": at % i, "payload": payload}


def test_trace_messages_carry_text_from_core_content(w):
    events = _trace_for(w, [
        _entry(1, "user_message", {"role": "user", "content": "how was the day?"}),
        _entry(2, "agent_message", {"role": "assistant", "content": [{"type": "text", "text": "Good."}]}),
    ])
    assert [(e.kind, e.payload["text"]) for e in events] == [("message", "how was the day?"), ("message", "Good.")]
    assert (events[0].from_agent, events[0].to_agent) == ("manager", "orchestrator")
    assert (events[1].from_agent, events[1].to_agent) == ("orchestrator", "manager")


def test_trace_tool_calls_carry_tool_args_and_result_summary(w):
    events = _trace_for(w, [
        _entry(1, "tool_call", {"tool": "propose_action", "caller": "x", "arguments": {"issue_id": "i1"}}),
        _entry(2, "tool_result", {"tool_name": "propose_action", "result": "r" * 500}),
    ])
    call, res = events
    assert call.kind == "tool_call" and call.payload["tool"] == "propose_action"
    assert call.payload["args"] == {"issue_id": "i1"}
    assert res.kind == "tool_result" and res.payload["tool"] == "propose_action"
    assert 0 < len(res.payload["result"]) <= 301


def test_trace_peer_exchange_becomes_question_and_answer_between_canonical_agents(w):
    events = _trace_for(w, [
        _entry(1, "peer_exchange", {"target_agent_id": "glazed_supply", "hop": 0, "state": "answered",
                                    "question": "stock of SKU-1?", "answer": "3 days"})])
    assert [(e.from_agent, e.to_agent, e.kind, e.payload["text"]) for e in events] == [
        ("orchestrator", "supply", "message", "stock of SKU-1?"),
        ("supply", "orchestrator", "message", "3 days")]


def test_trace_policy_denial_and_pending_request_are_escalations(w):
    events = _trace_for(w, [
        _entry(1, "policy_denial", {"tool": "ask_peer", "arguments": {}, "effect": "deny"}),
        _entry(2, "pending_request", {"kind": "approval", "tool_call_id": "tc"})])
    assert [e.kind for e in events] == ["escalation", "escalation"]
    assert events[0].payload["tool"] == "ask_peer"
    assert events[1].payload["text"]


def test_canonical_agent_ids():
    from glazed_backend.domain import canonical_agent_id
    for role in ("orchestrator", "present", "past", "supply", "strategist", "sentinel", "auditor", "liaison"):
        assert canonical_agent_id(f"glazed_{role}") == role == canonical_agent_id(role)
    assert canonical_agent_id("manager") == "manager" and canonical_agent_id("glazed_other") == "glazed_other"


def test_record_event_canonicalizes_core_profile_ids(w):
    c = start(w)
    e = RecordEvent(w.cases, w.trace, w.clock).execute(c.case_id, "glazed_sentinel", "glazed_orchestrator",
                                                         "message", {"text": "x"})
    assert (e.from_agent, e.to_agent) == ("sentinel", "orchestrator")


class _KpiStub:
    def __init__(self):
        self.calls = []

    def kpis(self, store_id, as_of, date_from, date_to):
        self.calls.append((store_id, as_of, date_from, date_to))
        return {"store_id": store_id, "net_sales": 700.0, "units": 70, "transactions": 50, "footfall": 200,
                "conversion": 0.25, "tx_per_staff_hour": 2.5, "waste_usd": 12.0, "stockout_hours": 4.0}


def test_explain_metric_returns_definition_formula_value_inputs_for_the_case_window(w):
    from glazed_backend.application import ExplainMetric
    c = start(w)
    stub = _KpiStub()
    out = ExplainMetric(w.cases, stub).execute(c.case_id, "conversion")
    assert stub.calls == [("S030", date(2026, 3, 10), date(2026, 3, 4), date(2026, 3, 10))]
    assert out["metric"] == "conversion" and out["value"] == 0.25
    assert out["definition"] and "footfall" in out["formula"]
    assert out["inputs"] == {"transactions": 50, "footfall": 200}
    assert out["window"] == {"date_from": "2026-03-04", "date_to": "2026-03-10"}


def test_explain_metric_rejects_unknown_metric_listing_the_known_ones(w):
    from glazed_backend.application import ExplainMetric
    c = start(w)
    with pytest.raises(DomainError, match="net_sales"):
        ExplainMetric(w.cases, _KpiStub()).execute(c.case_id, "vibes")


# --- turn polling against the real Core quirks -------------------------------------------------
from datetime import timedelta  # noqa: E402

from glazed_backend.application import GetTurn, TurnTracker  # noqa: E402
from glazed_backend.domain import NotFound  # noqa: E402


def _turns(w, **kw):
    tracker = TurnTracker()
    ask = AskAgent(w.cases, w.core, tracker, w.clock)
    get = GetTurn(w.cases, w.core, tracker, w.clock, **kw)
    return ask, get


def _sent_turn(w, ask, raw):
    c = start(w)
    tid = ask.execute(c.case_id, "hi")
    w.core.turns[tid] = raw
    return c, tid


def test_turn_404_right_after_the_202_is_pending_then_an_error(w):
    ask, get = _turns(w)
    c = start(w)
    tid = ask.execute(c.case_id, "hi")
    del w.core.turns[tid]  # fake core raises KeyError today; make it a 404 like the real one
    w.core.get_turn = lambda turn_id, store_id: (_ for _ in ()).throw(NotFound("no turn"))
    assert get.execute(c.case_id, tid) == {"turn_id": tid, "status": "pending", "progress": []}
    w.clock._now += timedelta(seconds=90)  # a turn queued behind another one in the conversation stays 404 for ~90s
    assert get.execute(c.case_id, tid) == {"turn_id": tid, "status": "pending", "progress": []}
    w.clock._now += timedelta(seconds=60)
    with pytest.raises(NotFound):
        get.execute(c.case_id, tid)


def test_turn_statuses_map_to_the_public_contract(w):
    ask, get = _turns(w)
    c, tid = _sent_turn(w, ask, {"turn_id": "x", "status": "running", "text": None})
    assert get.execute(c.case_id, tid) == {"turn_id": tid, "status": "pending", "progress": []}
    w.core.turns[tid] = {"turn_id": tid, "status": "finished", "text": "all good"}
    assert get.execute(c.case_id, tid) == {"turn_id": tid, "status": "done", "reply": "all good", "progress": []}


def test_waiting_is_pending_unless_an_approval_is_open(w):
    ask, get = _turns(w)
    c, tid = _sent_turn(w, ask, {"turn_id": "x", "status": "waiting", "text": None})
    assert get.execute(c.case_id, tid)["status"] == "pending"  # suspended on a peer, not on the manager
    w.core.transcript = [{"entry_id": "p1", "turn_id": tid, "kind": "pending_request", "at": "2026-03-10T10:00:00+00:00",
                          "payload": {"kind": "approval", "answered_at": None}}]
    assert get.execute(c.case_id, tid)["status"] == "waiting_approval"
    w.core.transcript[0]["payload"]["answered_at"] = "2026-03-10T10:01:00+00:00"
    assert get.execute(c.case_id, tid)["status"] == "pending"


def test_long_running_turn_is_flagged_not_failed_after_the_soft_timeout(w):
    ask, get = _turns(w, timeout_s=120)
    c, tid = _sent_turn(w, ask, {"turn_id": "x", "status": "running", "text": None})
    w.clock._now += timedelta(seconds=119)
    assert "still_running" not in get.execute(c.case_id, tid)
    w.clock._now += timedelta(seconds=500)
    out = get.execute(c.case_id, tid)
    assert out["status"] == "pending" and out["still_running"] is True
    for st in ("waiting", "started"):
        w.core.turns[tid] = {"turn_id": tid, "status": st, "text": None}
        assert get.execute(c.case_id, tid)["status"] in ("pending", "waiting_approval")
    w.core.turns[tid] = {"turn_id": tid, "status": "failed", "error": "boom"}
    assert get.execute(c.case_id, tid)["status"] == "failed"  # only a Core failure fails it
    w.core.turns[tid] = {"turn_id": tid, "status": "finished", "text": "late"}
    assert get.execute(c.case_id, tid)["status"] == "done"  # a real answer always wins over the timeout


def test_unknown_core_status_past_the_timeout_fails(w):
    ask, get = _turns(w, timeout_s=120)
    c, tid = _sent_turn(w, ask, {"turn_id": "x", "status": "mystery", "text": None})
    w.clock._now += timedelta(seconds=121)
    out = get.execute(c.case_id, tid)
    assert out["status"] == "failed" and "timed out" in out["error"]


def _alert_for(w, case, key, state=None):
    from glazed_backend.domain import Alert, AlertState
    a = Alert.new(1, case.store_id, case.case_id, 10.0, {"issue_id": key}, key, D)
    if state:
        a.state = state
    w.alerts.add(a)
    return a


def test_decide_is_scoped_to_the_proposals_case_and_never_errors_on_a_stale_alert(w):
    from glazed_backend.domain import AlertState
    a_case, b_case = start(w), start(w)
    stale = _alert_for(w, a_case, "S030|x|k", AlertState.EJECUTADA)  # another case already carried it to ejecutada
    p = SubmitProposal(w.cases, w.props).execute(b_case.case_id, "S030|x|k", "place_order", {"sku": "A"}, "N2", "why")
    ex = DecideProposal(w.cases, w.props, w.execs, w.alerts).execute(p.proposal_id, True, "ok")
    assert ex.status == "executed" and w.props.get(p.proposal_id).status == "approved"
    assert w.alerts.get(stale.alert_id).state == AlertState.EJECUTADA  # foreign alert untouched


def test_decide_is_idempotent_for_an_alert_already_advanced_in_the_same_case(w):
    from glazed_backend.domain import AlertState
    c = start(w)
    al = _alert_for(w, c, "S030|x|k", AlertState.EJECUTADA)
    p = SubmitProposal(w.cases, w.props).execute(c.case_id, "S030|x|k", "place_order", {"sku": "A"}, "N2", "why")
    DecideProposal(w.cases, w.props, w.execs, w.alerts).execute(p.proposal_id, True, "ok")
    assert w.alerts.get(al.alert_id).state == AlertState.EJECUTADA


def test_decide_advances_the_alert_of_its_own_case(w):
    from glazed_backend.domain import AlertState
    c = start(w)
    al = _alert_for(w, c, "S030|x|k")
    p = SubmitProposal(w.cases, w.props).execute(c.case_id, "S030|x|k", "place_order", {"sku": "A"}, "N2", "why")
    DecideProposal(w.cases, w.props, w.execs, w.alerts).execute(p.proposal_id, True, "ok")
    assert w.alerts.get(al.alert_id).state == AlertState.EJECUTADA


def test_sanitize_reply_strips_stray_non_latin_runs_and_reports_them():
    from glazed_backend.application import sanitize_reply
    clean, removed = sanitize_reply("Las ventas 螃蟹贡献 subieron, 近似 el 5% y 持有 stock.")
    assert clean == "Las ventas subieron, el 5% y stock."
    assert removed == ["螃蟹贡献", "近似", "持有"]
    clean, removed = sanitize_reply("Привет мир and مرحبا ok")
    assert clean == "and ok" and removed == ["Привет мир", "مرحبا"]


def test_sanitize_reply_leaves_spanish_digits_and_markdown_untouched():
    from glazed_backend.application import sanitize_reply
    text = "**Señor** Peña: ¿cómo está? Ágil, éxito, mañana, ñandú, pingüino, ó ú í — total $1,392.15 (€20, 3.5%) `x` #1 • ok"
    assert sanitize_reply(text) == (text, [])


def test_get_turn_marks_a_sanitized_reply_in_the_payload(w):
    ask, get = _turns(w)
    c, tid = _sent_turn(w, ask, {"turn_id": "x", "status": "finished", "text": "Hay 12 螃蟹贡献 cajas  en $1,392.15"})
    out = get.execute(c.case_id, tid)
    assert out["reply"] == "Hay 12 cajas en $1,392.15"
    assert out["sanitized"] is True and out["sanitized_fragments"] == ["螃蟹贡献"]
    w.core.turns[tid] = {"turn_id": "x", "status": "finished", "text": "Todo bien"}
    assert "sanitized" not in get.execute(c.case_id, tid)


def test_a_turn_core_never_finishes_fails_as_stale_even_after_a_backend_restart(w):
    """The in-process tracker is lost on restart; the stored turn's ts still ages it. Past `stale_s` a turn Core
    keeps reporting as running (e.g. its worker crashed) fails instead of showing 'still working' forever."""
    from glazed_backend.adapters.driven.memory import InMemoryTurns
    from glazed_backend.domain.models import TurnRecord

    turns = InMemoryTurns()
    c = start(w)
    turns.add(TurnRecord("t1", c.case_id, c.store_id, w.clock.now(), "hola"))
    w.core.turns["t1"] = {"turn_id": "t1", "status": "running", "text": None}
    get = GetTurn(w.cases, w.core, TurnTracker(), w.clock, timeout_s=600, turns=turns, stale_s=1800)
    w.clock._now += timedelta(seconds=700)
    out = get.execute(c.case_id, "t1")
    assert out["status"] == "pending" and out["still_running"] is True
    w.clock._now += timedelta(seconds=1200)
    out = get.execute(c.case_id, "t1")
    assert out["status"] == "failed" and "stale" in out["error"]
