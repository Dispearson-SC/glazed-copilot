"""Public API /api/v1/* for the CLI and the frontend."""

from datetime import date
from typing import Any

from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from ... import application as uc
from ...domain import AlertState, DomainError, NotFound


class NewCase(BaseModel):
    store_id: str
    sim_today: date
    mode: str = "live"
    title: str = ""


class ForkBody(BaseModel):
    title: str = ""


class AskBody(BaseModel):
    text: str


class AdvanceBody(BaseModel):
    days: int = 1
    to: date | None = None


class DecisionBody(BaseModel):
    approved: bool
    reason: str = ""


class BacktestBody(BaseModel):
    date_from: date
    date_to: date
    policy: str = "simple_v0"


class OutcomeBody(BaseModel):
    summary: str


class TransitionBody(BaseModel):
    state: str


def build_public_router(c: Any) -> APIRouter:
    r = APIRouter(prefix="/api/v1")

    @r.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "storage": c.storage, "core": c.core_status}

    @r.get("/stores")
    def stores():
        return c.metrics.stores()

    @r.post("/cases", status_code=201)
    def create_case(b: NewCase):
        return jsonable_encoder(uc.StartCase(c.cases).execute(b.store_id, b.sim_today, b.mode, b.title))

    @r.get("/cases")
    def list_cases(store_id: str | None = None):
        return jsonable_encoder(uc.ListCases(c.cases).execute(store_id))

    @r.get("/cases/{case_id}")
    def get_case(case_id: str):
        return jsonable_encoder(uc.ResumeCase(c.cases).execute(case_id))

    @r.post("/cases/{case_id}/fork", status_code=201)
    def fork(case_id: str, b: ForkBody | None = None):
        return jsonable_encoder(uc.ForkCase(c.cases, c.proposals, c.executions).execute(case_id, (b.title if b else "")))

    @r.post("/cases/{case_id}/messages", status_code=202)
    def ask(case_id: str, b: AskBody):
        return {"turn_id": uc.AskAgent(c.cases, c.core, c.turn_tracker, c.clock).execute(case_id, b.text)}

    @r.get("/cases/{case_id}/turns/{turn_id}")
    def turn(case_id: str, turn_id: str):
        return uc.GetTurn(c.cases, c.core, c.turn_tracker, c.clock, c.turn_timeout_s).execute(case_id, turn_id)

    @r.get("/cases/{case_id}/day-summary")
    def day_summary(case_id: str, date: date | None = None):
        return uc.GetDaySummary(c.cases, c.metrics).execute(case_id, date)

    @r.post("/cases/{case_id}/advance")
    def advance(case_id: str, b: AdvanceBody | None = None):
        b = b or AdvanceBody()
        res = uc.AdvanceSimClock(c.cases, c.alerts, c.metrics).execute(case_id, b.days, b.to)
        return jsonable_encoder({"sim_today": res["sim_today"], "new_alerts": res["alerts"]})

    @r.get("/alerts")
    def alerts(store_id: str | None = None, state: str | None = None):
        try:
            st = AlertState(state) if state else None
        except ValueError:
            raise DomainError(f"unknown alert state {state!r}") from None
        return jsonable_encoder(uc.ListAlerts(c.alerts).execute(store_id, st))

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
        return jsonable_encoder(alert)

    @r.get("/proposals")
    def proposals(case_id: str | None = None, store_id: str | None = None, status: str | None = None):
        return jsonable_encoder(c.proposals.list(case_id, store_id, status))

    @r.post("/proposals/{proposal_id}/decision")
    def decide(proposal_id: str, b: DecisionBody):
        return jsonable_encoder(uc.DecideProposal(c.cases, c.proposals, c.executions, c.alerts, c.memory)
                                .execute(proposal_id, b.approved, b.reason))

    @r.post("/proposals/{proposal_id}/outcome", status_code=201)
    def outcome(proposal_id: str, b: OutcomeBody):
        return jsonable_encoder(uc.RecordOutcome(c.proposals, c.cases, c.memory).execute(proposal_id, b.summary))

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
