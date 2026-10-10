"""Minimal Sentinel: did the approved decision get executed, and did the outcome land in the simulated range?

Diagnosis tree (architecture section 15.3): not executed -> `not_executed`; executed and inside the simulated
range -> `within_range`; outside it with a registered event overlapping the horizon -> `external_event`; else
`forecast_error`. The supplier-deviation branch is not implemented. The data does not respond to our decisions, so
every observed outcome is a `backtest` estimate. Pure functions over plain dicts."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

HORIZON_DAYS = 3
EVENT_TYPES = ("bloqueo", "clima_extremo", "evento_local", "cierre", "falla_proveedor", "otro")
_PRIORITY = {"operational": 2, "demo_injected": 1, "simulated": 0}


def latest_execution(executions: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Operational records beat injected or simulated ones; among equals the latest wins."""
    return max(executions, key=lambda e: (_PRIORITY.get(e.get("source", ""), 0), e["executed_at"]), default=None)


def _day(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _overlaps(event: dict[str, Any], start: date, end: date) -> bool:
    a, b = _day(event.get("date_from")), _day(event.get("date_to")) or _day(event.get("date_from"))
    return a is not None and b is not None and a <= end and b >= start


def _simulated(params: dict[str, Any]) -> dict[str, Any] | None:
    exp = params.get("expected")
    if not exp or exp.get("net_usd_mid") is None:
        return None
    return {"net_usd_mid": exp["net_usd_mid"], "net_usd_low": exp.get("net_usd_low"), "net_usd_high": exp.get("net_usd_high"),
            "label": "simulated"}


def evaluate_decision(decision: dict[str, Any], executions: list[dict[str, Any]], sim_today: date,
                      observed: dict[str, Any] | None, events: list[dict[str, Any]]) -> dict[str, Any]:
    """Compliance record of one decision. `observed` is the measured outcome ({net_usd, ...}) or None when the
    metrics cannot measure this action type; `events` are registered events (type, date_from, date_to, note)."""
    params = decision.get("params") or {}
    base = {"decision_id": decision["decision_id"], "issue_id": decision.get("issue_id"),
            "action_type": decision.get("action_type"), "status": decision["status"], "applicable": decision["status"] == "approved",
            "execution": None, "execution_status": None, "horizon": None, "simulated": _simulated(params),
            "observed": None, "events": [], "diagnosis": None, "explanation": ""}
    if not base["applicable"]:
        return {**base, "explanation": f"The decision is {decision['status']}: there is nothing to verify."}
    last = latest_execution(executions)
    status = last["status"] if last else "not_executed"
    base["execution"] = None if last is None else {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in last.items()}
    base["execution_status"] = status
    d0 = _day(params.get("decision_as_of"))
    if d0 is not None:
        ends = d0 + timedelta(days=HORIZON_DAYS)
        base["horizon"] = {"decision_date": d0.isoformat(), "days": HORIZON_DAYS, "ends": ends.isoformat(),
                           "passed": sim_today >= ends}
    if status in ("not_executed", "partial"):
        why = "no execution was recorded" if last is None else f"the execution is {status} ({last.get('source')})"
        return {**base, "diagnosis": "not_executed",
                "explanation": f"The approved action was not carried out: {why}. Ask the manager why; the answer is classified."}
    if base["horizon"] is None or not base["horizon"]["passed"]:
        return {**base, "explanation": "Executed; the outcome horizon has not passed yet, so no outcome is measured."}
    if observed is None or base["simulated"] is None:
        return {**base, "explanation": "Executed, but there is no measurable outcome for this action type (no diagnosis)."}
    net = float(observed["net_usd"])
    base["observed"] = {**observed, "label": "backtest"}
    lo, hi = base["simulated"]["net_usd_low"], base["simulated"]["net_usd_high"]
    lo = base["simulated"]["net_usd_mid"] if lo is None else lo
    hi = base["simulated"]["net_usd_mid"] if hi is None else hi
    tol = max(1.0, 0.25 * abs(base["simulated"]["net_usd_mid"]))  # replays of one rule are often zero-width
    lo, hi = min(lo, hi) - tol, max(lo, hi) + tol
    if lo <= net <= hi:
        return {**base, "diagnosis": "within_range",
                "explanation": f"Observed net ${net:,.2f} is inside the simulated range [${lo:,.2f}, ${hi:,.2f}] (backtest)."}
    hits = [e for e in events if _overlaps(e, d0, d0 + timedelta(days=HORIZON_DAYS))]
    if hits:
        return {**base, "events": hits, "diagnosis": "external_event",
                "explanation": f"Observed net ${net:,.2f} is outside the simulated range; attributed to the registered "
                               f"event {hits[0].get('type')} overlapping the horizon."}
    return {**base, "diagnosis": "forecast_error",
            "explanation": f"Observed net ${net:,.2f} is outside the simulated range [${lo:,.2f}, ${hi:,.2f}] with no "
                           f"registered event: the forecast was off."}
