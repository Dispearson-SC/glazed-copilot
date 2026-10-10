"""Public API /api/v1/* for the CLI and the frontend."""

from datetime import date, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, Query, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from ... import application as uc
from ...application import copilot as uc_copilot, decisions as uc_decisions, forecast as uc_forecast, manager as uc_manager, sentinel
from ...domain import AlertState, DomainError, NotFound
from .store_names import StoreNames


class NewCase(BaseModel):
    store_id: str
    sim_today: date
    mode: str = "live"
    title: str = ""


class ForkBody(BaseModel):
    title: str = ""


class AskContext(BaseModel):
    issue_id: str
    option_id: str | None = None
    mode: Literal["analizar", "dialogo"]


class AskBody(BaseModel):
    text: str
    context: AskContext | None = None


class AdvanceBody(BaseModel):
    days: int = 1
    to: date | None = None


class DecisionBody(BaseModel):
    approved: bool
    reason: str = ""


class CaseDecisionBody(BaseModel):
    issue_id: str
    option_id: str
    approved: bool
    reason: str = ""


class BacktestBody(BaseModel):
    date_from: date
    date_to: date
    policy: str = "simple_v0"


class ProposeBody(BaseModel):
    case_id: str
    issue_id: str
    option_id: str
    rationale: str = ""


class OutcomeBody(BaseModel):
    summary: str


class InjectExecutionBody(BaseModel):
    proposal_id: str
    status: str
    detail: str = ""


class InjectEventBody(BaseModel):
    type: str
    date_from: date | None = None
    date_to: date | None = None
    note: str = ""
    proposal_id: str | None = None  # the decision the event refers to; else the latest matching execution
    sku: str | None = None


class InjectBody(BaseModel):
    """Demo only: inject a not_executed/partial execution (source demo_injected) or an event (bloqueo, ...)."""
    execution: InjectExecutionBody | None = None
    event: InjectEventBody | None = None


class PromoAuditBody(BaseModel):
    case_id: str
    department: str
    discount_pct: float


class TransitionBody(BaseModel):
    state: str


