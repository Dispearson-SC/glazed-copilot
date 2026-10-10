"""Minimal Sentinel use cases: compliance of approved decisions, demo injections and deviation issues."""
from __future__ import annotations

from datetime import date
from typing import Any

from ..domain import DomainError, Execution, NotFound
from ..metrics.options import make_option
from ..metrics.sentinel import EVENT_TYPES, evaluate_decision

INJECTABLE = ("not_executed", "partial")


def _decision(p: Any) -> dict[str, Any]:
    return {"decision_id": p.proposal_id, "status": p.status, "action_type": p.action_type, "issue_id": p.issue_id,
            "tier": p.tier, "params": p.params, "case_id": p.case_id, "reason": p.reason}


class CheckCompliance:
    """Executed / not_executed / partial from the executions table, simulated vs observed outcome (backtest, only
    once sim_today passed the horizon) and the diagnosis of section 15.3."""

    def __init__(self, cases, proposals, executions, metrics, trace) -> None:
        self.cases, self.proposals, self.executions, self.metrics, self.trace = cases, proposals, executions, metrics, trace

    def events(self, store_id: str) -> list[dict[str, Any]]:
        out = []
        for e in self.trace.list(store_id=store_id):
            p = e.payload or {}
            if p.get("type") in EVENT_TYPES and p.get("date_from"):
                out.append({"type": p["type"], "date_from": p.get("date_from"), "date_to": p.get("date_to") or p.get("date_from"),
                            "note": p.get("note", ""), "source": p.get("source", "agent"), "case_id": e.case_id})
        return out

    def check(self, proposal: Any, sim_today: date, events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        d = _decision(proposal)
        execs = [{"status": x.status, "source": x.source, "executed_at": x.executed_at, "detail": x.detail,
                  "execution_id": x.execution_id} for x in self.executions.list(proposal.case_id)
                 if x.proposal_id == proposal.proposal_id]
        events = self.events(proposal.store_id) if events is None else events
        res = evaluate_decision(d, execs, sim_today, None, events)
        res.update(case_id=proposal.case_id, store_id=proposal.store_id, tier=proposal.tier, reason=proposal.reason,
                   sim_today=sim_today.isoformat())
        if res["applicable"] and res["execution_status"] == "executed" and res["horizon"] and res["horizon"]["passed"]:
            observed = self.metrics.observed_outcome(proposal.store_id, sim_today, proposal.action_type, proposal.params)
            res = {**evaluate_decision(d, execs, sim_today, observed, events), "case_id": proposal.case_id,
                   "store_id": proposal.store_id, "tier": proposal.tier, "reason": proposal.reason,
                   "sim_today": sim_today.isoformat()}
        return res

    def for_case(self, case_id: str) -> list[dict[str, Any]]:
        from . import _case
        case = _case(self.cases, case_id)
        events = self.events(case.store_id)
        return [self.check(p, case.sim_today, events) for p in self.proposals.list(case_id=case.case_id)]

    def one(self, case_id: str, decision_id: str) -> dict[str, Any]:
        from . import _case
        case = _case(self.cases, case_id)
        p = self.proposals.get(decision_id)
        if p is None or p.store_id != case.store_id:
            raise NotFound(f"decision {decision_id!r} not found")
        return self.check(p, case.sim_today)

    def decision_log(self, case_id: str) -> list[dict[str, Any]]:
        """Decisions of this case plus, for a live case, earlier live decisions of the same store (scope "store").
        Sandbox and backtest cases never leak, and decisions dated after this case's clock are not shown."""
        from . import _case
        case = _case(self.cases, case_id)
        events = self.events(case.store_id)
        own = {p.proposal_id: "case" for p in self.proposals.list(case_id=case.case_id)}
        scoped = dict(own)
        if case.mode == "live":
            live = {c.case_id for c in self.cases.list(case.store_id) if c.mode == "live" and c.sim_today <= case.sim_today}
            for p in self.proposals.list(store_id=case.store_id):
                if p.case_id in live and p.proposal_id not in scoped:
                    scoped[p.proposal_id] = "store"
        out = []
        for p in sorted(self.proposals.list(store_id=case.store_id), key=lambda x: x.created_at):
            if p.proposal_id not in scoped:
                continue
            res = self.check(p, case.sim_today, events)
            parts = p.issue_id.split("|")
            out.append({"decision_id": p.proposal_id, "scope": scoped[p.proposal_id], "case_id": p.case_id,
                        "issue_id": p.issue_id, "kind": parts[1] if len(parts) > 2 else None,
                        "sku": p.params.get("sku"), "action_type": p.action_type, "tier": p.tier, "status": p.status,
                        "rationale": p.rationale, "reason": p.reason, "agent_id": p.agent_id,
                        "decided_as_of": p.params.get("decision_as_of"), "created_at": p.created_at.isoformat(),
                        "executions": [{"status": x.status, "source": x.source, "detail": x.detail,
                                        "executed_at": x.executed_at.isoformat()} for x in self.executions.list(p.case_id)
                                       if x.proposal_id == p.proposal_id],
                        "outcome": None if not res["observed"] else
                        {"diagnosis": res["diagnosis"], "label": "backtest", "observed_net_usd": res["observed"]["net_usd"],
                         "simulated_net_usd": (res["simulated"] or {}).get("net_usd_mid"), "explanation": res["explanation"]}})
        return out

    def deviations(self, case_id: str) -> list[dict[str, Any]]:
        """Approved decisions of this store (same mode) that were not executed or missed their simulated range."""
        from . import _case
        case = _case(self.cases, case_id)
        events = self.events(case.store_id)
        same = {c.case_id for c in self.cases.list(case.store_id) if c.mode == case.mode}
        out = []
        for p in self.proposals.list(store_id=case.store_id, status="approved"):
            if p.case_id in same:
                res = self.check(p, case.sim_today, events)
                if res["diagnosis"] in ("not_executed", "external_event", "forecast_error"):
                    out.append(res)
        return out


def deviation_issue(res: dict[str, Any], as_of: date) -> dict[str, Any]:
    """Sentinel issue (Wave 5 shape) for a decision that was not executed or deviated."""
    store, pid = res["store_id"], res["decision_id"]
    iid = f"{store}|compliance|{pid}"
    exp = (res.get("simulated") or {}).get("net_usd_mid") or 0.0
    zero = {"benefit": {"low": 0.0, "mid": 0.0, "high": 0.0}, "cost_usd": abs(exp), "net_mid": 0.0, "waste_delta": 0.0, "lost_delta": 0.0}
    options = []
    if res["diagnosis"] == "not_executed":
        ev = {"benefit": {"low": 0.0, "mid": abs(exp), "high": abs(exp)}, "cost_usd": 0.0, "net_mid": abs(exp),
              "waste_delta": 0.0, "lost_delta": 0.0}
        o = make_option(iid, res["action_type"], {"original_decision_id": pid, "issue_id": res["issue_id"]}, ev,
                        {"deadline_date": as_of.isoformat(), "reason": "Carry out the approved action or record why not."},
                        ["The window of the original decision may have passed."])
        o["confidence"] = {"score": 1.0, "n_backtest": 0, "method": "rule", "noise_capped": False,
                           "effect_mean_usd": None, "noise_floor_usd": None}
        o["tier"], o["tier_reasons"] = "N2", ["re-executing an approved action: the manager confirms"]
        options.append(o)
    dn = make_option(iid, "do_nothing", {}, zero, {"deadline_date": None, "reason": "Record the deviation and move on."}, [],
                     cost_of_inaction_usd={"mid": round(abs(exp), 2)})
    dn["confidence"] = {"score": 1.0, "n_backtest": 0, "method": "baseline", "noise_capped": False,
                        "effect_mean_usd": None, "noise_floor_usd": None}
    dn["tier"], dn["tier_reasons"] = "N0", ["do_nothing: nothing to execute; record as healthy state"]
    options.append(dn)
    evidence = [{"metric": "execution_status", "value": res["execution_status"], "unit": "text", "period": "executions table",
                 "source": "glazed.executions"},
                {"metric": "diagnosis", "value": res["diagnosis"], "unit": "text", "period": as_of.isoformat(), "source": "sentinel"}]
    if res.get("observed"):
        evidence.append({"metric": "observed_net_usd", "value": res["observed"]["net_usd"], "unit": "USD",
                         "period": "outcome horizon", "source": "backtest replay"})
    if res.get("simulated"):
        evidence.append({"metric": "simulated_net_usd", "value": res["simulated"]["net_usd_mid"], "unit": "USD",
                         "period": "at decision time", "source": "glazed_metrics"})
    return {"issue_id": iid, "kind": "compliance_deviation", "sku": (res.get("params") or {}).get("sku"), "store_id": store,
            "as_of": as_of.isoformat(), "as_of_date": as_of.isoformat(), "severity_usd": round(abs(exp), 2),
            "evidence": evidence, "data_caveats": ["Outcomes are backtest estimates: the data does not respond to our decisions."],
            "options": options, "recommended_option_id": options[0]["option_id"], "engine_version": "sentinel_v0",
            "category": "sentinel", "compliance": res}


class InjectExecution:
    """Demo: record that an approved decision was not (fully) executed. Source is always demo_injected."""

    def __init__(self, cases, proposals, executions) -> None:
        self.cases, self.proposals, self.executions = cases, proposals, executions

    def execute(self, case_id: str, proposal_id: str, status: str, detail: str = "") -> Execution:
        from . import _case
        case = _case(self.cases, case_id)
        if status not in INJECTABLE:
            raise DomainError(f"only {INJECTABLE} can be injected, got {status!r}")
        p = self.proposals.get(proposal_id)
        if p is None or p.store_id != case.store_id:
            raise NotFound(f"proposal {proposal_id!r} not found")
        ex = Execution.new(p.proposal_id, p.case_id, "demo_injected", status, detail or f"injected {status}")
        self.executions.add(ex)
        return ex


class InjectEvent:
    def __init__(self, record_event) -> None:
        self.record_event = record_event

    def execute(self, case_id: str, type_: str, date_from: date | None, date_to: date | None, note: str = ""):
        if type_ not in EVENT_TYPES:
            raise DomainError(f"event type must be one of {EVENT_TYPES}")
        if date_from is None:
            raise DomainError("date_from is required")
        to = date_to or date_from
        if to < date_from:
            raise DomainError("date_to must not precede date_from")
        payload = {"text": f"{type_} {date_from}..{to}: {note}".strip(": "), "type": type_, "date_from": date_from.isoformat(),
                   "date_to": to.isoformat(), "note": note, "source": "demo_injected"}
        return self.record_event.execute(case_id, "manager", "sentinel", "message", payload)
