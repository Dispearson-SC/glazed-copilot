"""Close the loop (R2): measure approved decisions as the simulated clock advances, persist the outcome and keep it as a
verified memory. Reads data up to the case's simulated day only."""
from __future__ import annotations

from typing import Any

from ..domain import DecisionMemory, Experience, Outcome, utcnow
from ..metrics.memory_view import category_of
from ..metrics.outcomes import outcome_text


class MeasureOutcomes:
    def __init__(self, proposals: Any, checker: Any, outcomes: Any, decision_memories: Any = None, memory: Any = None,
                 clock: Any = None, names: Any = None) -> None:
        self.proposals, self.checker, self.outcomes = proposals, checker, outcomes
        self.decision_memories, self.memory, self.clock, self.names = decision_memories, memory, clock, names

    def execute(self, case: Any) -> list[dict[str, Any]]:
        """Outcomes created or updated by this call (a final one is measured once and never repeated)."""
        events = self.checker.events(case.store_id)
        out = []
        for p in self.proposals.list(case_id=case.case_id, status="approved"):
            stored = self.outcomes.get(p.proposal_id)
            if stored is not None and stored.complete:
                continue
            payload = self.checker.measure(p, case.sim_today, events)
            if payload is None or (stored is not None and stored.payload.get("measured_as_of") == payload["measured_as_of"]):
                continue
            self.outcomes.add(Outcome(p.proposal_id, p.case_id, p.store_id, case.sim_today, payload["complete"], payload,
                                      self.clock.now() if self.clock else utcnow()))
            if payload["complete"]:
                self._remember(p, case, payload)
            out.append(payload)
        return out

    def _remember(self, p: Any, case: Any, payload: dict[str, Any]) -> None:
        """A verified memory (shown by the memories route) and a Backboard experience agents can recall; best effort."""
        parts = p.issue_id.split("|")
        product = (payload.get("sku") or p.issue_id)
        text = outcome_text(payload, product)
        if self.decision_memories is not None:
            try:
                self.decision_memories.add(DecisionMemory(
                    f"out-{p.proposal_id}", p.store_id, p.case_id, p.proposal_id,
                    category_of(p.action_type, None, parts[1] if len(parts) > 2 else None), text, None, p.action_type,
                    p.params.get("sku"), self.clock.now() if self.clock else utcnow(), "", case.sim_today))
            except Exception:  # noqa: BLE001 - never blocks the advance
                pass
        if self.memory is not None:
            try:
                self.memory.remember(p.store_id, Experience(text, "outcome", p.store_id, p.proposal_id))
            except Exception:  # noqa: BLE001
                pass