def build_public_router(c: Any) -> APIRouter:
    r = APIRouter(prefix="/api/v1")
    names = StoreNames(c.metrics)

    def checker() -> sentinel.CheckCompliance:
        return sentinel.CheckCompliance(c.cases, c.proposals, c.executions, c.metrics, c.trace)

    def case_of(case_id: str) -> Any:
        return uc._case(c.cases, case_id)

    @r.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "storage": c.storage, "core": c.core_status}

    @r.get("/stores")
    def stores():
        return c.metrics.stores()

    @r.post("/cases", status_code=201)
    def create_case(b: NewCase):
        case = uc.StartCase(c.cases).execute(b.store_id, b.sim_today, b.mode, b.title)
        c.briefings.refresh_async(case)
        return names.tag(jsonable_encoder(case))

    @r.get("/cases")
    def list_cases(store_id: str | None = None):
        return names.tag(jsonable_encoder(uc.ListCases(c.cases).execute(store_id)))

    @r.get("/cases/{case_id}")
    def get_case(case_id: str):
        return names.tag(jsonable_encoder(uc.ResumeCase(c.cases).execute(case_id)))

    @r.post("/cases/{case_id}/fork", status_code=201)
    def fork(case_id: str, b: ForkBody | None = None):
        child = uc.ForkCase(c.cases, c.proposals, c.executions).execute(case_id, (b.title if b else ""))
        c.briefings.refresh_async(child)
        return names.tag(jsonable_encoder(child))

    @r.post("/cases/{case_id}/messages", status_code=202)
    def ask(case_id: str, b: AskBody):
        def lookup(case, issue_id):
            return uc_copilot.require_issue(c.alerts, c.metrics, c.served, case, issue_id)
        ctx = b.context.model_dump() if b.context else None
        return {"turn_id": uc.AskAgent(c.cases, c.core, c.turn_tracker, c.clock, c.turns).execute(case_id, b.text, ctx, lookup)}

    def turn_getter() -> uc.GetTurn:
        return uc.GetTurn(c.cases, c.core, c.turn_tracker, c.clock, c.turn_timeout_s, turns=c.turns)

    @r.get("/cases/{case_id}/turns")
    def turn_history(case_id: str):
        return uc.ListTurns(c.cases, c.core, c.turns, turn_getter(), c.turn_tracker).execute(case_id)

    @r.get("/cases/{case_id}/turns/{turn_id}")
    def turn(case_id: str, turn_id: str):
        return turn_getter().execute(case_id, turn_id)

    @r.get("/cases/{case_id}/day-summary")
    def day_summary(case_id: str, date: date | None = None):
        return names.tag(uc.GetDaySummary(c.cases, c.metrics).execute(case_id, date))

    @r.post("/cases/{case_id}/advance")
    def advance(case_id: str, b: AdvanceBody | None = None):
        b = b or AdvanceBody()
        res = uc.AdvanceSimClock(c.cases, c.alerts, c.metrics, compliance=checker()).execute(case_id, b.days, b.to)
        c.briefings.refresh_async(uc.ResumeCase(c.cases).execute(case_id))
        return {"sim_today": res["sim_today"], "new_alerts": names.tag(jsonable_encoder(res["alerts"]))}

    @r.get("/cases/{case_id}/briefing")
    def briefing(case_id: str):
        return jsonable_encoder(c.briefings.briefing(uc.ResumeCase(c.cases).execute(case_id)))

    @r.post("/promos/audit")
    def promo_audit(b: PromoAuditBody):
        case = uc.ResumeCase(c.cases).execute(b.case_id)
        return jsonable_encoder(c.metrics.promo_audit(case.store_id, case.sim_today, b.department, b.discount_pct))

    @r.get("/cases/{case_id}/compliance")
    def compliance(case_id: str):
        return jsonable_encoder(checker().for_case(case_id))

    @r.post("/cases/{case_id}/inject", status_code=201)
    def inject(case_id: str, b: InjectBody):
        if b.execution is None and b.event is None:
            raise DomainError("inject needs an `execution` or an `event`")
        out: dict[str, Any] = {}
        if b.execution is not None:
            out["execution"] = jsonable_encoder(sentinel.InjectExecution(c.cases, c.proposals, c.executions).execute(
                case_id, b.execution.proposal_id, b.execution.status, b.execution.detail))
        if b.event is not None:
            ev = sentinel.InjectEvent(uc.RecordEvent(c.cases, c.trace, c.clock), c.cases, c.proposals, c.executions).execute(
                case_id, b.event.type, b.event.date_from, b.event.date_to, b.event.note, b.event.proposal_id, b.event.sku)
            out["event"] = {**ev.payload, "event_id": ev.event_id}
        return out

    @r.get("/alerts")
    def alerts(store_id: str | None = None, state: str | None = None):
        try:
            st = AlertState(state) if state else None
        except ValueError:
            raise DomainError(f"unknown alert state {state!r}") from None
        return names.tag(jsonable_encoder(uc.ListAlerts(c.alerts).execute(store_id, st)))

    @r.patch("/alerts/{alert_id}")
    def transition(alert_id: str, b: TransitionBody):
        alert = c.alerts.get(alert_id)
        if alert is None:
            raise NotFound(f"alert {alert_id!r} not found")
        try:
            target = AlertState(b.state)
        except ValueError:
            raise DomainError(f"unknown alert state {b.state!r}") from None
        alert.advance(target)
        c.alerts.update(alert)
        return names.tag(jsonable_encoder(alert))

    @r.get("/proposals")
    def proposals(case_id: str | None = None, store_id: str | None = None, status: str | None = None):
        return jsonable_encoder(c.proposals.list(case_id, store_id, status))

    @r.post("/proposals", status_code=201)
    def propose(b: ProposeBody, response: Response, idempotency_key: Annotated[str | None, Header()] = None):
        proposal, created = uc.ProposeOption(c.cases, c.proposals, c.alerts, c.metrics, c.served).execute_keyed(
            b.case_id, b.issue_id, b.option_id, b.rationale, idempotency_key=idempotency_key)
        if not created:
            response.status_code = 200
        return jsonable_encoder(proposal)

    @r.get("/cases/{case_id}/order-plan")
    def order_plan(case_id: str):
        case = uc.ResumeCase(c.cases).execute(case_id)
        plan = c.metrics.order_plan(case.store_id, case.sim_today)
        for line in plan.get("lines", []):
            if line.get("issue"):
                c.served[(case.case_id, line["issue"]["issue_id"])] = line["issue"]
        return names.tag({**plan, "case_id": case.case_id, "store_id": case.store_id})

    @r.get("/cases/{case_id}/kpis")
    def kpis(case_id: str, date_from: date | None = None, date_to: date | None = None):
        case = uc.ResumeCase(c.cases).execute(case_id)
        end = date_to or case.sim_today
        out = c.metrics.kpis(case.store_id, case.sim_today, date_from or end - timedelta(days=6), end)
        return names.tag({**out, "case_id": case.case_id})

    @r.post("/proposals/{proposal_id}/decision")
    def decide(proposal_id: str, b: DecisionBody):
        return jsonable_encoder(uc.DecideProposal(c.cases, c.proposals, c.executions, c.alerts, c.memory, c.classifier)
                                .execute(proposal_id, b.approved, b.reason))

    @r.post("/proposals/{proposal_id}/outcome", status_code=201)
    def outcome(proposal_id: str, b: OutcomeBody):
        return jsonable_encoder(uc.RecordOutcome(c.proposals, c.cases, c.memory).execute(proposal_id, b.summary))

    @r.get("/cases/{case_id}/decisions")
    def decisions(case_id: str, date_from: Annotated[date | None, Query(alias="from")] = None,
                  date_to: Annotated[date | None, Query(alias="to")] = None):
        return uc_decisions.ListDecisions(c.cases, c.proposals, c.executions, checker()).execute(case_id, date_from, date_to)

    @r.get("/cases/{case_id}/decisions/pending")
    def decisions_pending(case_id: str):
        return uc_copilot.PendingDecisions(c.metrics, c.proposals, c.served, names).execute(case_of(case_id))

    @r.post("/cases/{case_id}/decisions", status_code=201)
    def post_decision(case_id: str, b: CaseDecisionBody, response: Response,
                      idempotency_key: Annotated[str | None, Header()] = None):
        out, created = uc_copilot.RecordDecision(c.cases, c.proposals, c.executions, c.alerts, c.metrics, c.served,
                                                 c.memory, c.classifier, getattr(c, "rejections", None), c.clock).execute(
            case_id, b.issue_id, b.option_id, b.approved, b.reason, idempotency_key)
        if not created:
            response.status_code = 200
        return jsonable_encoder(out)

    @r.get("/cases/{case_id}/forecast")
    def forecast(case_id: str, sku: str | None = None, date_from: Annotated[date | None, Query(alias="from")] = None,
                 date_to: Annotated[date | None, Query(alias="to")] = None, level: str | None = None,
                 metric: str | None = None):
        if metric is None:
            return uc_forecast.GetForecast(c.cases, c.metrics, c.forecasters).execute(case_id, sku, date_from, date_to, level)
        return uc_forecast.StoreMetricForecast(c.cases, c.metrics, c.forecasters, c.flow_forecaster, names).execute(
            case_id, metric, date_from, date_to, level, sku)

    @r.get("/cases/{case_id}/forecast/accuracy")
    def forecast_accuracy(case_id: str, by: str | None = None, date_from: Annotated[date | None, Query(alias="from")] = None,
                          date_to: Annotated[date | None, Query(alias="to")] = None):
        return uc_forecast.ForecastAccuracy(c.cases, c.metrics, c.forecasters).execute(case_id, by, date_from, date_to)

    @r.get("/cases/{case_id}/inventory")
    def inventory(case_id: str, sort: str | None = None, limit: int | None = None):
        return uc_manager.InventoryView(c.metrics, names).execute(case_of(case_id), sort, limit)

    @r.get("/cases/{case_id}/expiring")
    def expiring(case_id: str, days: int | None = None, limit: int | None = None):
        return uc_manager.ExpiringView(c.metrics, names).execute(case_of(case_id), days, limit)

    @r.get("/cases/{case_id}/issues")
    def case_issues(case_id: str, limit: int = 5, kind: str | None = None, category: str | None = None):
        return uc_manager.select_issues(c.metrics, names, c.served, case_of(case_id), limit, kind, category)

    @r.get("/cases/{case_id}/issues/{issue_id}/analysis")
    def issue_analysis(case_id: str, issue_id: str):
        return uc_copilot.IssueAnalysis(c.cases, c.alerts, c.metrics, c.served, names).execute(case_of(case_id), issue_id)

    @r.get("/cases/{case_id}/inventory/projection")
    def inventory_projection(case_id: str, sku: str, horizon: int = 7):
        return uc_manager.inventory_projection(c.metrics, case_of(case_id), sku, horizon)

    @r.get("/cases/{case_id}/suppliers/performance")
    def suppliers_performance(case_id: str):
        case = case_of(case_id)
        return c.metrics.supplier_performance(case.store_id, case.sim_today)

    @r.get("/cases/{case_id}/history")
    def case_history(case_id: str, weeks: int | None = None):
        return uc_manager.case_history(c.metrics, checker(), case_of(case_id), weeks)

    @r.get("/cases/{case_id}/deliveries")
    def deliveries(case_id: str, days: int | None = None):
        return uc_manager.DeliveriesView(c.metrics, names).execute(case_of(case_id), days)

    @r.get("/cases/{case_id}/promos")
    def promos(case_id: str, status: str | None = None, days: int | None = None, limit: int | None = None):
        return uc_manager.PromosView(c.metrics, names).execute(case_of(case_id), status, days, limit)

    @r.get("/cases/{case_id}/staffing")
    def staffing(case_id: str, days: int | None = None):
        return uc_manager.StaffingView(c.metrics, names, c.flow_forecaster).execute(case_of(case_id), days)

    @r.get("/cases/{case_id}/executions")
    def executions(case_id: str):
        uc.ResumeCase(c.cases).execute(case_id)
        return jsonable_encoder(c.executions.list(case_id))

    @r.post("/cases/{case_id}/backtests", status_code=201)
    def run_backtest(case_id: str, b: BacktestBody):
        return jsonable_encoder(uc.RunBacktest(c.cases, c.metrics, c.backtests, c.clock)
                                .execute(case_id, b.date_from, b.date_to, b.policy))

    @r.get("/cases/{case_id}/backtests")
    def list_backtests(case_id: str):
        return jsonable_encoder(c.backtests.list(case_id))

    @r.get("/backtests/{run_id}")
    def get_backtest(run_id: str):
        run = c.backtests.get(run_id)
        if run is None:
            raise NotFound(f"backtest {run_id!r} not found")
        return jsonable_encoder(run)

    @r.get("/trace")
    def trace(case_id: str | None = None, store_id: str | None = None):
        if not case_id and not store_id:
            raise DomainError("case_id or store_id is required")
        return jsonable_encoder(uc.GetAgentTrace(c.cases, c.core, c.trace).execute(case_id, store_id))

    return r
