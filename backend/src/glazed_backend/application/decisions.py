"""Decision timeline of a case: proposals, manager decisions, executions and measured outcomes in one list."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from ..metrics.sentinel import HORIZON_DAYS


def _compact(row: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if v is not None}


def _score(res: dict[str, Any]) -> dict[str, Any]:
    sim, obs = res["simulated"], res["observed"]
    lo, hi = sim["net_usd_low"], sim["net_usd_high"]
    lo = sim["net_usd_mid"] if lo is None else lo
    hi = sim["net_usd_mid"] if hi is None else hi
    net = float(obs["net_usd"])
    return {"within_expected_range": min(lo, hi) <= net <= max(lo, hi),
            "error_vs_mid_usd": round(net - sim["net_usd_mid"], 2), "diagnosis": res["diagnosis"]}


class ListDecisions:
    """Read-only and case-scoped. Rows: `proposal` (created), `decision` (approved/rejected; `skip_order` when an
    approved skip), `execution` (real or injected records only: the bookkeeping row a decision itself writes is not
    one), `outcome` (once the horizon passed; label backtest). `ts` of a decision is the moment its bookkeeping
    execution was written; an outcome sorts after its decision and carries `as_of` = the end of the horizon."""

    def __init__(self, cases, proposals, executions, checker) -> None:
        self.cases, self.proposals, self.executions, self.checker = cases, proposals, executions, checker

    def execute(self, case_id: str, date_from: date | None = None, date_to: date | None = None) -> list[dict[str, Any]]:
        from . import _case
        case = _case(self.cases, case_id)
        events = self.checker.events(case.store_id)
        execs: dict[str, list[Any]] = {}
        for x in self.executions.list(case.case_id):
            execs.setdefault(x.proposal_id, []).append(x)
        rows: list[dict[str, Any]] = []
        for p in self.proposals.list(case_id=case.case_id):
            mine = sorted(execs.get(p.proposal_id, []), key=lambda x: x.executed_at)
            exp = p.params.get("expected") or {}
            base = {"decision_id": p.proposal_id, "issue_id": p.issue_id, "action_type": p.action_type,
                    "sku": p.params.get("sku"), "supplier": p.params.get("supplier_id"), "qty": p.params.get("qty"),
                    "deadline": p.params.get("deadline_date") or p.params.get("deadline")}
            rows.append(_compact({**base, "ts": p.created_at, "kind": "proposal", "status": "proposed"}))
            last = p.created_at
            if p.status != "pending":
                decided_at = mine[0].executed_at if mine else p.created_at
                kind = "skip_order" if p.status == "approved" and p.action_type == "skip_order" else "decision"
                rows.append(_compact({**base, "ts": decided_at, "kind": kind, "status": p.status,
                                      "reason": p.reason or None, "reason_category": p.reason_category}))
                last = decided_at
                for x in mine:
                    if x.source == "simulated" and x.status == "not_executed":
                        continue  # the decision's own bookkeeping row (rejection, or do_nothing)
                    rows.append(_compact({**base, "ts": x.executed_at, "kind": "execution", "status": x.status,
                                          "reason": x.detail or None}))
                    last = max(last, x.executed_at)
            if p.status == "approved":
                res = self.checker.check(p, case.sim_today, events)
                if res["observed"] and res["simulated"]:
                    end = date.fromisoformat(res["horizon"]["ends"])
                    ts = max(datetime.combine(end, time.min, tzinfo=timezone.utc), last + timedelta(milliseconds=1))
                    obs = res["observed"]
                    rows.append(_compact({**base, "ts": ts, "kind": "outcome", "status": "measured",
                                          "as_of": end.isoformat(), "outcome": {
                                              "observed": {k: obs.get(k) for k in ("net_usd", "waste_usd", "lost_sales_usd",
                                                                                  "censored", "window") if obs.get(k) is not None},
                                              "simulated": res["simulated"], "label": "backtest", "score": _score(res)}}))
        rows.sort(key=lambda r: r["ts"])
        rows = [r for r in rows if (date_from is None or r["ts"].date() >= date_from)
                and (date_to is None or r["ts"].date() <= date_to)]
        for r in rows:
            r["ts"] = r["ts"].isoformat()
        return rows
