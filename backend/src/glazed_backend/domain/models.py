"""Pure domain model. No I/O, no framework."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

ACTION_TYPES = frozenset({
    "place_order", "adjust_order_qty", "skip_order", "markdown_end_of_day",
    "run_promo", "transfer_stock", "shift_staff_hours", "data_fix_task", "do_nothing",
})
TIERS = ("N0", "N1", "N2", "N3")
CASE_MODES = ("live", "sandbox", "backtest")
EXECUTION_SOURCES = ("simulated", "demo_injected", "operational")
EXECUTION_STATUSES = ("executed", "not_executed", "partial")
TRACE_KINDS = ("message", "tool_call", "tool_result", "escalation")
AGENT_IDS = ("orchestrator", "present", "past", "supply", "strategist", "sentinel", "auditor", "liaison")


def case_id_from_session(session_id: str) -> str:
    """Peer sessions are named `peer~<asker session id>~<uuid>` by the Core worker; the asker is the case."""
    parts = session_id.split("~")
    return parts[1] if len(parts) == 3 and parts[0] == "peer" and parts[1] else session_id


def canonical_agent_id(agent_id: str) -> str:
    """Agent-Core profile ids are `glazed_<role>`; the product (trace, frontend lanes, CLI) uses `<role>`.
    Anything else (the manager, `backend`, unknown ids) keeps its id."""
    role = agent_id.removeprefix("glazed_")
    return role if role in AGENT_IDS else agent_id


_KIND_TO_ALERT_TYPE = {
    "expiring": 1, "overstock_waste": 1, "stockout_risk": 2, "staffing": 3,
    "min_order": 5, "inflated_order": 5, "misleading_promo": 7, "calendar_uplift": 19,
    "sku_key_mismatch": 9, "orphan_sku": 9, "compliance_deviation": 21, "short_shipment": 8, "promo": 7,
    "late_delivery": 20, "supplier_variability": 20,
}


class DomainError(ValueError):
    pass


class InvalidTransition(DomainError):
    pass


class NotFound(DomainError):
    pass


class FutureDate(DomainError):
    """A read tried to go past the case's as_of date."""


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def alert_type_for_kind(kind: str) -> int:
    return _KIND_TO_ALERT_TYPE.get(kind, 2)


@dataclass
class Case:
    case_id: str
    store_id: str
    sim_today: date
    mode: str
    parent_case_id: str | None
    core_conversation_id: str | None
    title: str
    created_at: datetime
    issue_key: str | None = None

    @classmethod
    def new(cls, store_id: str, sim_today: date, mode: str = "live", title: str = "",
            parent_case_id: str | None = None, issue_key: str | None = None) -> "Case":
        if mode not in CASE_MODES:
            raise DomainError(f"invalid mode {mode!r}; expected one of {CASE_MODES}")
        return cls(new_id(), store_id, sim_today, mode, parent_case_id, None,
                   title or f"{store_id} {sim_today.isoformat()}", utcnow(), issue_key)


@dataclass
class Proposal:
    proposal_id: str
    case_id: str
    store_id: str
    issue_id: str
    action_type: str
    params: dict[str, Any]
    tier: str
    rationale: str
    status: str = "pending"
    reason: str = ""
    agent_id: str = ""
    created_at: datetime = field(default_factory=utcnow)
    reason_category: str | None = None  # Jev label of a rejection reason
    reason_confidence: float | None = None
    idempotency_key: str | None = None  # client retry key, unique per case

    @classmethod
    def new(cls, case_id: str, store_id: str, issue_id: str, action_type: str,
            params: dict[str, Any], tier: str, rationale: str, agent_id: str = "") -> "Proposal":
        if action_type not in ACTION_TYPES:
            raise DomainError(f"action_type {action_type!r} not in the closed list")
        if tier not in TIERS:
            raise DomainError(f"tier {tier!r} must be one of {TIERS}")
        return cls(new_id(), case_id, store_id, issue_id, action_type, dict(params), tier,
                   rationale, agent_id=agent_id)

    def decide(self, approved: bool, reason: str) -> None:
        if self.status != "pending":
            raise DomainError(f"proposal already {self.status}")
        if not approved and not reason.strip():
            raise DomainError("a reason is required to reject a proposal")
        self.status = "approved" if approved else "rejected"
        self.reason = reason


