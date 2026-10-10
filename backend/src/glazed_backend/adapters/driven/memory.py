"""In-memory adapters: quick local runs and the fakes used by unit tests."""
from __future__ import annotations

import copy
import dataclasses
from datetime import datetime, timezone

from ...domain import Alert, AlertState, BacktestRun, Case, DecisionMemory, Execution, Proposal, TraceEvent, TurnRecord


class InMemoryCases:
    def __init__(self) -> None:
        self._d: dict[str, Case] = {}

    def add(self, case: Case) -> None:
        self._d[case.case_id] = copy.deepcopy(case)

    update = add

    def get(self, case_id: str) -> Case | None:
        return copy.deepcopy(self._d.get(case_id))

    def get_by_issue_key(self, issue_key: str) -> Case | None:
        return next((copy.deepcopy(c) for c in self._d.values() if c.issue_key == issue_key), None)

    def get_by_conversation(self, conversation_id: str) -> Case | None:
        return next((copy.deepcopy(c) for c in self._d.values() if c.core_conversation_id == conversation_id), None)

    def list(self, store_id: str | None = None) -> list[Case]:
        rows = [c for c in self._d.values() if store_id in (None, c.store_id)]
        return copy.deepcopy(sorted(rows, key=lambda c: c.created_at))


class InMemoryAlerts:
    def __init__(self) -> None:
        self._d: dict[str, Alert] = {}

    def add(self, alert: Alert) -> None:
        self._d[alert.alert_id] = copy.deepcopy(alert)

    update = add

    def get(self, alert_id: str) -> Alert | None:
        return copy.deepcopy(self._d.get(alert_id))

    def get_by_issue_key(self, issue_key: str) -> Alert | None:
        return next((copy.deepcopy(a) for a in self._d.values() if a.issue_key == issue_key), None)

    def list(self, store_id: str | None = None, state: AlertState | None = None) -> list[Alert]:
        rows = [a for a in self._d.values()
                if store_id in (None, a.store_id) and state in (None, a.state)]
        return copy.deepcopy(sorted(rows, key=lambda a: -a.severity_usd))


class InMemoryProposals:
    def __init__(self) -> None:
        self._d: dict[str, Proposal] = {}

    def add(self, proposal: Proposal) -> None:
        self._d[proposal.proposal_id] = copy.deepcopy(proposal)

    update = add

    def get(self, proposal_id: str) -> Proposal | None:
        return copy.deepcopy(self._d.get(proposal_id))

    def find_by_idempotency_key(self, case_id: str, key: str) -> Proposal | None:
        return next((copy.deepcopy(p) for p in self._d.values()
                     if p.case_id == case_id and p.idempotency_key == key), None)

    def list(self, case_id: str | None = None, store_id: str | None = None,
             status: str | None = None) -> list[Proposal]:
        rows = [p for p in self._d.values() if case_id in (None, p.case_id)
                and store_id in (None, p.store_id) and status in (None, p.status)]
        return copy.deepcopy(sorted(rows, key=lambda p: p.created_at))


class InMemoryExecutions:
    def __init__(self) -> None:
        self._rows: list[Execution] = []

    def add(self, execution: Execution) -> None:
        self._rows.append(copy.deepcopy(execution))

    def list(self, case_id: str) -> list[Execution]:
        return copy.deepcopy([e for e in self._rows if e.case_id == case_id])


class InMemoryBacktests:
    def __init__(self) -> None:
        self._d: dict[str, BacktestRun] = {}

    def add(self, run: BacktestRun) -> None:
        self._d[run.run_id] = copy.deepcopy(run)

    def get(self, run_id: str) -> BacktestRun | None:
        return copy.deepcopy(self._d.get(run_id))

    def list(self, case_id: str | None = None) -> list[BacktestRun]:
        return copy.deepcopy([r for r in self._d.values() if case_id in (None, r.case_id)])


class InMemoryTrace:
    def __init__(self) -> None:
        self._rows: dict[str, TraceEvent] = {}

    def record(self, event: TraceEvent) -> None:
        self._rows[event.event_id] = copy.deepcopy(event)

    def list(self, case_id: str | None = None, store_id: str | None = None) -> list[TraceEvent]:
        rows = [e for e in self._rows.values() if case_id in (None, e.case_id) and store_id in (None, e.store_id)]
        return copy.deepcopy(sorted(rows, key=lambda e: e.ts))


class InMemoryTurns:
    def __init__(self) -> None:
        self._d: dict[str, TurnRecord] = {}

    def add(self, turn: TurnRecord) -> None:
        self._d[turn.turn_id] = copy.deepcopy(turn)

    def get(self, turn_id: str) -> TurnRecord | None:
        return copy.deepcopy(self._d.get(turn_id))

    def list(self, case_id: str) -> list[TurnRecord]:
        return copy.deepcopy(sorted((t for t in self._d.values() if t.case_id == case_id), key=lambda t: t.ts))


class InMemoryDecisionMemories:
    def __init__(self) -> None:
        self._d: dict[str, DecisionMemory] = {}

    def add(self, memory: DecisionMemory) -> None:
        self._d[memory.memory_id] = copy.deepcopy(memory)

    def get(self, memory_id: str) -> DecisionMemory | None:
        return copy.deepcopy(self._d.get(memory_id))

    def list(self, store_id: str) -> list[DecisionMemory]:
        return copy.deepcopy(sorted((m for m in self._d.values() if m.store_id == store_id), key=lambda m: m.created_at))


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class InMemoryAssistants:
    def __init__(self) -> None:
        self._d: dict[str, str] = {}

    def get(self, store_id: str) -> str | None:
        return self._d.get(store_id)

    def set(self, store_id: str, assistant_id: str) -> None:
        self._d[store_id] = assistant_id


class InMemoryExperienceMemory:
    """Keyword-overlap recall; isolated per store."""

    def __init__(self) -> None:
        self._d: dict[str, list] = {}

    def remember(self, store_id: str, experience) -> None:
        self._d.setdefault(store_id, []).append(experience)

    def recall(self, store_id: str, query: str, limit: int = 5) -> list:
        words = {w.lower() for w in query.split() if w}
        scored = []
        for e in self._d.get(store_id, []):
            hay = e.text.lower() + " " + e.kind
            s = sum(1 for w in words if w in hay)
            if s or not words:
                scored.append((s, e))
        scored.sort(key=lambda x: -x[0])
        return [dataclasses.replace(e, score=float(s)) for s, e in scored[:limit]]
