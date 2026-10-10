"""Use cases. Each class takes the ports it needs; none touches I/O directly."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from ..domain import (Alert, AlertState, BacktestRun, Case, DomainError, Execution, Experience, FutureDate, NotFound,
                      Proposal, TraceEvent, alert_type_for_kind, new_id)
from ..ports import (AlertRepository, BacktestRepository, CaseRepository, Clock, CorePort,
                     ExecutionRepository, ExperienceMemoryPort, MetricsPort, ProposalRepository, TracePort)


def _case(cases: CaseRepository, case_id: str) -> Case:
    case = cases.get(case_id) or cases.get_by_conversation(case_id)
    if case is None:
        raise NotFound(f"case {case_id!r} not found")
    return case


class StartCase:
    def __init__(self, cases: CaseRepository) -> None:
        self.cases = cases

    def execute(self, store_id: str, sim_today: date, mode: str = "live", title: str = "") -> Case:
        case = Case.new(store_id, sim_today, mode, title)
        self.cases.add(case)
        return case


class ListCases:
    def __init__(self, cases: CaseRepository) -> None:
        self.cases = cases

    def execute(self, store_id: str | None = None) -> list[Case]:
        return self.cases.list(store_id)


class ResumeCase:
    def __init__(self, cases: CaseRepository) -> None:
        self.cases = cases

    def execute(self, case_id: str) -> Case:
        return _case(self.cases, case_id)


class ForkCase:
    """What-if: new case with the same store/date and a copy of the decisions."""

    def __init__(self, cases: CaseRepository, proposals: ProposalRepository, executions: ExecutionRepository) -> None:
        self.cases, self.proposals, self.executions = cases, proposals, executions

    def execute(self, case_id: str, title: str = "") -> Case:
        parent = _case(self.cases, case_id)
        child = Case.new(parent.store_id, parent.sim_today, "sandbox" if parent.mode == "live" else parent.mode,
                         title or f"fork of {parent.title}", parent_case_id=parent.case_id)
        self.cases.add(child)
        mapping: dict[str, str] = {}
        for p in self.proposals.list(case_id=parent.case_id):
            copy = Proposal(new_id(), child.case_id, p.store_id, p.issue_id, p.action_type, dict(p.params),
                            p.tier, p.rationale, p.status, p.reason, p.agent_id, p.created_at)
            mapping[p.proposal_id] = copy.proposal_id
            self.proposals.add(copy)
        for e in self.executions.list(parent.case_id):
            if e.proposal_id in mapping:
                self.executions.add(Execution(new_id(), mapping[e.proposal_id], child.case_id, e.source,
                                              e.status, e.detail, e.executed_at))
        return child


class AskAgent:
    """Send a manager message to the orchestrator through the case's Core conversation."""

    def __init__(self, cases: CaseRepository, core: CorePort) -> None:
        self.cases, self.core = cases, core

    def execute(self, case_id: str, text: str) -> str:
        if not text.strip():
            raise DomainError("message text is required")
        case = _case(self.cases, case_id)
        if case.core_conversation_id is None:
            case.core_conversation_id = self.core.create_conversation(case.case_id, case.store_id)
            self.cases.update(case)
        return self.core.send_turn(case.core_conversation_id, case.store_id, text)


class GetTurn:
    def __init__(self, cases: CaseRepository, core: CorePort) -> None:
        self.cases, self.core = cases, core

    def execute(self, case_id: str, turn_id: str) -> dict[str, Any]:
        case = _case(self.cases, case_id)
        return self.core.get_turn(turn_id, case.store_id)


class GetDaySummary:
    def __init__(self, cases: CaseRepository, metrics: MetricsPort) -> None:
        self.cases, self.metrics = cases, metrics

    def execute(self, case_id: str, day: date | None = None) -> dict[str, Any]:
        case = _case(self.cases, case_id)
        day = day or case.sim_today - timedelta(days=1)
        if day > case.sim_today:
            raise FutureDate(f"{day} is after the case date {case.sim_today}")
        return self.metrics.day_summary(case.store_id, case.sim_today, day)