@dataclass
class Execution:
    execution_id: str
    proposal_id: str
    case_id: str
    source: str
    status: str
    detail: str = ""
    executed_at: datetime = field(default_factory=utcnow)

    @classmethod
    def new(cls, proposal_id: str, case_id: str, source: str, status: str, detail: str = "") -> "Execution":
        if source not in EXECUTION_SOURCES:
            raise DomainError(f"invalid execution source {source!r}")
        if status not in EXECUTION_STATUSES:
            raise DomainError(f"invalid execution status {status!r}")
        return cls(new_id(), proposal_id, case_id, source, status, detail)


class AlertState(str, Enum):
    NUEVA = "nueva"
    VISTA = "vista"
    EN_ANALISIS = "en_analisis"
    DECIDIDA = "decidida"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"
    EJECUTADA = "ejecutada"
    EN_MEDICION = "en_medicion"
    MEDIDA = "medida"
    POSPUESTA = "pospuesta"
    EXPIRADA = "expirada"
    AUTO_RESUELTA = "auto_resuelta"


_S = AlertState
_OPEN = {_S.NUEVA, _S.VISTA, _S.EN_ANALISIS}
_TRANSITIONS: dict[AlertState, set[AlertState]] = {
    _S.NUEVA: {_S.VISTA, _S.POSPUESTA, _S.EXPIRADA, _S.AUTO_RESUELTA},
    _S.VISTA: {_S.EN_ANALISIS, _S.POSPUESTA, _S.EXPIRADA, _S.AUTO_RESUELTA},
    _S.EN_ANALISIS: {_S.DECIDIDA, _S.POSPUESTA, _S.EXPIRADA, _S.AUTO_RESUELTA},
    _S.DECIDIDA: {_S.APROBADA, _S.RECHAZADA},
    _S.APROBADA: {_S.EJECUTADA},
    _S.EJECUTADA: {_S.EN_MEDICION},
    _S.EN_MEDICION: {_S.MEDIDA},
    _S.RECHAZADA: {_S.MEDIDA},
    _S.POSPUESTA: {_S.VISTA},
    _S.EXPIRADA: set(),
    _S.AUTO_RESUELTA: set(),
    _S.MEDIDA: set(),
}
_MAIN_PATH = [_S.NUEVA, _S.VISTA, _S.EN_ANALISIS, _S.DECIDIDA]


@dataclass
class Alert:
    alert_id: str
    alert_type: int
    store_id: str
    case_id: str
    severity_usd: float
    state: AlertState
    issue: dict[str, Any]
    issue_key: str
    as_of: date
    created_at: datetime

    @classmethod
    def new(cls, alert_type: int, store_id: str, case_id: str, severity_usd: float,
            issue: dict[str, Any], issue_key: str, as_of: date) -> "Alert":
        if not 1 <= alert_type <= 21:
            raise DomainError("alert_type must be in the catalog range 1..20, or 21 (Sentinel compliance)")
        return cls(new_id(), alert_type, store_id, case_id, float(severity_usd), AlertState.NUEVA,
                   issue, issue_key, as_of, utcnow())

    def advance(self, target: AlertState) -> None:
        if target not in _TRANSITIONS[self.state]:
            raise InvalidTransition(f"{self.state.value} -> {target.value} is not allowed")
        self.state = target

    def advance_to(self, target: AlertState) -> None:
        """Walk the main path (nueva..decidida) step by step, then apply `target`."""
        if self.state in _OPEN and target in _MAIN_PATH:
            while self.state != target:
                self.advance(_MAIN_PATH[_MAIN_PATH.index(self.state) + 1])
            return
        self.advance(target)


@dataclass
class BacktestRun:
    run_id: str
    case_id: str
    store_id: str
    period_from: date
    period_to: date
    policy: str
    results: dict[str, Any]
    created_at: datetime = field(default_factory=utcnow)
    label: str = "backtest"


@dataclass
class TraceEvent:
    case_id: str
    store_id: str
    ts: datetime
    from_agent: str
    to_agent: str
    kind: str
    payload: dict[str, Any]
    event_id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if self.kind not in TRACE_KINDS:
            raise DomainError(f"invalid trace kind {self.kind!r}")


class CoreError(DomainError):
    """Agent-Core unreachable or returned an unexpected response."""


class MemoryUnavailable(DomainError):
    """Experience memory is not configured or the provider failed. Callers degrade, never fail."""


@dataclass
class Experience:
    text: str
    kind: str  # decision | outcome | promo_evaluation | ...
    store_id: str
    decision_id: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    score: float | None = None
    ref: str | None = None  # id to re-verify the memory with (a promo id such as PR002)
