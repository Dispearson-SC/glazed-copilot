"""Public API /api/v1/* for the CLI and the frontend."""

from datetime import date, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from ... import application as uc
from ...application import copilot as uc_copilot, decisions as uc_decisions, outcomes as uc_outcomes, forecast as uc_forecast, manager as uc_manager, notes as uc_notes, sentinel, transfers as uc_transfers
from ...domain import AlertState, DomainError, NotFound
from ...domain.models import alert_agent, alert_category, public_agent_id
from .auth_api import AuthGuard
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
    voice: bool = False  # push-to-talk message: the Core answers as spoken language


class AdvanceBody(BaseModel):
    days: int = 1
    to: date | None = None


class DecisionBody(BaseModel):
    approved: bool
    reason: str = ""


class NoteBody(BaseModel):
    text: str
    category: str = "eventos"
    date_from: date | None = None
    date_to: date | None = None
    impact: str | None = None


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


def alert_view(alert: Any) -> dict[str, Any]:
    """An alert as the UI reads it: category (operacion|integridad|automatica), owning agent and ts."""
    out = jsonable_encoder(alert)
    kind = (alert.issue or {}).get("kind")
    from glazed_backend.metrics.analysis import _TITLES
    issue = alert.issue or {}
    label = _TITLES.get(kind or "", (kind or "alerta").replace("_", " ").capitalize())
    product = issue.get("product_name") or issue.get("sku") or issue.get("supplier_name") or issue.get("supplier_id")
    return {**out, "category": alert_category(kind, issue.get("category")), "agent_id": public_agent_id(alert_agent(kind)),
            "ts": out["created_at"], "kind_label_es": label,
            "title_es": f"{label}: {product}" if product else label}


