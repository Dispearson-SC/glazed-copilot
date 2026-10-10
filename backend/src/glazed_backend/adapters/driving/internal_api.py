"""Internal API /internal/v1/* for Agent-Core tools.

The store and the as-of date are never parameters: they come from the case named in X-Glazed-Case.
"""

from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from ... import application as uc
from ...application import copilot as uc_copilot, forecast as uc_forecast, manager as uc_manager, sentinel
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


class PromoAuditBody(BaseModel):
    """A proposed promotion template: department plus discount percentage."""
    department: str
    discount_pct: float


class ClassifyBody(BaseModel):
    kind: str  # rejection_reason | deviation_cause
    text: str


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

    @r.get("/snapshot")
    def snapshot(case: Ctx):
        """Everything a specialist usually needs in one call (KPIs, top issues, order plan, suppliers, decisions)."""
        return jsonable_encoder(c.briefings.snapshot(case))

    @r.get("/briefing")
    def briefing(case: Ctx):
        """Precomputed snapshot plus code-computed headline facts: answers simple questions without a specialist."""
        return jsonable_encoder(c.briefings.briefing(case))

    @r.get("/metrics/explain")
    def explain(case: Ctx, metric: str):
        return uc.ExplainMetric(c.cases, c.metrics).execute(case.case_id, metric)

    @r.get("/day-summary")
    def day_summary(case: Ctx, date: date | None = None):
        return names.tag(uc.GetDaySummary(c.cases, c.metrics).execute(case.case_id, date), case.store_id)

    @r.get("/issues")
    def issues(case: Ctx, limit: int = 5, kind: str | None = None, category: str | None = None):
        """Default: operational issues only (integrity never crowds out alerts). `kind=` filters by kind;
        `category=integrity` returns integrity issues only; `category=all` returns both, ranked by
        severity_usd (operational) / exposure_usd (integrity)."""
        return uc_manager.select_issues(c.metrics, names, c.served, case, limit, kind, category)

    @r.get("/issues/{issue_id}/analysis")
    def issue_analysis(case: Ctx, issue_id: str):
        """Deterministic Spanish analysis of one issue; the same use case as the public route."""
        return uc_copilot.IssueAnalysis(c.cases, c.alerts, c.metrics, c.served, names).execute(case, issue_id)

    def own_case(case: Case, store_id: str | None, as_of: date | None) -> None:
        """store_id and as_of are accepted only as assertions: they may never move the read away from the case."""
        if store_id is not None and store_id != case.store_id:
            raise DomainError("store_id does not match the case's store; it comes from X-Glazed-Case")
        if as_of is not None and as_of != case.sim_today:
            raise DomainError("as_of does not match the case date; it comes from X-Glazed-Case")

    @r.get("/forecast")
    def forecast_series(case: Ctx, metric: str = "net_sales", level: str | None = "store",
                        date_from: Annotated[date | None, Query(alias="from")] = None,
                        date_to: Annotated[date | None, Query(alias="to")] = None,
                        store_id: str | None = None, as_of: date | None = None):
        """Store forecast series of one metric (net_sales, transactions, footfall, avg_ticket, conversion); the same
        use case as the public /cases/{id}/forecast?metric=."""
        own_case(case, store_id, as_of)
        return uc_forecast.StoreMetricForecast(c.cases, c.metrics, c.forecasters, c.flow_forecaster, names).execute(
            case.case_id, metric, date_from, date_to, level)

    @r.get("/forecast/demand")
    def forecast_demand(case: Ctx, sku: str, target_date: date, store_id: str | None = None, as_of: date | None = None):
        """p50 and quantiles of one SKU's units on a future day (> the case date), from the forecast model."""
        own_case(case, store_id, as_of)
        return uc_forecast.DemandForecast(c.metrics, c.forecasters).execute(case, sku, target_date)

    @r.get("/forecast/flow")
    def forecast_flow(case: Ctx, target_date: date, store_id: str | None = None, as_of: date | None = None):
        """Store transactions, footfall and average ticket on a future day (> the case date)."""
        own_case(case, store_id, as_of)
        return uc_forecast.FlowForecast(c.metrics, c.flow_forecaster).execute(case, target_date)

    @r.get("/inventory")
    def inventory(case: Ctx, sort: str | None = None, limit: int | None = None, store_id: str | None = None,
                  as_of: date | None = None):
        """Stock, cover, turnover and slow movers; the same use case as the public /cases/{id}/inventory."""
        own_case(case, store_id, as_of)
        return uc_manager.InventoryView(c.metrics, names).execute(case, sort, limit)

    @r.get("/expiring")
    def expiring(case: Ctx, days: int | None = None, limit: int | None = None, store_id: str | None = None,
                 as_of: date | None = None):
        """Lots about to expire (inferred ages) with waste as a USD range; the same use case as the public route."""
        own_case(case, store_id, as_of)
        return uc_manager.ExpiringView(c.metrics, names).execute(case, days, limit)

    @r.get("/deliveries")
    def deliveries(case: Ctx, days: int | None = None, store_id: str | None = None, as_of: date | None = None):
        """Open purchase orders and scheduled supplier slots; the same use case as the public route."""
        own_case(case, store_id, as_of)
        return uc_manager.DeliveriesView(c.metrics, names).execute(case, days)

    @r.get("/staffing")
    def staffing(case: Ctx, days: int | None = None, store_id: str | None = None, as_of: date | None = None):
        """Recommended staff hours per future day from the flow forecast; the same use case as the public route."""
        own_case(case, store_id, as_of)
        return uc_manager.StaffingView(c.metrics, names, c.flow_forecaster).execute(case, days)

    @r.get("/outlook")
    def outlook(case: Ctx, days: int | None = None, store_id: str | None = None, as_of: date | None = None):
        """Next days: sales, transactions, ticket, expected waste and lost sales as ranges; same use case as the public route."""
        own_case(case, store_id, as_of)
        return uc_manager.OutlookView(c.metrics, names, c.forecasters, c.flow_forecaster).execute(case, days)

    @r.get("/inventory/projection")
    def projection(case: Ctx, sku: str, horizon: int = 7):
        return uc_manager.inventory_projection(c.metrics, case, sku, horizon)

    @r.get("/order-plan")
    def order_plan(case: Ctx):
        return names.tag(c.metrics.order_plan(case.store_id, case.sim_today), case.store_id)

    @r.get("/suppliers/performance")
    def suppliers(case: Ctx):
        return c.metrics.supplier_performance(case.store_id, case.sim_today)

    @r.get("/promos")
    def promos(case: Ctx, status: str | None = None, days: int | None = None, limit: int | None = None,
               store_id: str | None = None, as_of: date | None = None):
        """Promotions (active, upcoming, past) with audit verdict and evaluation; the same use case as the public route."""
        own_case(case, store_id, as_of)
        return uc_manager.PromosView(c.metrics, names).execute(case, status, days, limit)

    @r.get("/promos/{promo_id}/evaluation")
    def promo(case: Ctx, promo_id: str):
        return c.metrics.promo_evaluation(case.store_id, case.sim_today, promo_id)

    @r.post("/promos/audit")
    def promo_audit(case: Ctx, b: PromoAuditBody):
        return c.metrics.promo_audit(case.store_id, case.sim_today, b.department, b.discount_pct)

    @r.post("/classify")
    def classify(b: ClassifyBody):
        """Free text -> closed label (Jev). No case needed: nothing here reads store data."""
        from ..driven.classifiers import ChainClassifier
        from ...ports.classifier import ClassifierError, labels_for
        try:
            labels_for(b.kind)
        except ClassifierError as exc:
            raise DomainError(str(exc)) from exc
        if not b.text.strip():
            raise DomainError("text is required")
        clf = getattr(c, "classifier", None) or ChainClassifier([])
        return clf.classify(b.kind, b.text).as_dict()

    @r.get("/compliance")
    def compliance(case: Ctx, decision_id: str | None = None):
        chk = sentinel.CheckCompliance(c.cases, c.proposals, c.executions, c.metrics, c.trace)
        return jsonable_encoder(chk.one(case.case_id, decision_id) if decision_id else chk.for_case(case.case_id))

    @r.get("/history")
    def history(case: Ctx, weeks: int | None = None):
        chk = sentinel.CheckCompliance(c.cases, c.proposals, c.executions, c.metrics, c.trace)
        return uc_manager.case_history(c.metrics, chk, case, weeks)

    @r.get("/experiences")
    def experiences(case: Ctx, response: Response, query: str = "", limit: int = 5):
        found, warning = uc.RecallExperiences(getattr(c, "memory", None)).execute(
            case.store_id, query, max(1, min(limit, 20)))
        if warning:
            response.headers["X-Glazed-Warning"] = warning.replace("\n", " ")[:200]
        def verify(e: Any) -> dict[str, str] | None:
            """How the Past agent re-checks a memory before citing a number from it."""
            if e.ref and e.ref.startswith("PR"):
                return {"tool": "evaluate_promo", "promo_id": e.ref}
            return {"tool": "history", "decision_id": e.decision_id} if e.decision_id else None
        def origin(e: Any) -> str | None:
            p = c.proposals.get(e.decision_id) if e.decision_id else None
            return p.case_id if p is not None and p.store_id == case.store_id else None
        # store memory spans every case of the store: say which case a memory came from (when known)
        return [{"text": e.text, "decision_id": e.decision_id, "ref": e.ref, "kind": e.kind,
                 "created_at": e.created_at.isoformat(), "score": e.score, "verify": verify(e),
                 "scope": "store_memory", "case_id": origin(e), "same_case": origin(e) == case.case_id}
                for e in found]

    @r.post("/proposals", status_code=201)
    def post_proposal(case: Ctx, b: ProposalBody, response: Response,
                      x_glazed_agent: Annotated[str | None, Header()] = None,
                      idempotency_key: Annotated[str | None, Header()] = None):
        proposal, created = uc.ProposeOption(c.cases, c.proposals, c.alerts, c.metrics, c.served).execute_keyed(
            case.case_id, b.issue_id, b.option_id, b.rationale, canonical_agent_id(x_glazed_agent or ""),
            idempotency_key)
        if not created:
            response.status_code = 200  # replay of an earlier request: the original proposal
        return jsonable_encoder(proposal)

    @r.post("/events", status_code=201)
    def post_event(case: Ctx, b: EventBody, x_glazed_agent: Annotated[str | None, Header()] = None):
        payload = dict(b.payload)
        if b.type:  # Core record_event tool shape
            payload = {"text": f"{b.type} {b.date_from}..{b.date_to}: {b.note}".strip(": "), "type": b.type,
                       "date_from": b.date_from, "date_to": b.date_to, "note": b.note, **payload}
        return jsonable_encoder(uc.RecordEvent(c.cases, c.trace, c.clock).execute(
            case.case_id, b.from_agent or x_glazed_agent or "agent", b.to_agent or "orchestrator", b.kind, payload))

    return r
