"""Alert 19: calendar uplift ahead (school breaks, holidays). Effects are computed per store x department with
shrinkage toward the format x department average when the cell has fewer than 20 event days. No I/O."""
from __future__ import annotations

from datetime import date

from .issues import _issue, finalize_options
from .options import _do_nothing, make_option
from .types import Config

MIN_CELL_DAYS = 20
MATERIAL_PCT = 5.0
SELL_THROUGH = {"low": 0.4, "mid": 0.7, "high": 1.0}  # share of the extra units that sell (assumption)


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _pct(event: list[float], base: list[float]) -> float | None:
    b = _mean(base)
    return None if not base or b <= 0 or not event else (_mean(event) / b - 1.0) * 100.0


def event_effect(cell_event: list[float], cell_base: list[float], group_event: list[float],
                 group_base: list[float]) -> dict | None:
    """Percent change of daily units on event days vs ordinary days. weight = min(1, n / 20): below 20 event days
    the cell's own estimate is blended with the format x department one and a data_caveat says so."""
    cell, group = _pct(cell_event, cell_base), _pct(group_event, group_base)
    n = len(cell_event)
    if cell is None and group is None:
        return None
    if cell is None:
        w, eff = 0.0, group
    elif group is None:
        w, eff = 1.0, cell
    else:
        w = min(1.0, n / MIN_CELL_DAYS)
        eff = w * cell + (1.0 - w) * group
    shrunk = w < 1.0
    caveat = None
    if shrunk:
        caveat = (f"Only {n} days of this event in this store and department (< {MIN_CELL_DAYS}): the effect is blended "
                  f"{round(w * 100)}% store / {round((1 - w) * 100)}% format x department average.")
    return {"effect_pct": round(eff, 1), "n": n, "weight": round(w, 3), "shrunk": shrunk,
            "cell_pct": None if cell is None else round(cell, 1), "group_pct": None if group is None else round(group, 1),
            "data_caveat": caveat}


def calendar_issue(store_id: str, as_of: date, ref: date, event: dict, departments: list[dict], cfg: Config) -> dict | None:
    """One issue per upcoming event: raise the order in the departments whose calculated effect is material."""
    days = sorted(event["days"])
    material = [d for d in departments if d.get("effect") and abs(d["effect"]["effect_pct"]) >= MATERIAL_PCT]
    if not material:
        return None
    effects, gain, cost, waste, lost = [], {k: 0.0 for k in SELL_THROUGH}, 0.0, 0.0, 0.0
    caveats = []
    for d in material:
        e = d["effect"]
        extra = d["units_per_day"] * e["effect_pct"] / 100.0 * len(days)
        effects.append({"department": d["department"], "effect_pct": e["effect_pct"], "n": e["n"], "shrunk": e["shrunk"],
                        "extra_units": round(extra, 1)})
        if e["data_caveat"]:
            caveats.append(f"{d['department']}: {e['data_caveat']}")
        outlay = max(extra, 0.0) * d["avg_cost"]
        cost += outlay
        for k, f in SELL_THROUGH.items():
            gain[k] += f * max(extra, 0.0) * d["avg_price"]
        waste += (1 - SELL_THROUGH["mid"]) * max(extra, 0.0) * d["avg_cost"]
        lost -= SELL_THROUGH["mid"] * max(extra, 0.0) * d["avg_price"]
    iid = f"{store_id}|calendar_uplift|{event['type']}-{days[0].isoformat()}"
    urgency = {"deadline_date": ref.isoformat(), "reason": f"{event['name']} starts {days[0].isoformat()}: the plan only reflects the last 56 ordinary days."}
    ev = {"benefit": dict(gain), "cost_usd": cost, "net_mid": gain["mid"] - cost, "waste_delta": waste, "lost_delta": lost}
    adj = make_option(iid, "adjust_order_qty",
                      {"event": event["name"], "event_type": event["type"], "effects": effects,
                       "window": [days[0].isoformat(), days[-1].isoformat()],
                       "scope": "apply effect_pct to every SKU plan quantity of the listed departments"},
                      ev, urgency, ["Perishables follow the newsvendor, so the real increase can be lower than the effect.",
                                    "Calendar effect is not isolated from season or weather."])
    dn = _do_nothing(iid, 0.0, gain["mid"], "Expected lost sales if the order stays at the usual plan.")
    options = [adj, dn]
    rec = finalize_options(options, "calendar_uplift", {}, cfg)
    sev = gain["mid"]
    evidence = [{"metric": f"{e['department']} effect", "value": e["effect_pct"], "unit": "% vs ordinary days",
                 "period": f"{event['name']} {days[0].isoformat()}..{days[-1].isoformat()}",
                 "source": "calendar_effects (store x department, shrunk to format x department)"} for e in effects]
    return _issue(store_id, "calendar_uplift", f"{event['type']}-{days[0].isoformat()}", as_of, ref, sev, evidence,
                  caveats + ["Assumes 70% of the extra units sell (40%-100% range)."], options, rec,
                  event={"type": event["type"], "name": event["name"], "days": [d.isoformat() for d in days]})
