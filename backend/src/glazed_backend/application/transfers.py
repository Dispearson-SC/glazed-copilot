"""Inter-store transfers: options computed by code, and the pending proposal for the manager to decide (four eyes)."""
from __future__ import annotations

from typing import Any

from ..domain import Case, DomainError, NotFound, Proposal
from . import ProposeOption

MAX_LIMIT = 20


class TransferOptions:
    def __init__(self, metrics: Any) -> None:
        self.metrics = metrics

    def execute(self, case: Case, sku: str | None = None, limit: int | None = None) -> dict[str, Any]:
        limit = 5 if limit is None else limit
        if not 1 <= limit <= MAX_LIMIT:
            raise DomainError(f"limit must be between 1 and {MAX_LIMIT}")
        return self.metrics.transfer_options(case.store_id, case.sim_today, sku or None, limit)


class ProposeTransfer:
    """A transfer option becomes a pending proposal of its transfer_stock issue; the manager decides it."""

    def __init__(self, cases: Any, proposals: Any, alerts: Any, metrics: Any, served: dict) -> None:
        self.proposals = proposals
        self.metrics = metrics
        self.propose = ProposeOption(cases, proposals, alerts, metrics, served)

    def execute(self, case: Case, option_id: str, rationale: str = "", agent_id: str = "",
                idempotency_key: str | None = None) -> tuple[Proposal, bool]:
        if idempotency_key:
            prior = self.proposals.find_by_idempotency_key(case.case_id, idempotency_key)
            if prior is not None:
                return prior, False
        if not option_id:
            raise DomainError("option_id is required: propose one of the options from transfers/options")
        found = self.metrics.transfer_options(case.store_id, case.sim_today, None, MAX_LIMIT * 50)["options"]
        option = next((o for o in found if o["option_id"] == option_id), None)
        if option is None:
            raise NotFound(f"transfer option {option_id!r} is not available for this case date")
        issue_id = f"{case.store_id}|transfer_opportunity|{option['sku']}"
        return self.propose.execute_keyed(case.case_id, issue_id, option_id, rationale, agent_id, idempotency_key)
