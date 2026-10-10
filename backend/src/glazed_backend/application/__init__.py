"""Use cases. Each class takes the ports it needs; none touches I/O directly."""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Any

from ..domain import (Alert, AlertState, BacktestRun, Case, DecisionMemory, DomainError, Execution, Experience, FutureDate, InvalidTransition, NotFound,
                      Proposal, TraceEvent, TurnRecord, alert_type_for_kind, canonical_agent_id, case_id_from_session, new_id, utcnow)
from .reply_sanitizer import clean_reply, role_name_es, sanitize_reply  # noqa: F401 - sanitize_reply stays importable from here
from ..ports import (AlertRepository, BacktestRepository, CaseRepository, Clock, CorePort,
                     ExecutionRepository, ExperienceMemoryPort, MetricsPort, ProposalRepository, TracePort,
                     TurnRepository)


def _case(cases: CaseRepository, case_id: str) -> Case:
    case_id = case_id_from_session(case_id)
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


class TurnTracker:
    """When each Core turn was started (in-process): drives the 404 grace and the overall timeout."""

    def __init__(self) -> None:
        self._started: dict[str, datetime] = {}
        self.backfilled: set[str] = set()  # cases whose Core transcript was already read for turn history

    def started(self, turn_id: str, at: datetime) -> None:
        self._started[turn_id] = at

    def started_at(self, turn_id: str) -> datetime | None:
        return self._started.get(turn_id)


class AskAgent:
    """Send a manager message to the orchestrator through the case's Core conversation."""

    def __init__(self, cases: CaseRepository, core: CorePort, tracker: TurnTracker | None = None,
                 clock: Clock | None = None, turns: TurnRepository | None = None) -> None:
        self.cases, self.core, self.tracker, self.clock, self.turns = cases, core, tracker, clock, turns

    def execute(self, case_id: str, text: str, context: dict[str, Any] | None = None,
                lookup: Any = None) -> str:
        """`context` = {issue_id, option_id?, mode}: validated against the case, pinned in front of the message sent to
        the Core (computed by code) and echoed in reply_meta.context. The stored user_text is the manager's text only."""
        if not text.strip():
            raise DomainError("message text is required")
        case = _case(self.cases, case_id)
        sent, echo = text, None
        if context:
            from . import copilot
            issue = lookup(case, context["issue_id"])
            copilot.validate_context(issue, context.get("option_id"), context["mode"])
            sent = copilot.context_block(issue, context.get("option_id"), context["mode"]) + text
            echo = {k: v for k, v in context.items() if v is not None}
        if case.core_conversation_id is None:
            case.core_conversation_id = self.core.create_conversation(case.case_id, case.store_id)
            self.cases.update(case)
        turn_id = self.core.send_turn(case.core_conversation_id, case.store_id, sent)
        if self.tracker and self.clock:
            self.tracker.started(turn_id, self.clock.now())
        if self.turns is not None and self.clock:
            self.turns.add(TurnRecord(turn_id, case.case_id, case.store_id, self.clock.now(), text,
                                      reply_meta={"context": echo} if echo else None))
        return turn_id


REWRITE_PROMPT = ("Rewrite your previous answer as one clean final answer for the manager, no drafts, no internal names. "
                  "Reescribe tu respuesta anterior como una sola respuesta final limpia para el gerente, en español, "
                  "sin borradores y sin nombres internos.")
REWRITE_TIMEOUT_S = 300.0
_LIVE_STATUSES = ("running", "waiting", "started", "pending", "queued")


