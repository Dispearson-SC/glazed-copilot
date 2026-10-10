"""Internal API /internal/v1/* for Agent-Core tools.

The store and the as-of date are never parameters: they come from the case named in X-Glazed-Case.
"""

from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from ... import application as uc
from .store_names import StoreNames
from ...domain import Case, DomainError, canonical_agent_id, case_id_from_session


class ProposalBody(BaseModel):
    """The agent names an option; action_type/params/tier below are legacy fields that are ignored."""
    issue_id: str
    option_id: str | None = None
    rationale: str = ""
    action_type: str | None = None
    params: dict[str, Any] = {}
    tier: str | None = None


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
    def trace_read(case: Case, request: Request, agent: str | None) -> None:
        """A data read by a named agent shows up in the trace as agent -> backend tool_call."""
        if not agent or request.method != "GET":
            return
        tool = request.url.path.removeprefix("/internal/v1/").strip("/") or "root"
        query = request.url.query
        uc.RecordEvent(c.cases, c.trace, c.clock).execute(
            case.case_id, agent, "backend", "tool_call",
            {"tool": tool, "text": f"{tool}?{query}" if query else tool})

    r = APIRouter(prefix="/internal/v1")
    names = StoreNames(c.metrics)

    def case_ctx(request: Request, x_glazed_case: Annotated[str | None, Header()] = None,
                 x_glazed_agent: Annotated[str | None, Header()] = None) -> Case:
        if not x_glazed_case:
            raise DomainError("X-Glazed-Case header is required")
        key = case_id_from_session(x_glazed_case)  # peer~<case>~<uuid> -> <case>
        case = c.cases.get(key) or c.cases.get_by_conversation(key)
        if case is None:
            raise DomainError(f"X-Glazed-Case {x_glazed_case!r} does not match any case")
        trace_read(case, request, x_glazed_agent)
        return case

    Ctx = Annotated[Case, Depends(case_ctx)]

    @r.get("/kpis")
    def kpis(case: Ctx, date_from: date | None = None, date_to: date | None = None):
        end = date_to or case.sim_today
        return names.tag(c.metrics.kpis(case.store_id, case.sim_today, date_from or end - timedelta(days=6), end), case.store_id)

    @r.get("/metrics/explain")
    def explain(case: Ctx, metric: str):
        return uc.ExplainMetric(c.cases, c.metrics).execute(case.case_id, metric)

    @r.get("/day-summary")
    def day_summary(case: Ctx, date: date | None = None):
        return names.tag(uc.GetDaySummary(c.cases, c.metrics).execute(case.case_id, date), case.store_id)

    @r.get("/issues")
    def issues(case: Ctx, limit: int = 5):
        found = names.tag(c.metrics.issues(case.store_id, case.sim_today, max(1, min(limit, 20))), case.store_id)
        for issue in found:
            c.served[(case.case_id, issue["issue_id"])] = issue
        return found

    @r.get("/inventory/projection")
    def projection(case: Ctx, sku: str, horizon: int = 7):
        return c.metrics.inventory_projection(case.store_id, case.sim_today, sku, max(1, min(horizon, 30)))

    @r.get("/order-plan")
    def order_plan(case: Ctx):
        return names.tag(c.metrics.order_plan(case.store_id, case.sim_today), case.store_id)

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
        return jsonable_encoder(uc.ProposeOption(c.cases, c.proposals, c.alerts, c.metrics, c.served).execute(
            case.case_id, b.issue_id, b.option_id, b.rationale, canonical_agent_id(x_glazed_agent or "")))

    @r.post("/events", status_code=201)
    def post_event(case: Ctx, b: EventBody, x_glazed_agent: Annotated[str | None, Header()] = None):
        payload = dict(b.payload)
        if b.type:  # Core record_event tool shape
            payload = {"text": f"{b.type} {b.date_from}..{b.date_to}: {b.note}".strip(": "), "type": b.type,
                       "date_from": b.date_from, "date_to": b.date_to, "note": b.note, **payload}
        return jsonable_encoder(uc.RecordEvent(c.cases, c.trace, c.clock).execute(
            case.case_id, b.from_agent or x_glazed_agent or "agent", b.to_agent or "orchestrator", b.kind, payload))

    return r
