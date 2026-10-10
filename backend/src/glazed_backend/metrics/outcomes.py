"""The realized outcome of an approved, executed decision: figures measured on data up to the case date, a verdict
against the range expected when it was decided, and a Spanish summary. Pure functions over plain dicts.

Every outcome is a `backtest` estimate: the data does not respond to our decisions (the order was simulated)."""
from __future__ import annotations

from datetime import date
from typing import Any

from .memory_view import ACTION_ES

VERDICTS = {"better": "mejor de lo esperado", "within": "dentro de lo esperado", "worse": "peor de lo esperado"}
_OBSERVED_KEYS = ("net_usd", "waste_usd", "lost_sales_usd", "censored", "units_sold", "units_forecast", "window")


def _range(sim: dict[str, Any]) -> tuple[float, float]:
    mid = float(sim["net_usd_mid"])
    lo = mid if sim.get("net_usd_low") is None else float(sim["net_usd_low"])
    hi = mid if sim.get("net_usd_high") is None else float(sim["net_usd_high"])
    return min(lo, hi), max(lo, hi)


def verdict(net: float, sim: dict[str, Any]) -> tuple[str, str]:
    """(code, Spanish text). Replays of one rule are often zero-width, so the range gets a tolerance of 25% of the
    expected net (at least $1), the same one the Sentinel diagnosis uses."""
    lo, hi = _range(sim)
    tol = max(1.0, 0.25 * abs(float(sim["net_usd_mid"])))
    code = "better" if net > hi + tol else "worse" if net < lo - tol else "within"
    return code, VERDICTS[code]


def _sold_vs_forecast(obs: dict[str, Any]) -> dict[str, Any] | None:
    sold, fc = obs.get("units_sold"), obs.get("units_forecast")
    if sold is None:
        return None
    if fc is None:
        return {"units_sold": sold, "units_forecast": None, "delta_units": None, "delta_pct": None}
    return {"units_sold": sold, "units_forecast": fc, "delta_units": round(sold - fc, 2),
            "delta_pct": round((sold - fc) / fc * 100, 1) if fc else None}


def outcome_text(o: dict[str, Any], product: str) -> str:
    ob, sim = o["observed"], o["simulated"]
    what = ACTION_ES.get(o["action_type"], o["action_type"])
    svf = o.get("sold_vs_forecast")
    sold = ""
    if svf and svf.get("units_forecast") is not None:
        sold = f"; vendiste {svf['units_sold']:g} unidades frente a {svf['units_forecast']:g} pronosticadas"
    elif svf:
        sold = f"; vendiste {svf['units_sold']:g} unidades"
    figures = (f"merma real ${float(ob.get('waste_usd') or 0):,.2f}, venta perdida ${float(ob.get('lost_sales_usd') or 0):,.2f}"
               f"{sold}")
    cens = " La demanda quedó censurada por un quiebre de inventario: la venta pudo ser mayor." if ob.get("censored") else ""
    head = f"Aprobaste {what} de {product} el {o['decided_as_of']}."
    if not o["complete"]:
        return (f"Resultado en curso al {o['measured_as_of']} ({o['window_days']} día(s) de datos tras la decisión): "
                f"{figures}. {head} Aún no hay veredicto.{cens}")
    lo, hi = _range(sim)
    return (f"Resultado medido el {o['measured_as_of']}: {head[:-1]}; {figures}. Veredicto: {o['verdict']} "
            f"(neto ${float(ob['net_usd']):,.2f}; esperado ${lo:,.2f} a ${hi:,.2f}).{cens}")


def build_outcome(decision: dict[str, Any], horizon: dict[str, Any], simulated: dict[str, Any], observed: dict[str, Any],
                  measured_as_of: date, complete: bool, diagnosis: str | None, product: str | None = None) -> dict[str, Any]:
    params = decision.get("params") or {}
    obs = {k: observed[k] for k in _OBSERVED_KEYS if observed.get(k) is not None}
    window = obs.get("window") or []
    days = (date.fromisoformat(window[-1]) - date.fromisoformat(window[0])).days + 1 if len(window) == 2 else 0
    code, es = verdict(float(obs["net_usd"]), simulated) if complete else (None, None)
    lo, hi = _range(simulated)
    score = {"within_expected_range": lo <= float(obs["net_usd"]) <= hi,
             "error_vs_mid_usd": round(float(obs["net_usd"]) - float(simulated["net_usd_mid"]), 2),
             "diagnosis": diagnosis} if complete else None
    out = {"decision_id": decision["decision_id"], "case_id": decision.get("case_id"), "issue_id": decision.get("issue_id"),
           "action_type": decision.get("action_type"), "sku": params.get("sku"), "decided_as_of": horizon["decision_date"],
           "measured_as_of": measured_as_of.isoformat(), "horizon_ends": horizon["ends"], "complete": complete,
           "window_days": days, "observed": obs, "simulated": simulated, "label": "backtest", "score": score,
           "sold_vs_forecast": _sold_vs_forecast(obs), "verdict": es, "verdict_code": code}
    out["summary"] = outcome_text(out, product or params.get("sku") or decision.get("issue_id") or "la decisión")
    return out
