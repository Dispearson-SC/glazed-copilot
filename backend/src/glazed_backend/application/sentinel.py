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

    def __init__(self, cases, proposals, executions, metrics, trace, outcomes=None) -> None:
        self.cases, self.proposals, self.executions, self.metrics, self.trace = cases, proposals, executions, metrics, trace
        self.outcomes = outcomes

    def measure(self, proposal: Any, sim_today: date, events: list[dict[str, Any]] | None = None,
                res: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Outcome of an approved, executed decision measured on data <= sim_today: complete once the horizon passed,
        partial from one day after the decision. None when nothing can be measured yet (or for this action type)."""
        from ..metrics.outcomes import build_outcome
        res = res if res is not None else self.check(proposal, sim_today, events)
        h = res.get("horizon")
        if not res["applicable"] or res["execution_status"] != "executed" or not h or not res["simulated"]:
            return None
        if (sim_today - date.fromisoformat(h["decision_date"])).days < 1:
            return None
        obs, complete = (res["observed"], True) if h["passed"] else (None, False)
        if obs is None:
            obs, complete = self.metrics.observed_outcome(proposal.store_id, sim_today, proposal.action_type, proposal.params,
                                                          partial=True), False
        if not obs:
            return None
        return build_outcome(_decision(proposal), h, res["simulated"], obs, sim_today, complete, res["diagnosis"])

    def measured(self, proposal: Any, case: Any, events: list[dict[str, Any]] | None = None,
                 res: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """The outcome as this case may see it: a stored final one measured on or before the case date, else computed."""
        stored = self.outcomes.get(proposal.proposal_id) if self.outcomes is not None else None
        if stored is not None and stored.complete and stored.measured_as_of <= case.sim_today:
            return stored.payload
        return self.measure(proposal, case.sim_today, events, res)

    def events(self, store_id: str) -> list[dict[str, Any]]:
        out = []
        for e in self.trace.list(store_id=store_id):
            p = e.payload or {}
            if p.get("type") in EVENT_TYPES and p.get("date_from"):
                out.append({"type": p["type"], "date_from": p.get("date_from"), "date_to": p.get("date_to") or p.get("date_from"),
                            "note": p.get("note", ""), "source": p.get("source", "agent"), "case_id": e.case_id,
                            "event_id": e.event_id, "proposal_id": p.get("proposal_id"), "execution_id": p.get("execution_id"),
                            "sku": p.get("sku")})
        return out

    def check(self, proposal: Any, sim_today: date, events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        d = _decision(proposal)
        execs = [{"status": x.status, "source": x.source, "executed_at": x.executed_at, "detail": x.detail,
                  "execution_id": x.execution_id} for x in self.executions.list(proposal.case_id)
                 if x.proposal_id == proposal.proposal_id]
        events = self.events(proposal.store_id) if events is None else events
        events = [e for e in events if not e.get("proposal_id") or e["proposal_id"] == proposal.proposal_id]
        res = evaluate_decision(d, execs, sim_today, None, events)
        res.update(case_id=proposal.case_id, store_id=proposal.store_id, tier=proposal.tier, reason=proposal.reason,
                   sim_today=sim_today.isoformat())
        if res["applicable"] and res["execution_status"] == "executed" and res["horizon"] and res["horizon"]["passed"]:
            observed = self.metrics.observed_outcome(proposal.store_id, sim_today, proposal.action_type, proposal.params)
            res = {**evaluate_decision(d, execs, sim_today, observed, events), "case_id": proposal.case_id,
                   "store_id": proposal.store_id, "tier": proposal.tier, "reason": proposal.reason,
                   "sim_today": sim_today.isoformat()}
        res["cause"] = self._cause(proposal, res, events)
        return res

    @staticmethod
    def _cause(proposal: Any, res: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any] | None:
        """The registered event that explains this decision's deviation: one linked to it, else the overlapping one."""
        linked = [e for e in events if e.get("proposal_id") == proposal.proposal_id]
        hit = linked[-1] if linked else (res.get("events") or [None])[0]
        if hit is None:
            return None
        keys = ("type", "note", "date_from", "date_to", "source", "event_id", "proposal_id", "execution_id", "sku")
        return {k: hit.get(k) for k in keys}

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
        """Decisions of this case plus, for a live case, earlier live decisions of the same store (scope "other_case").
        Sandbox and backtest cases never leak, and decisions dated after this case's clock are not shown."""
        from . import _case
        from .scope import decision_date, visible
        case = _case(self.cases, case_id)
        events = self.events(case.store_id)
        owners = {c.case_id: c for c in self.cases.list(case.store_id)}
        own = {p.proposal_id: "this_case" for p in self.proposals.list(case_id=case.case_id)}
        scoped = dict(own)
        if case.mode == "live":  # other live cases only: never archived (test) ones, nothing decided after this date
            for p in self.proposals.list(store_id=case.store_id):
                if p.proposal_id not in scoped and visible(case, p, owners):
                    scoped[p.proposal_id] = "other_case"
        out = []
        dated = lambda x: (str(decision_date(x, owners) or ""), x.created_at)  # noqa: E731 - simulated day first
        for p in sorted(self.proposals.list(store_id=case.store_id), key=dated):
            if p.proposal_id not in scoped:
                continue
            res = self.check(p, case.sim_today, events)
            got = self.measured(p, case, events, res) if p.status == "approved" else None
            extra = {} if got is None else {k: v for k, v in {
                "verdict": got["verdict"], "complete": got["complete"], "measured_as_of": got["measured_as_of"],
                "waste_usd": got["observed"].get("waste_usd"), "lost_sales_usd": got["observed"].get("lost_sales_usd"),
                "censored": got["observed"].get("censored"), "sold_vs_forecast": got["sold_vs_forecast"],
                "summary": got["summary"]}.items()}
            parts = p.issue_id.split("|")
            out.append({"decision_id": p.proposal_id, "scope": scoped[p.proposal_id], "same_case": p.case_id == case.case_id,
                        "case_id": p.case_id,
                        "issue_id": p.issue_id, "kind": parts[1] if len(parts) > 2 else None,
                        "sku": p.params.get("sku"), "action_type": p.action_type, "tier": p.tier, "status": p.status,
                        "rationale": p.rationale, "reason": p.reason, "agent_id": p.agent_id,
                        "decided_as_of": p.params.get("decision_as_of"), "created_at": p.created_at.isoformat(),
                        "executions": [{"status": x.status, "source": x.source, "detail": x.detail,
                                        "executed_at": x.executed_at.isoformat()} for x in self.executions.list(p.case_id)
                                       if x.proposal_id == p.proposal_id],
                        "outcome": None if not res["observed"] and got is None else
                        {"diagnosis": res["diagnosis"], "label": "backtest",
                         "observed_net_usd": (got or res)["observed"]["net_usd"],
                         "simulated_net_usd": (res["simulated"] or {}).get("net_usd_mid"), "explanation": res["explanation"],
                         **extra}})
        return out

    def deviations(self, case_id: str) -> list[dict[str, Any]]:
        """Approved decisions of this store (same mode) that were not executed or missed their simulated range."""
        from . import _case
        case = _case(self.cases, case_id)
        events = self.events(case.store_id)
        from .scope import decision_date
        owners = {c.case_id: c for c in self.cases.list(case.store_id)}
        same = {c.case_id for c in owners.values() if c.mode == case.mode and (c.case_id == case.case_id or not c.archived)}
        out = []
        for p in self.proposals.list(store_id=case.store_id, status="approved"):
            if p.case_id in same and (decision_date(p, owners) or case.sim_today) <= case.sim_today:
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

    def __init__(self, record_event, cases=None, proposals=None, executions=None) -> None:
        self.record_event, self.cases, self.proposals, self.executions = record_event, cases, proposals, executions

    def _link(self, case_id: str, proposal_id: str | None, sku: str | None) -> dict[str, Any]:
        """The decision/execution the event refers to: the given proposal, else the latest execution matching the sku,
        else the latest execution of the case. Unknown ids stay unlinked (nothing is invented)."""
        if self.cases is None or self.proposals is None or self.executions is None:
            return {}
        from . import _case
        case = _case(self.cases, case_id)
        chosen = None
        if proposal_id:
            p = self.proposals.get(proposal_id)
            chosen = p if p is not None and p.store_id == case.store_id else None
        else:
            props = {p.proposal_id: p for p in self.proposals.list(case_id=case.case_id)}
            rows = [x for x in self.executions.list(case.case_id) if x.proposal_id in props
                    and (not sku or props[x.proposal_id].params.get("sku") == sku)]
            if rows:
                chosen = props[max(rows, key=lambda x: x.executed_at).proposal_id]
        if chosen is None:
            return {}
        ex = [x for x in self.executions.list(chosen.case_id) if x.proposal_id == chosen.proposal_id]
        last = max(ex, key=lambda x: x.executed_at) if ex else None
        return {"proposal_id": chosen.proposal_id, "execution_id": last.execution_id if last else None,
                "sku": sku or chosen.params.get("sku")}

    def execute(self, case_id: str, type_: str, date_from: date | None, date_to: date | None, note: str = "",
                proposal_id: str | None = None, sku: str | None = None):
        if type_ not in EVENT_TYPES:
            raise DomainError(f"event type must be one of {EVENT_TYPES}")
        if date_from is None:
            raise DomainError("date_from is required")
        to = date_to or date_from
        if to < date_from:
            raise DomainError("date_to must not precede date_from")
        payload = {"text": f"{type_} {date_from}..{to}: {note}".strip(": "), "type": type_, "date_from": date_from.isoformat(),
                   "date_to": to.isoformat(), "note": note, "source": "demo_injected",
                   **self._link(case_id, proposal_id, sku)}
        return self.record_event.execute(case_id, "manager", "sentinel", "message", payload)