class AdvanceSimClock:
    """Move the case's simulated 'today' forward and run detectors for the store.

    Each detected issue becomes one Alert, and opens its own case (idempotent per issue key)."""

    def __init__(self, cases: CaseRepository, alerts: AlertRepository, metrics: MetricsPort, limit: int = 5) -> None:
        self.cases, self.alerts, self.metrics, self.limit = cases, alerts, metrics, limit

    def execute(self, case_id: str, days: int = 1, to: date | None = None) -> dict[str, Any]:
        case = _case(self.cases, case_id)
        target = to or case.sim_today + timedelta(days=days)
        if target < case.sim_today:
            raise DomainError("the simulated clock cannot go backwards")
        case.sim_today = target
        self.cases.update(case)
        return {"case_id": case.case_id, "sim_today": target, "alerts": self.detect(case_id)}

    def detect(self, case_id: str) -> list[Alert]:
        case = _case(self.cases, case_id)
        out: list[Alert] = []
        for issue in self.metrics.issues(case.store_id, case.sim_today, self.limit):
            key = issue["issue_id"]
            alert = self.alerts.get_by_issue_key(key)
            if alert is None:
                opened = self.cases.get_by_issue_key(key)
                if opened is None:
                    opened = Case.new(case.store_id, case.sim_today, case.mode,
                                      f"{issue.get('kind', 'issue')} {issue.get('sku') or ''}".strip(),
                                      parent_case_id=case.case_id, issue_key=key)
                    self.cases.add(opened)
                alert = Alert.new(alert_type_for_kind(issue.get("kind", "")), case.store_id, opened.case_id,
                                  issue.get("severity_usd", 0.0), issue, key, case.sim_today)
                self.alerts.add(alert)
            out.append(alert)
        return out


class ListAlerts:
    def __init__(self, alerts: AlertRepository) -> None:
        self.alerts = alerts

    def execute(self, store_id: str | None = None, state: AlertState | None = None) -> list[Alert]:
        return self.alerts.list(store_id, state)


class SubmitProposal:
    """An agent proposes an action (pending). The manager decides later."""

    def __init__(self, cases: CaseRepository, proposals: ProposalRepository) -> None:
        self.cases, self.proposals = cases, proposals

    def execute(self, case_id: str, issue_id: str, action_type: str, params: dict[str, Any], tier: str,
                rationale: str, agent_id: str = "") -> Proposal:
        case = _case(self.cases, case_id)
        proposal = Proposal.new(case.case_id, case.store_id, issue_id, action_type, params, tier, rationale, agent_id)
        self.proposals.add(proposal)
        return proposal


class DecideProposal:
    def __init__(self, cases: CaseRepository, proposals: ProposalRepository, executions: ExecutionRepository,
                 alerts: AlertRepository, memory: ExperienceMemoryPort | None = None) -> None:
        self.cases, self.proposals, self.executions, self.alerts = cases, proposals, executions, alerts
        self.memory = memory

    def execute(self, proposal_id: str, approved: bool, reason: str = "") -> Execution:
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            raise NotFound(f"proposal {proposal_id!r} not found")
        proposal.decide(approved, reason)
        self.proposals.update(proposal)
        runs = approved and proposal.action_type != "do_nothing"
        execution = Execution.new(proposal.proposal_id, proposal.case_id, "simulated",
                                  "executed" if runs else "not_executed",
                                  reason if not approved else f"simulated {proposal.action_type}")
        self.executions.add(execution)
        alert = self.alerts.get_by_issue_key(proposal.issue_id)
        if alert is not None:
            alert.advance_to(AlertState.DECIDIDA)
            alert.advance(AlertState.APROBADA if approved else AlertState.RECHAZADA)
            if approved:
                alert.advance(AlertState.EJECUTADA)
            self.alerts.update(alert)
        self._remember(proposal)
        return execution

    def _remember(self, p: Proposal) -> None:
        if self.memory is None:
            return
        case = self.cases.get(p.case_id)
        parts = p.issue_id.split("|")
        kind, key = (parts[1], parts[2]) if len(parts) >= 3 else ("issue", p.issue_id)
        when = case.sim_today.isoformat() if case else ""
        verdict = "APPROVED" if p.status == "approved" else "REJECTED"
        text = (f"[{p.store_id} · {kind} · {key} · {when}] {p.action_type} {verdict}. {p.reason or 'no reason given'}. "
                f"Simulated option: {json.dumps(p.params, sort_keys=True)}. tier={p.tier}. decision_id={p.proposal_id}")
        try:
            self.memory.remember(p.store_id, Experience(text, "decision", p.store_id, p.proposal_id))
        except Exception:  # noqa: BLE001 - memory is best-effort, never blocks a decision
            pass


class RecordOutcome:
    """Write the measured result of a decision into the store's experience memory (from code only)."""

    def __init__(self, proposals: ProposalRepository, cases: CaseRepository, memory: ExperienceMemoryPort | None) -> None:
        self.proposals, self.cases, self.memory = proposals, cases, memory

    def execute(self, proposal_id: str, summary: str) -> Experience:
        p = self.proposals.get(proposal_id)
        if p is None:
            raise NotFound(f"proposal {proposal_id!r} not found")
        exp = Experience(f"[{p.store_id} · outcome · {p.action_type}] measured: {summary}. decision_id={p.proposal_id}",
                         "outcome", p.store_id, p.proposal_id)
        if self.memory is not None:
            try:
                self.memory.remember(p.store_id, exp)
            except Exception:  # noqa: BLE001
                pass
        return exp


