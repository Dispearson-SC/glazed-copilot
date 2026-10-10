"""Internal API /internal/v1/* for Agent-Core tools.

The store and the as-of date are never parameters: they come from the case named in X-Glazed-Case.
"""

from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from ... import application as uc
from ...domain import Case, DomainError, canonical_agent_id, case_id_from_session


class ProposalBody(BaseModel):
    issue_id: str
    option_id: str | None = None
    action_type: str
    params: dict[str, Any] = {}
    tier: str = "N2"  # agents do not pick the approval tier; the manager always decides
    rationale: str = ""


class EventBody(BaseModel):
    """Either a trace event (from/to/kind/payload) or the Core `record_event` tool shape
    (type/date_from/date_to/note), attributed to the calling agent."""
    from_agent: str | None = None
    to_agent: str | None = None
    kind: str = "message"
    payload: dict[str, Any] = {}
    type: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    note: str = ""


def build_internal_router(c: Any) -> APIRouter:
    r = APIRouter(prefix="/internal/v1")

    def case_ctx(x_glazed_case: Annotated[str | None, Header()] = None) -> Case:
        if not x_glazed_case:
            raise DomainError("X-Glazed-Case header is required")
        key = case_id_from_session(x_glazed_case)  # peer~<case>~<uuid> -> <case>
        case = c.cases.get(key) or c.cases.get_by_conversation(key)
        if case is None:
            raise DomainError(f"X-Glazed-Case {x_glazed_case!r} does not match any case")
        return case

    Ctx = Annotated[Case, Depends(case_ctx)]

    @r.get("/kpis")
    def kpis(case: Ctx, date_from: date | None = None, date_to: date | None = None):
        end = date_to or case.sim_today
        return c.metrics.kpis(case.store_id, case.sim_today, date_from or end - timedelta(days=6), end)

    @r.get("/day-summary")
    def day_summary(case: Ctx, date: date | None = None):
        return uc.GetDaySummary(c.cases, c.metrics).execute(case.case_id, date)

    @r.get("/issues")
    def issues(case: Ctx, limit: int = 5):
        return c.metrics.issues(case.store_id, case.sim_today, max(1, min(limit, 20)))

    @r.get("/inventory/projection")
    def projection(case: Ctx, sku: str, horizon: int = 7):
        return c.metrics.inventory_projection(case.store_id, case.sim_today, sku, max(1, min(horizon, 30)))

    @r.get("/order-plan")
    def order_plan(case: Ctx):
        return c.metrics.order_plan(case.store_id, case.sim_today)

    @r.get("/suppliers/performance")
    def suppliers(case: Ctx):
        return c.metrics.supplier_performance(case.store_id, case.sim_today)

    @r.get("/promos/{promo_id}/evaluation")
    def promo(case: Ctx, promo_id: str):
        return c.metrics.promo_evaluation(case.store_id, case.sim_today, promo_id)

    @r.get("/history")
    def history(case: Ctx):
        return c.metrics.history(case.store_id, case.sim_today)

    @r.get("/experiences")
    def experiences(case: Ctx, response: Response, query: str = "", limit: int = 5):
        found, warning = uc.RecallExperiences(getattr(c, "memory", None)).execute(
            case.store_id, query, max(1, min(limit, 20)))
        if warning:
            response.headers["X-Glazed-Warning"] = warning.replace("\n", " ")[:200]
        return [{"text": e.text, "decision_id": e.decision_id, "kind": e.kind,
                 "created_at": e.created_at.isoformat(), "score": e.score} for e in found]

    @r.post("/proposals", status_code=201)
    def post_proposal(case: Ctx, b: ProposalBody, x_glazed_agent: Annotated[str | None, Header()] = None):
        return jsonable_encoder(uc.SubmitProposal(c.cases, c.proposals).execute(
            case.case_id, b.issue_id, b.action_type, {**b.params, **({"option_id": b.option_id} if b.option_id else {})},
            b.tier, b.rationale, canonical_agent_id(x_glazed_agent or "")))

    @r.post("/events", status_code=201)
    def post_event(case: Ctx, b: EventBody, x_glazed_agent: Annotated[str | None, Header()] = None):
        payload = dict(b.payload)
        if b.type:  # Core record_event tool shape
            payload = {"text": f"{b.type} {b.date_from}..{b.date_to}: {b.note}".strip(": "), "type": b.type,
                       "date_from": b.date_from, "date_to": b.date_to, "note": b.note, **payload}
        return jsonable_encoder(uc.RecordEvent(c.cases, c.trace, c.clock).execute(
            case.case_id, b.from_agent or x_glazed_agent or "agent", b.to_agent or "orchestrator", b.kind, payload))

    return r
