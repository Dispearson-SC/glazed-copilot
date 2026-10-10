"""Manager notes: free text from the manager ("hoy se venderá menos porque cierran la calle") turned by code into a
local "eventos" memory, a Backboard experience (best effort) and an operational event of the case.

Code does every write; the agent only forwards the text. Store and as-of come from the case, never from the body."""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any
from uuid import uuid4

from ..domain import Case, DecisionMemory, DomainError, Experience, TraceEvent, canonical_agent_id
from .scope import in_scope

log = logging.getLogger(__name__)

NOTE_EVENT = "nota_gerente"
NOTE_CATEGORIES = ("eventos", "demanda", "proveedores", "preferencias")
NOTE_IMPACTS = ("menos_venta", "mas_venta", "otro")
MAX_TEXT = 500


def _day(raw: Any) -> date | None:
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


class ManagerNotes:
    def __init__(self, cases: Any, trace: Any, decision_memories: Any, memory: Any, clock: Any) -> None:
        self.cases, self.trace, self.decision_memories, self.memory, self.clock = cases, trace, decision_memories, memory, clock

    def add(self, case: Case, text: str, category: str = "eventos", date_from: date | None = None,
            date_to: date | None = None, impact: str | None = None) -> dict[str, Any]:
        text = (text or "").strip()
        if not text:
            raise DomainError("text is required")
        if len(text) > MAX_TEXT:
            raise DomainError(f"text must be at most {MAX_TEXT} characters")
        if category not in NOTE_CATEGORIES:
            raise DomainError(f"category must be one of {', '.join(NOTE_CATEGORIES)}")
        if impact is not None and impact not in NOTE_IMPACTS:
            raise DomainError(f"impact must be one of {', '.join(NOTE_IMPACTS)}")
        start = date_from or case.sim_today
        end = date_to or (case.sim_today if date_from is None else start)
        if end < start:
            raise DomainError("date_to must not precede date_from")
        now: datetime = self.clock.now()
        memory_id = f"note-{uuid4().hex[:12]}"
        payload = {"text": f"{NOTE_EVENT} {start}..{end}: {text}", "type": NOTE_EVENT, "date_from": start.isoformat(),
                   "date_to": end.isoformat(), "note": text, "source": "gerente", "category": category,
                   "impact": impact, "memory_id": memory_id}
        event = TraceEvent(case.case_id, case.store_id, now, canonical_agent_id("manager"), canonical_agent_id("sentinel"), "message", payload)
        self.trace.record(event)  # (c) operational event: compliance and deviation explanations cite it
        self.decision_memories.add(DecisionMemory(  # (a) local memory row, always saved
            memory_id, case.store_id, case.case_id, event.event_id, category, text, None, None, None, now,
            impact or "", case.sim_today))
        if self.memory is not None:  # (b) Backboard, best effort
            try:
                self.memory.remember(case.store_id, Experience(
                    f"Nota del gerente ({start} a {end}): {text}", "note", case.store_id, event.event_id, now, ref=memory_id))
            except Exception:  # noqa: BLE001 - memory problems never lose the note
                log.warning("note %s was not stored in Backboard", memory_id, exc_info=True)
        return {"saved": True, "memory_id": memory_id, "event_id": event.event_id, "category": category,
                "date_from": start.isoformat(), "date_to": end.isoformat()}

    def _events(self, case: Case) -> list[dict[str, Any]]:
        owners = {c.case_id: c for c in self.cases.list(case.store_id)}
        out = []
        for e in self.trace.list(store_id=case.store_id):
            p = e.payload or {}
            if p.get("type") != NOTE_EVENT or not in_scope(case, e.case_id, owners):
                continue
            a, b = _day(p.get("date_from")), _day(p.get("date_to") or p.get("date_from"))
            if a is None or b is None:
                continue
            out.append({"memory_id": p.get("memory_id"), "event_id": e.event_id, "text": p.get("note", ""),
                        "category": p.get("category") or "eventos", "impact": p.get("impact"), "date_from": a.isoformat(),
                        "date_to": b.isoformat(), "created_at": e.ts.isoformat(), "case_id": e.case_id})
        return sorted(out, key=lambda n: n["created_at"], reverse=True)

    def active(self, case: Case) -> list[dict[str, Any]]:
        """Notes whose date range covers the case's day (date_from <= as_of <= date_to)."""
        day = case.sim_today.isoformat()
        return [n for n in self._events(case) if n["date_from"] <= day <= n["date_to"]]

    def known(self, case: Case) -> list[dict[str, Any]]:
        """Notes the case may cite: written on or before its day (no look-ahead)."""
        day = case.sim_today.isoformat()
        return [n for n in self._events(case) if n["date_from"] <= day]
