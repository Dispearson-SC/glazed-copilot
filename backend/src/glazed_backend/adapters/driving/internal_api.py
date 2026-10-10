"""Internal API /internal/v1/* for Agent-Core tools.

The store and the as-of date are never parameters: they come from the case named in X-Glazed-Case.
"""

from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from ... import application as uc
from ...domain import Case, DomainError


class ProposalBody(BaseModel):
    issue_id: str
    action_type: str
    params: dict[str, Any] = {}
    tier: str
    rationale: str = ""


class EventBody(BaseModel):
    from_agent: str
    to_agent: str
    kind: str = "message"
    payload: dict[str, Any] = {}


def build_internal_router(c: Any) -> APIRouter:
    r = APIRouter(prefix="/internal/v1")

    def case_ctx(x_glazed_case: Annotated[str | None, Header()] = None) -> Case:
        if not x_glazed_case:
            raise DomainError("X-Glazed-Case header is required")
        case = c.cases.get(x_glazed_case) or c.cases.get_by_conversation(x_glazed_case)
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

    @r.post("/proposals", status_code=201)
    def post_proposal(case: Ctx, b: ProposalBody, x_glazed_agent: Annotated[str | None, Header()] = None):
        return jsonable_encoder(uc.SubmitProposal(c.cases, c.proposals).execute(
            case.case_id, b.issue_id, b.action_type, b.params, b.tier, b.rationale, x_glazed_agent or ""))

    @r.post("/events", status_code=201)
    def post_event(case: Ctx, b: EventBody):
        return jsonable_encoder(uc.RecordEvent(c.cases, c.trace, c.clock)
                                .execute(case.case_id, b.from_agent, b.to_agent, b.kind, b.payload))

    return r