class GetTurn:
    """Poll a turn and normalize Core's quirks into the public contract
    `{turn_id, status: pending|done|failed|waiting_approval, reply?, error?}`:
    - Core answers 404 for about a second after the 202 -> pending during a short grace period.
    - Core `waiting` means suspended on a peer OR on an approval -> waiting_approval only if an approval is open.
    - Past `timeout_s` a turn Core still reports running/waiting/started stays pending with `still_running: true`
      (real multi-peer turns take 4-7 min); only a Core failure or an unknown status fails it."""

    def __init__(self, cases: CaseRepository, core: CorePort, tracker: TurnTracker | None = None,
                 clock: Clock | None = None, timeout_s: float = 600.0, grace_s: float = 120.0,
                 turns: TurnRepository | None = None) -> None:
        self.cases, self.core, self.tracker, self.clock = cases, core, tracker, clock
        self.timeout_s, self.grace_s, self.turns = timeout_s, grace_s, turns

    def _age(self, turn_id: str) -> float | None:
        started = self.tracker.started_at(turn_id) if self.tracker and self.clock else None
        return (self.clock.now() - started).total_seconds() if started else None

    def execute(self, case_id: str, turn_id: str) -> dict[str, Any]:
        case = _case(self.cases, case_id)
        rec = self.turns.get(turn_id) if self.turns is not None else None
        if rec is not None and rec.status == "done" and rec.reply is not None and rec.reply_meta:
            return self._stored(turn_id, rec)  # final and already judged: stable, never rewritten again
        meta: dict[str, Any] = {}
        out = self._poll(case, turn_id, meta)
        out["progress"] = self._progress(case, turn_id, out.get("status") in ("done", "failed"))
        if out["progress"] and out.get("status") == "done":
            meta["progress"] = out["progress"]
        self._persist(turn_id, out, meta)
        ctx = ((rec.reply_meta or {}).get("context")) if rec is not None else None
        if ctx:  # the pinned issue context is echoed on every read of the turn
            out["reply_meta"] = {**out.get("reply_meta", {}), "context": ctx}
        return out

    @staticmethod
    def _stored(turn_id: str, rec: TurnRecord) -> dict[str, Any]:
        out: dict[str, Any] = {"turn_id": turn_id, "status": "done", "reply": rec.reply}
        if rec.reply_meta and rec.reply_meta.get("rewritten"):
            out["reply_meta"] = {"rewritten": True, "sanitized": True}
        if rec.reply_meta and rec.reply_meta.get("context"):
            out["reply_meta"] = {**out.get("reply_meta", {}), "context": rec.reply_meta["context"]}
        out["progress"] = list((rec.reply_meta or {}).get("progress") or [])
        return out

    def _progress(self, case: Case, turn_id: str, finished: bool) -> list[dict[str, str]]:
        """[{agent_id, display_name_es, state: consulting|done}] from the orchestrator's peer asks in this turn: an ask
        is consulting until its peer_exchange carries an answer; a finished turn has no open consultation."""
        if not case.core_conversation_id:
            return []
        try:
            entries = self.core.list_transcript(case.core_conversation_id, case.store_id)
        except Exception:  # noqa: BLE001 - progress is cosmetic: never fail a poll over it
            return []
        order: list[str] = []
        state: dict[str, str] = {}  # the latest event about an agent decides
        for e in entries:
            if str(e.get("turn_id")) != turn_id:
                continue
            payload, kind = dict(e.get("payload") or {}), e.get("kind")
            if kind == "tool_call" and payload.get("tool") == "ask_peer":
                args = payload.get("arguments") or {}
                target = args.get("target") or args.get("agent_id") or args.get("target_agent_id")
                answered = False
            elif kind == "peer_exchange":
                target = payload.get("target_agent_id")
                answered = bool(payload.get("answer")) or str(payload.get("state", "")).lower() in ("answered", "done", "completed", "finished")
            else:
                continue
            if target:
                agent = canonical_agent_id(str(target))
                if agent not in order:
                    order.append(agent)
                state[agent] = "done" if answered else "consulting"
        return [{"agent_id": a, "display_name_es": role_name_es(a), "state": "done" if finished else state[a]} for a in order]

    def _persist(self, turn_id: str, out: dict[str, Any], meta: dict[str, Any]) -> None:
        """Keep the final status and the FULL sanitized reply (history reads it from here, not from /trace)."""
        if self.turns is None:
            return
        rec = self.turns.get(turn_id)
        if rec is None or rec.final:
            return
        if out.get("status") in ("done", "failed"):
            rec.status, rec.reply, rec.error = out["status"], out.get("reply"), out.get("error")
            if out["status"] == "done" and meta:
                rec.reply_meta = {**(rec.reply_meta or {}), **meta}
                rec.reply_meta.pop("rewrite_turn_id", None)
            self.turns.add(rec)
        elif meta.get("rewrite_turn_id"):
            rec.reply_meta = {**(rec.reply_meta or {}), **meta}
            self.turns.add(rec)

    def _finish(self, case: Case, turn_id: str, text: str, meta: dict[str, Any]) -> dict[str, Any]:
        """The turn finished: sanitize; if the reply still looks contaminated ask the Core for ONE rewrite in the same
        conversation and keep the cleaner of the two. The rewrite id lives in the stored turn, which is the guard."""
        out: dict[str, Any] = {"turn_id": turn_id, "status": "done"}
        cleaning = clean_reply(text)
        rec = self.turns.get(turn_id) if self.turns is not None else None
        rewrite_id = (rec.reply_meta or {}).get("rewrite_turn_id") if rec is not None else None
        rewritten = None
        if rec is not None and rewrite_id is None and cleaning.contaminated and case.core_conversation_id and self.clock:
            try:
                new_id_ = self.core.send_turn(case.core_conversation_id, case.store_id, REWRITE_PROMPT)
            except Exception:  # noqa: BLE001 - cannot ask: deliver what we have
                new_id_ = None
            if new_id_:
                if self.tracker:
                    self.tracker.started(new_id_, self.clock.now())
                meta["rewrite_turn_id"] = new_id_
                return {"turn_id": turn_id, "status": "pending", "rewriting": True}
        if rewrite_id is not None:
            second = self._rewrite_result(case, str(rewrite_id))
            if second is None:
                return {"turn_id": turn_id, "status": "pending", "rewriting": True}
            alt = clean_reply(second) if second else None
            rewritten = False
            if alt is not None and alt.text.strip() and alt.score < cleaning.score:
                cleaning, rewritten = alt, True
        out["reply"] = cleaning.text
        if cleaning.removed:  # auditable: what was dropped from the model's reply
            out["sanitized"], out["sanitized_fragments"] = True, cleaning.removed
        meta["sanitized"] = True
        if rewritten is not None:
            meta["rewritten"] = rewritten
        if cleaning.contaminated:
            meta["contaminated"] = True
        if rewritten:
            out["reply_meta"] = {"rewritten": True, "sanitized": True}
        return out

    def _rewrite_result(self, case: Case, rewrite_id: str) -> str | None:
        """Text of the rewrite turn, "" when it failed or took too long (keep the original), None while it runs."""
        age = self._age(rewrite_id)
        try:
            raw = self.core.get_turn(rewrite_id, case.store_id)
        except Exception:  # noqa: BLE001 - 404 while queued, or Core down
            return None if age is not None and age < self.grace_s else ""
        status = str(raw.get("status", "")).lower()
        if status == "finished":
            text = raw.get("reply", raw.get("text"))
            return text if isinstance(text, str) else ""
        if status in ("failed", "error") or (age is not None and age > REWRITE_TIMEOUT_S):
            return ""
        return None

    def _poll(self, case: Case, turn_id: str, meta: dict[str, Any]) -> dict[str, Any]:
        age = self._age(turn_id)
        try:
            raw = self.core.get_turn(turn_id, case.store_id)
        except NotFound:
            if age is not None and age < self.grace_s:
                return {"turn_id": turn_id, "status": "pending"}
            raise
        out: dict[str, Any] = {"turn_id": turn_id}
        core_status = str(raw.get("status", "")).lower()
        text = raw.get("reply", raw.get("text"))
        if core_status == "finished":
            if not isinstance(text, str):
                return {**out, "status": "done", **({"reply": text} if text is not None else {})}
            return self._finish(case, turn_id, text, meta)
        if core_status in ("failed", "error"):
            return {**out, "status": "failed", "error": raw.get("error") or text or "Agent-Core reported a failed turn"}
        overdue = age is not None and age > self.timeout_s
        if overdue and core_status not in _LIVE_STATUSES:
            return {**out, "status": "failed",
                    "error": f"turn timed out after {self.timeout_s:g}s without an answer from Agent-Core"}
        out["status"] = "waiting_approval" if core_status == "waiting" and self._approval_open(case, turn_id) else "pending"
        if overdue and out["status"] == "pending":
            out["still_running"] = True  # past the soft timeout but Core still works on it: never a false failure
        return out

    def _approval_open(self, case: Case, turn_id: str) -> bool:
        try:
            entries = self.core.list_transcript(case.core_conversation_id or case.case_id, case.store_id)
        except Exception:  # noqa: BLE001 - cannot tell: keep polling
            return False
        return any(e.get("kind") == "pending_request" and str(e.get("turn_id")) == turn_id
                   and not (e.get("payload") or {}).get("answered_at") for e in entries)