class RecallExperiences:
    """Returns (experiences, warning). Never raises: memory problems degrade to ([], warning)."""

    def __init__(self, memory: ExperienceMemoryPort | None) -> None:
        self.memory = memory

    def execute(self, store_id: str, query: str, limit: int = 5) -> tuple[list[Experience], str | None]:
        if self.memory is None:
            return [], "experience memory not configured"
        try:
            return self.memory.recall(store_id, query, limit), None
        except Exception as exc:  # noqa: BLE001
            return [], str(exc)


class RunBacktest:
    """Replay a period day by day: simple policy vs current practice. Results are labeled 'backtest'."""

    POLICY = "simple_v0"

    def __init__(self, cases: CaseRepository, metrics: MetricsPort, backtests: BacktestRepository, clock: Clock) -> None:
        self.cases, self.metrics, self.backtests, self.clock = cases, metrics, backtests, clock

    def execute(self, case_id: str, date_from: date, date_to: date, policy: str = POLICY) -> BacktestRun:
        case = _case(self.cases, case_id)
        if date_to < date_from:
            raise DomainError("date_to must not precede date_from")
        totals = {"waste_usd": [0.0, 0.0], "lost_sales_usd": [0.0, 0.0]}
        daily = []
        day, days = date_from, 0
        while day <= date_to:
            res = self.metrics.backtest_day(case.store_id, day, policy)
            for k in totals:
                totals[k][0] += res["current"][k]
                totals[k][1] += res["policy"][k]
            daily.append({"date": day.isoformat(), **res})
            day, days = day + timedelta(days=1), days + 1
        results: dict[str, Any] = {"label": "backtest", "days": days, "daily": daily,
                                   "note": "Estimates from a simple projection, not a guarantee."}
        for k, (cur, pol) in totals.items():
            results[k] = {"current": round(cur, 2), "policy": round(pol, 2), "delta": round(pol - cur, 2)}
        cur_net = sum(v[0] for v in totals.values())
        pol_net = sum(v[1] for v in totals.values())  # net cost = waste + lost sales; lower is better
        results["net_usd"] = {"current": round(cur_net, 2), "policy": round(pol_net, 2),
                              "delta": round(pol_net - cur_net, 2)}
        run = BacktestRun(new_id(), case.case_id, case.store_id, date_from, date_to, policy, results,
                          self.clock.now())
        self.backtests.add(run)
        return run


_KIND_MAP = (("tool_call", "tool_call"), ("tool_result", "tool_result"), ("escalat", "escalation"),
             ("approval", "escalation"))


def _event_from_entry(case: Case, entry: dict[str, Any]) -> TraceEvent:
    raw = str(entry.get("kind", "message"))
    kind = next((v for k, v in _KIND_MAP if k in raw), "message")
    payload = entry.get("payload") or {}
    user = raw.startswith("user")
    frm = payload.get("from_agent") or ("manager" if user else payload.get("profile_id") or "agent")
    to = payload.get("to_agent") or ("orchestrator" if user else "manager")
    return TraceEvent(case.case_id, case.store_id, datetime.fromisoformat(str(entry["at"])), frm, to, kind,
                      {"core_kind": raw, **payload}, event_id=str(entry.get("entry_id") or new_id()))


class GetAgentTrace:
    """Agent communication by case or store: Core transcript (cached) plus recorded events."""

    def __init__(self, cases: CaseRepository, core: CorePort, trace: TracePort) -> None:
        self.cases, self.core, self.trace = cases, core, trace

    def execute(self, case_id: str | None = None, store_id: str | None = None) -> list[TraceEvent]:
        if case_id:
            case = _case(self.cases, case_id)
            self._refresh(case)
            return self.trace.list(case_id=case.case_id)
        for case in self.cases.list(store_id):
            self._refresh(case)
        return self.trace.list(store_id=store_id)

    def _refresh(self, case: Case) -> None:
        if not case.core_conversation_id:
            return
        try:
            entries = self.core.list_transcript(case.core_conversation_id, case.store_id)
        except Exception:  # Core unavailable: serve the cache
            return
        for entry in entries:
            self.trace.record(_event_from_entry(case, entry))


class RecordEvent:
    def __init__(self, cases: CaseRepository, trace: TracePort, clock: Clock) -> None:
        self.cases, self.trace, self.clock = cases, trace, clock

    def execute(self, case_id: str, from_agent: str, to_agent: str, kind: str, payload: dict[str, Any]) -> TraceEvent:
        case = _case(self.cases, case_id)
        event = TraceEvent(case.case_id, case.store_id, self.clock.now(), from_agent, to_agent, kind, payload)
        self.trace.record(event)
        return event