def build_public_router(c: Any, guard: AuthGuard) -> APIRouter:
    root = APIRouter()
    open_r = APIRouter(prefix="/api/v1")  # reachable without a session
    r = APIRouter(prefix="/api/v1", dependencies=[Depends(guard)])
    decider = lambda request: (guard.user(request).user_id if guard.user(request) else None)  # noqa: E731
    names = StoreNames(c.metrics)
    agents = uc_copilot.AgentsStatus(lambda: c.core, c.clock)

    def checker() -> sentinel.CheckCompliance:
        return sentinel.CheckCompliance(c.cases, c.proposals, c.executions, c.metrics, c.trace, c.outcomes)

    def case_of(case_id: str) -> Any:
        return uc._case(c.cases, case_id)

    @open_r.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "storage": c.storage, "core": c.core_status, "auth_required": c.auth_required,
                "demo_login": c.demo_login}

    @r.get("/agents/status")
    def agents_status():
        return agents.execute()

    @r.get("/stores")
    def stores(request: Request):
        return [s for s in c.metrics.stores() if guard.allowed(request, s["store_id"])]

    @r.post("/cases", status_code=201)
    def create_case(b: NewCase, request: Request):
        guard.ensure_store(request, b.store_id)
        case = uc.StartCase(c.cases).execute(b.store_id, b.sim_today, b.mode, b.title)
        c.briefings.refresh_async(case)
        return names.tag(jsonable_encoder(case))

    @r.get("/cases")
    def list_cases(request: Request, store_id: str | None = None):
        if store_id:
            guard.ensure_store(request, store_id)
        rows = [k for k in uc.ListCases(c.cases).execute(store_id) if guard.allowed(request, k.store_id)]
        return names.tag(jsonable_encoder(rows))

    @r.get("/cases/{case_id}")
    def get_case(case_id: str):
        return names.tag(jsonable_encoder(uc.ResumeCase(c.cases).execute(case_id)))

    @r.post("/cases/{case_id}/archive")
    def archive(case_id: str):
        case = uc.ArchiveCase(c.cases).execute(case_id)
        c.briefings.clear()
        return names.tag(jsonable_encoder(case))

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
        return {"turn_id": uc.AskAgent(c.cases, c.core, c.turn_tracker, c.clock, c.turns).execute(case_id, b.text, ctx, lookup, voice=b.voice)}

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
        chk = checker()
        measure = uc_outcomes.MeasureOutcomes(c.proposals, chk, c.outcomes, c.decision_memories, c.memory, c.clock)
        res = uc.AdvanceSimClock(c.cases, c.alerts, c.metrics, compliance=chk, measure=measure).execute(case_id, b.days, b.to)
        c.briefings.refresh_async(uc.ResumeCase(c.cases).execute(case_id))
        return {"sim_today": res["sim_today"], "new_alerts": names.tag([alert_view(a) for a in res["alerts"]]),
                "outcomes": res["outcomes"]}

    @r.get("/cases/{case_id}/briefing")
    def briefing(case_id: str):
        return jsonable_encoder(c.briefings.briefing(uc.ResumeCase(c.cases).execute(case_id)))

    @r.post("/promos/audit")
    def promo_audit(b: PromoAuditBody, request: Request):
        case = uc.ResumeCase(c.cases).execute(b.case_id)
        guard.ensure_store(request, case.store_id)
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
    def alerts(request: Request, store_id: str | None = None, state: str | None = None):
        if store_id:
            guard.ensure_store(request, store_id)
        try:
            st = AlertState(state) if state else None
        except ValueError:
            raise DomainError(f"unknown alert state {state!r}") from None
        if store_id and not c.alerts.list(store_id, None):
            # alerts used to appear only after an advance: seed them from the store's latest live case on first read
            live = [k for k in c.cases.list(store_id) if not k.archived and not k.issue_key]
            if live:
                latest = max(live, key=lambda k: k.created_at)
                uc.AdvanceSimClock(c.cases, c.alerts, c.metrics).detect(latest.case_id)
        return names.tag([alert_view(a) for a in uc.ListAlerts(c.alerts, c.cases).execute(store_id, st)
                          if guard.allowed(request, a.store_id)])

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
        return names.tag(alert_view(alert))

    @r.get("/proposals")
    def proposals(request: Request, case_id: str | None = None, store_id: str | None = None, status: str | None = None):
        if case_id:
            guard.ensure_store(request, uc._case(c.cases, case_id).store_id)
        if store_id:
            guard.ensure_store(request, store_id)
        return jsonable_encoder([p for p in c.proposals.list(case_id, store_id, status) if guard.allowed(request, p.store_id)])

    @r.post("/proposals", status_code=201)
    def propose(b: ProposeBody, request: Request, response: Response, idempotency_key: Annotated[str | None, Header()] = None):
        guard.ensure_store(request, uc._case(c.cases, b.case_id).store_id)
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
        return names.tag({**uc_manager.kpis_vs_normal(c.metrics, case, date_from, date_to), "case_id": case.case_id})

    @r.post("/proposals/{proposal_id}/decision")
    def decide(proposal_id: str, b: DecisionBody, request: Request):
        return jsonable_encoder(uc.DecideProposal(c.cases, c.proposals, c.executions, c.alerts, c.memory, c.classifier,
                                                  c.decision_memories, c.clock).execute(proposal_id, b.approved, b.reason, decided_by=decider(request)))

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
    def post_decision(case_id: str, b: CaseDecisionBody, request: Request, response: Response,
                      idempotency_key: Annotated[str | None, Header()] = None):
        out, created = uc_copilot.RecordDecision(c.cases, c.proposals, c.executions, c.alerts, c.metrics, c.served,
                                                 c.memory, c.classifier, c.decision_memories, c.clock).execute(
            case_id, b.issue_id, b.option_id, b.approved, b.reason, idempotency_key, decider(request))
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
    def inventory(case_id: str, sort: str | None = None, limit: int | None = None, days: int | None = None):
        return uc_manager.InventoryView(c.metrics, names, c.forecasters).execute(case_of(case_id), sort, limit, days)

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

    @r.get("/cases/{case_id}/inbox-counts")
    def inbox_counts(case_id: str):
        return uc_copilot.InboxCounts(uc_copilot.PendingDecisions(c.metrics, c.proposals, c.served, names), c.alerts).execute(
            case_of(case_id))

    @r.get("/cases/{case_id}/memories")
    def memories(case_id: str, category: str | None = None, q: str | None = None):
        return uc_copilot.ListMemories(c.cases, c.proposals, c.metrics, c.memory, c.decision_memories, c.clock).execute(
            case_of(case_id), category, q)

    @r.get("/cases/{case_id}/transfers/options")
    def transfer_options(case_id: str, sku: str | None = None, limit: int | None = None):
        return jsonable_encoder(uc_transfers.TransferOptions(c.metrics).execute(case_of(case_id), sku, limit))

    @r.post("/cases/{case_id}/notes", status_code=201)
    def post_note(case_id: str, b: NoteBody):
        """Public twin of the internal notes route, for the UI."""
        return uc_notes.ManagerNotes(c.cases, c.trace, c.decision_memories, c.memory, c.clock).add(
            case_of(case_id), b.text, b.category, b.date_from, b.date_to, b.impact)

    @r.get("/cases/{case_id}/outlook")
    def outlook(case_id: str, days: int | None = None, past_days: int | None = None):
        return uc_manager.OutlookView(c.metrics, names, c.forecasters, c.flow_forecaster).execute(case_of(case_id), days, past_days)

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
    def trace(request: Request, case_id: str | None = None, store_id: str | None = None):
        if not case_id and not store_id:
            raise DomainError("case_id or store_id is required")
        if case_id:
            guard.ensure_store(request, uc._case(c.cases, case_id).store_id)
        if store_id:
            guard.ensure_store(request, store_id)
        return jsonable_encoder(uc.GetAgentTrace(c.cases, c.core, c.trace).execute(case_id, store_id))

    root.include_router(open_r)
    root.include_router(r)
    return root