class ListTurns:
    """The conversation history of a case: [{turn_id, ts, user_text, reply, status, ...}] ordered by ts.
    The reply is the stored FULL final reply. Turns still in flight are resolved on read (like a poll); turns that
    exist only in the Core transcript (sent before turns were stored) are back-filled once per case and process."""

    def __init__(self, cases: CaseRepository, core: CorePort, turns: TurnRepository, getter: GetTurn,
                 tracker: TurnTracker | None = None) -> None:
        self.cases, self.core, self.turns, self.getter, self.tracker = cases, core, turns, getter, tracker

    def execute(self, case_id: str) -> list[dict[str, Any]]:
        case = _case(self.cases, case_id)
        self._backfill(case)
        out = []
        for rec in self.turns.list(case.case_id):
            live: dict[str, Any] = {}
            if not rec.final:
                try:
                    live = self.getter.execute(case.case_id, rec.turn_id)
                except Exception:  # noqa: BLE001 - Core cannot tell right now: the turn stays pending
                    live = {}
                rec = self.turns.get(rec.turn_id) or rec
            item: dict[str, Any] = {"turn_id": rec.turn_id, "ts": rec.ts.isoformat(), "user_text": _message_text({"text": rec.user_text}),
                                    "reply": rec.reply if rec.final else None,
                                    "status": rec.status if rec.final else live.get("status", "pending")}
            if rec.error:
                item["error"] = rec.error
            if live.get("still_running") and not rec.final:
                item["still_running"] = True
            if rec.reply_meta:
                item["reply_meta"] = rec.reply_meta
            out.append(item)
        return out

    def _backfill(self, case: Case) -> None:
        if not case.core_conversation_id or (self.tracker is not None and case.case_id in self.tracker.backfilled):
            return
        try:
            entries = self.core.list_transcript(case.core_conversation_id, case.store_id)
        except Exception:  # noqa: BLE001 - try again on the next read
            return
        if self.tracker is not None:
            self.tracker.backfilled.add(case.case_id)
        for e in entries:
            tid = str(e.get("turn_id") or "")
            if e.get("kind") != "user_message" or not tid or self.turns.get(tid) is not None:
                continue
            if _message_text(dict(e.get("payload") or {})).startswith(REWRITE_PROMPT[:40]):
                continue  # our own rewrite request is not a manager message
            self.turns.add(TurnRecord(tid, case.case_id, case.store_id, datetime.fromisoformat(str(e["at"])),
                                      _message_text(dict(e.get("payload") or {}))))


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

    Each detected issue becomes one Alert, and opens its own case (idempotent per issue key). The Sentinel check runs
    too: an approved decision that was not executed, or missed its simulated range, raises a compliance alert."""

    def __init__(self, cases: CaseRepository, alerts: AlertRepository, metrics: MetricsPort, limit: int = 5,
                 compliance: Any = None) -> None:
        self.cases, self.alerts, self.metrics, self.limit, self.compliance = cases, alerts, metrics, limit, compliance

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
        out: list[Alert] = [self._raise(case, issue) for issue in self.metrics.issues(case.store_id, case.sim_today, self.limit)]
        if self.compliance is not None:
            from .sentinel import deviation_issue
            out += [self._raise(case, deviation_issue(res, case.sim_today)) for res in self.compliance.deviations(case.case_id)]
        return out

    def _raise(self, case: Case, issue: dict[str, Any]) -> Alert:
        key = issue["issue_id"]
        alert = self.alerts.get_by_issue_key(key)
        if alert is not None and "options" not in alert.issue:  # raised before issues carried options
            alert.issue, alert.severity_usd = issue, float(issue.get("severity_usd", alert.severity_usd))
            self.alerts.update(alert)
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
        return alert


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


class ProposeOption:
    """Turn (issue_id, option_id) into a pending proposal. action_type, params and tier are copied from the stored
    option; whatever the caller sends for them is ignored, so an agent can neither invent an action nor pick a tier.

    The option is found in what was served to this case, then in the alert's stored issue, then recomputed
    deterministically from the metrics at the case date. Anything else is a 400."""

    def __init__(self, cases: CaseRepository, proposals: ProposalRepository, alerts: AlertRepository,
                 metrics: MetricsPort, served: dict | None = None) -> None:
        self.cases, self.proposals, self.alerts, self.metrics = cases, proposals, alerts, metrics
        self.served = served if served is not None else {}

    def _issue(self, case: Case, issue_id: str) -> dict[str, Any] | None:
        from .copilot import find_issue
        return find_issue(self.alerts, self.metrics, self.served, case, issue_id)

    def execute(self, case_id: str, issue_id: str, option_id: str | None, rationale: str = "",
                agent_id: str = "", idempotency_key: str | None = None) -> Proposal:
        return self.execute_keyed(case_id, issue_id, option_id, rationale, agent_id, idempotency_key)[0]

    def execute_keyed(self, case_id: str, issue_id: str, option_id: str | None, rationale: str = "",
                      agent_id: str = "", idempotency_key: str | None = None) -> tuple[Proposal, bool]:
        """(proposal, created). A repeated key within the same case returns the original proposal, created=False."""
        case = _case(self.cases, case_id)
        if idempotency_key:
            prior = self.proposals.find_by_idempotency_key(case.case_id, idempotency_key)
            if prior is not None:
                return prior, False
        if not option_id:
            raise DomainError("option_id is required: propose one of the options returned with the issue")
        issue = self._issue(case, issue_id)
        option = next((o for o in (issue or {}).get("options", []) if o.get("option_id") == option_id), None)
        if option is None:
            raise DomainError(f"unknown option {option_id!r} for issue {issue_id!r}")
        ben, cost = option.get("expected_benefit_usd") or {}, option.get("cost_usd")
        lo, hi = ben.get("low"), ben.get("high")
        expected = {"net_usd_mid": option.get("net_usd_mid"), "cost_usd": cost,
                    "net_usd_low": None if lo is None or cost is None else round(lo - cost, 2),
                    "net_usd_high": None if hi is None or cost is None else round(hi - cost, 2)}
        proposal = Proposal.new(case.case_id, case.store_id, issue_id, option["action_type"],
                                {**option.get("params", {}), "option_id": option_id,
                                 "decision_as_of": case.sim_today.isoformat(), "expected": expected},
                                option.get("tier") or "N2", rationale, agent_id)
        proposal.idempotency_key = idempotency_key or None
        self.proposals.add(proposal)
        return proposal, True


class DecideProposal:
    def __init__(self, cases: CaseRepository, proposals: ProposalRepository, executions: ExecutionRepository,
                 alerts: AlertRepository, memory: ExperienceMemoryPort | None = None,
                 classifier: Any = None, decision_memories: Any = None, clock: Clock | None = None) -> None:
        self.cases, self.proposals, self.executions, self.alerts = cases, proposals, executions, alerts
        self.memory, self.classifier = memory, classifier
        self.decision_memories, self.clock = decision_memories, clock

    def execute(self, proposal_id: str, approved: bool, reason: str = "", subject: str | None = None) -> Execution:
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            raise NotFound(f"proposal {proposal_id!r} not found")
        proposal.decide(approved, reason)
        if not approved and self.classifier is not None and reason.strip():
            try:  # Jev turns the free-text reason into a label; it never blocks the decision
                res = self.classifier.classify("rejection_reason", reason)
                proposal.reason_category, proposal.reason_confidence = res.label, res.confidence
            except Exception:  # noqa: BLE001
                pass
        self.proposals.update(proposal)
        runs = approved and proposal.action_type != "do_nothing"
        execution = Execution.new(proposal.proposal_id, proposal.case_id, "simulated",
                                  "executed" if runs else "not_executed",
                                  reason if not approved else f"simulated {proposal.action_type}")
        self.executions.add(execution)
        self._advance_alert(proposal, approved)
        self._remember(proposal)
        if not approved and reason.strip():
            self._keep_preference(proposal, subject)
        return execution

    def _keep_preference(self, p: Proposal, subject: str | None) -> None:
        """A rejection with a reason is a stated preference: keep it as a `preferencias` memory (best effort)."""
        if self.decision_memories is None:
            return
        try:
            from ..metrics.memory_view import rejected_text
            case = self.cases.get(p.case_id)
            when = case.sim_today.isoformat() if case else None
            text = rejected_text(p.action_type, subject or p.params.get("sku") or p.issue_id, when, p.reason, p.reason_category)
            self.decision_memories.add(DecisionMemory(
                f"rej-{p.proposal_id}", p.store_id, p.case_id, p.proposal_id, "preferencias", text, p.reason_category,
                p.action_type, p.params.get("sku"), self.clock.now() if self.clock else utcnow(), p.reason))
        except Exception:  # noqa: BLE001 - never blocks a decision
            pass

    def _advance_alert(self, proposal: Proposal, approved: bool) -> None:
        """Alert lifecycle for a decision: scoped to the proposal's own case, idempotent, and never an error
        (the decision is already committed, so a stale or foreign alert must not turn it into a 409)."""
        try:
            alert = self.alerts.get_by_issue_key(proposal.issue_id)
            if alert is None or alert.case_id != proposal.case_id:
                return  # issue_key is shared across cases: another case's alert is not ours to move
            path = [AlertState.DECIDIDA, AlertState.APROBADA if approved else AlertState.RECHAZADA]
            if approved:
                path.append(AlertState.EJECUTADA)
            for step in path:
                try:
                    alert.advance_to(step)
                except InvalidTransition:
                    continue  # already past this state: fine
            self.alerts.update(alert)
        except Exception:  # noqa: BLE001
            pass

    def _remember(self, p: Proposal) -> None:
        if self.memory is None:
            return
        case = self.cases.get(p.case_id)
        parts = p.issue_id.split("|")
        kind, key = (parts[1], parts[2]) if len(parts) >= 3 else ("issue", p.issue_id)
        when = case.sim_today.isoformat() if case else ""
        verdict = "APPROVED" if p.status == "approved" else "REJECTED"
        cat = (f"Reason category: {p.reason_category} (confidence {p.reason_confidence:.2f}). "
               if p.reason_category else "")
        text = (f"[{p.store_id} · {kind} · {key} · {when}] {p.action_type} {verdict}. {p.reason or 'no reason given'}. {cat}"
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
                                   "note": "Backtest of the per-SKU service-level reorder policy, decided with data up to the supplier lead time before each day and scored on that day. Estimates, not a guarantee: supply is assumed to hit the target exactly (no case rounding, no minimum order value)."}
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


_ENTRY_KINDS = {"user_message": "message", "agent_message": "message", "reasoning": "message",
                "compaction": "message", "knowledge_hit": "message", "peer_exchange": "message",
                "tool_call": "tool_call", "tool_result": "tool_result", "policy_denial": "escalation",
                "pending_request": "escalation", "human_decision": "escalation"}
_SUMMARY_MAX = 300


def _clip(value: Any, limit: int = _SUMMARY_MAX) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + "…"


def _message_text(payload: dict[str, Any]) -> str:
    """Core message payloads carry `content` (a string or a list of parts) or `text`/`summary`."""
    content = payload.get("content", payload.get("text", payload.get("summary", "")))
    if isinstance(content, list):
        content = " ".join(str(p.get("text", "")) if isinstance(p, dict) else str(p) for p in content).strip()
    if isinstance(content, str) and content.startswith('{"kind"'):
        content = _envelope_text(content)
    return content if isinstance(content, str) else _clip(content)


def _envelope_text(raw: str) -> str:
    """Older transcript rows store the serialized model envelope {"kind", "parts": [{"content"}]}: keep its text."""
    try:
        env = json.loads(raw)
    except ValueError:
        return raw
    parts = env.get("parts") if isinstance(env, dict) else None
    if not isinstance(parts, list):
        return raw
    texts = [str(p.get("content")) for p in parts if isinstance(p, dict) and isinstance(p.get("content"), str)]
    return "\n".join(texts) if texts else raw


def _events_from_entry(case: Case, entry: dict[str, Any]) -> list[TraceEvent]:
    """One Core transcript entry -> trace events with the keys the UIs read: `text` for messages,
    `tool` (+ `args` / `result` summary) for tool activity, agents as canonical short ids."""
    raw = str(entry.get("kind", "message"))
    kind = _ENTRY_KINDS.get(raw, "message")
    payload = dict(entry.get("payload") or {})
    ts = datetime.fromisoformat(str(entry["at"]))
    eid = str(entry.get("entry_id") or new_id())
    turn = {"turn_id": str(entry["turn_id"])} if entry.get("turn_id") else {}
    mk = lambda frm, to, body, suffix="": TraceEvent(  # noqa: E731
        case.case_id, case.store_id, ts, canonical_agent_id(frm), canonical_agent_id(to), kind,
        {"core_kind": raw, **turn, **body}, event_id=eid + suffix)

    if raw == "peer_exchange":
        target = str(payload.get("target_agent_id") or "agent")
        out = [mk("orchestrator", target, {"text": _clip(payload.get("question") or "", 2000),
                                           "hop": payload.get("hop")}, ":q")]
        if payload.get("answer"):
            out.append(TraceEvent(case.case_id, case.store_id, ts + timedelta(milliseconds=1),
                                  canonical_agent_id(target), "orchestrator", "message",
                                  {"core_kind": raw, **turn, "text": _clip(payload["answer"], 2000)}, event_id=eid + ":a"))
        return out
    if raw in ("tool_call", "policy_denial", "tool_result"):
        tool = str(payload.get("tool") or payload.get("tool_name") or "")
        body: dict[str, Any] = {"tool": tool}
        if "arguments" in payload:
            body["args"] = payload["arguments"]
        if "result" in payload:
            body["result"] = _clip(payload["result"])
        if payload.get("effect"):
            body["effect"] = payload["effect"]
        if raw == "tool_result":
            return [mk("backend", "orchestrator", body)]
        target = "backend"
        if tool == "ask_peer":
            target = str((payload.get("arguments") or {}).get("agent_id")
                         or (payload.get("arguments") or {}).get("target_agent_id") or "backend")
        return [mk("orchestrator", target, body)]
    if raw == "user_message":
        return [mk("manager", "orchestrator", {"text": _message_text(payload)})]
    if kind == "escalation":  # pending_request, human_decision
        return [mk("orchestrator", "manager", {"text": _clip(payload), **{k: v for k, v in payload.items()
                                                                           if k in ("kind", "approved", "note")}})]
    return [mk("orchestrator", "manager", {"text": _message_text(payload)})]


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
            for event in _events_from_entry(case, entry):
                self.trace.record(event)


class RecordEvent:
    def __init__(self, cases: CaseRepository, trace: TracePort, clock: Clock) -> None:
        self.cases, self.trace, self.clock = cases, trace, clock

    def execute(self, case_id: str, from_agent: str, to_agent: str, kind: str, payload: dict[str, Any]) -> TraceEvent:
        case = _case(self.cases, case_id)
        event = TraceEvent(case.case_id, case.store_id, self.clock.now(), canonical_agent_id(from_agent),
                           canonical_agent_id(to_agent), kind, payload)
        self.trace.record(event)
        return event


# metric -> (definition, formula, kpi keys that feed it). Values come from MetricsPort.kpis, never recomputed here.
METRIC_CATALOG: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "net_sales": ("Net sales revenue in the window, after discounts and returns.", "sum(net_sales)", ()),
    "units": ("Units sold in the window.", "sum(units_sold)", ()),
    "transactions": ("Number of completed sales transactions.", "sum(transactions)", ()),
    "footfall": ("Visitors counted entering the store.", "sum(footfall)", ()),
    "conversion": ("Share of visitors who bought something, using only days with a valid footfall counter.",
                   "sum(transactions) / sum(footfall) over days with conversion_valid",
                   ("transactions", "footfall")),
    "tx_per_staff_hour": ("Transactions handled per staffed hour: labour productivity.",
                          "sum(transactions) / sum(staff_hours)", ("transactions",)),
    "waste_usd": ("Cost of product written off as waste in the window.", "sum(waste_cost)", ()),
    "stockout_hours": ("Hours a SKU was out of stock while the store was open.", "sum(stockout_hours)", ()),
}


class ExplainMetric:
    """Definition, formula, value and inputs of one metric over the case window (last 7 days up to as_of)."""

    WINDOW_DAYS = 7

    def __init__(self, cases: CaseRepository, metrics: MetricsPort) -> None:
        self.cases, self.metrics = cases, metrics

    def execute(self, case_id: str, metric: str) -> dict[str, Any]:
        if metric not in METRIC_CATALOG:
            raise DomainError(f"unknown metric {metric!r}; known: {', '.join(METRIC_CATALOG)}")
        case = _case(self.cases, case_id)
        end = case.sim_today
        start = end - timedelta(days=self.WINDOW_DAYS - 1)
        kpis = self.metrics.kpis(case.store_id, case.sim_today, start, end)
        definition, formula, inputs = METRIC_CATALOG[metric]
        return {"metric": metric, "definition": definition, "formula": formula, "value": kpis.get(metric),
                "inputs": {k: kpis.get(k) for k in inputs},
                "window": {"date_from": start.isoformat(), "date_to": end.isoformat()}}
