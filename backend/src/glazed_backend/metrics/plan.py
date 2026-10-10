"""Order plan lines: stockout projection, order deadline, risk, expected losses and comparison with practice."""
from __future__ import annotations

import math
from datetime import date, timedelta
from statistics import NormalDist

from .inventory import SkuState, is_short_life
from .policy import Recommendation, loss_units, recommend, round_to_cases
from .schedule import first_delivery
from .service_level import SENSITIVITY, critical_ratio
from .types import Config

_N = NormalDist()
_Z_SCENARIO = 0.674  # demand P25 / P50 / P75 scenarios


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def projected_stockout(state: SkuState, horizon: int = 14) -> date | None:
    """First day the expected inventory goes negative (mean demand, in-transit arrivals on their projected date)."""
    stock = float(state.closing)
    for i in range(1, horizon + 1):
        d = state.t + timedelta(days=i)
        stock += state.arrivals_between(d, d) - state.daily_mean(d)
        if stock < 0:
            return d
    return None


def order_deadline(state: SkuState, stockout: date | None) -> tuple[date | None, str]:
    """Last order day whose delivery (supplier lead p90 and delivery days) lands on or before the stockout."""
    if stockout is None:
        return None, "no_stockout_projected"
    sup, closed = state.supplier, state.store.closed_dates
    lead = max(1, math.ceil(sup.lead_p90))
    o = stockout
    while o >= state.t:
        if first_delivery(o, lead, sup.delivery_days, closed) <= stockout:
            return o, "ok"
        o -= timedelta(days=1)
    return None, "deadline_passed"


def stockout_risk(state: SkuState, with_qty: float | None) -> float:
    """P(demand before the next delivery exceeds the stock). Without an order the horizon ends where an order
    placed tomorrow would land; with one, at the delivery after the order's. Deliveries slip one day with p_late."""
    from .demand import horizon_demand
    from .policy import delivery_window
    sup, closed = state.supplier, state.store.closed_dates
    d1, d2 = delivery_window(state)
    lead = max(1, round(sup.lead_mean))
    end = first_delivery(state.t + timedelta(days=1), lead, sup.delivery_days, closed) - timedelta(days=1) \
        if with_qty is None else d2 - timedelta(days=1)
    end = max(end, state.t + timedelta(days=1))
    days = [state.t + timedelta(days=i) for i in range(1, (end - state.t).days + 1)]
    mean, sd = horizon_demand(state.censored.demand, state.t, days)
    qty = with_qty or 0.0

    def p_short(avail: float) -> float:
        return 1.0 - _N.cdf((avail - mean) / sd) if sd > 1e-9 else float(mean > avail)
    on_time = state.closing + state.arrivals_between(days[0], end) + qty
    late = state.closing + state.arrivals_between(days[0], end - timedelta(days=1)) + (qty if d1 < end else 0.0)
    p = sup.p_late
    return round((1 - p) * p_short(on_time) + p * p_short(late), 4)


def scenario_losses(rec: Recommendation, qty: float, price: float, unit_cost: float, perishable: bool) -> dict:
    """Expected leftover-waste and lost-sales USD with qty ordered, at demand P25/P50/P75 of the cover window."""
    waste, lost = [], []
    total = rec.base + qty
    for z in (-_Z_SCENARIO, 0.0, _Z_SCENARIO):
        over, under = loss_units(total, max(0.0, rec.mean + z * rec.sd), rec.sd)
        waste.append(over * unit_cost if perishable else 0.0)
        lost.append(under * price)
    srt = lambda xs: dict(zip(("low", "mid", "high"), (round(x, 2) for x in sorted(xs))))  # noqa: E731
    return {"waste_usd": srt(waste), "lost_sales_usd": srt(lost)}


def _service(state: SkuState, cfg: Config) -> float:
    p = state.product
    cr = critical_ratio(p.price, p.unit_cost)
    return cr if is_short_life(p.shelf_life_days) else max(cr, cfg.non_perishable_service)


def _costs(state: SkuState, service: float) -> tuple[float, float]:
    p = state.product
    if is_short_life(p.shelf_life_days):
        return max(p.price - p.unit_cost, 1e-6), max(p.unit_cost, 1e-6)
    return service / (1.0 - service), 1.0  # (s,S): implied by the target availability


def recommended_qty(state: SkuState, service: float) -> tuple[Recommendation, int]:
    rec = recommend(state, service)
    cu, co = _costs(state, service)
    return rec, round_to_cases(rec.qty_raw, state.product.case_size, rec.base, rec.mean, rec.sd, cu, co)


def plan_line(state: SkuState, cfg: Config, typical_qty: float | None, window_received: float,
              window_sold: float) -> dict | None:
    p = state.product
    service = _service(state, cfg)
    rec, qty = recommended_qty(state, service)
    if qty <= 0:
        return None
    perishable = is_short_life(p.shelf_life_days)
    sens = {f"{s:.2f}": recommended_qty(state, s)[1] for s in SENSITIVITY}
    qtys = list(sens.values()) + [qty]
    stockout = projected_stockout(state, cfg.horizon_days)
    deadline, why = order_deadline(state, stockout)
    loss = scenario_losses(rec, qty, p.price, p.unit_cost, perishable)
    case = max(1, p.case_size or 1)
    caveats = []
    if state.censored.censored_share > 0.2:
        caveats.append(f"{state.censored.censored_share:.0%} of days had stockouts: demand is corrected upward (capped at p90).")
    if state.supplier.p_late >= 0.1:
        caveats.append(f"Supplier late on {state.supplier.p_late:.0%} of orders: one day of slip is priced in.")
    return {
        "sku": p.sku, "name": p.name, "product_name": p.name, "supplier_id": p.supplier_id,
        "method": rec.method, "service_level_target": round(service, 4), "sensitivity": sens,
        "qty": qty, "qty_units": qty, "case_size": case, "cases": qty // case,
        "qty_range": {"low": min(qtys), "high": max(qtys)}, "qty_low": min(qtys), "qty_high": max(qtys),
        "est_cost_usd": round(qty * p.unit_cost, 2),
        "expected_delivery": _iso(rec.delivery), "days_to_next_delivery": (rec.delivery - state.t).days,
        "usable_stock": round(rec.usable, 2), "in_transit_qty": round(rec.arrivals, 2),
        "projected_stockout_date": _iso(stockout), "order_deadline": _iso(deadline), "order_deadline_status": why,
        "stockout_risk_without_order": stockout_risk(state, None),
        "stockout_risk_with_order": stockout_risk(state, qty),
        "expected_waste_usd": loss["waste_usd"], "expected_lost_sales_usd": loss["lost_sales_usd"],
        "vs_current_practice": {
            "received_to_sold": round(window_received / window_sold, 2) if window_sold > 0 else None,
            "qty_delta": None if typical_qty is None else round(qty - typical_qty)},
        "min_order_warning": None,
        "basis": {"method": rec.method, "n_days": len(state.rows),
                  "censored_share": round(state.censored.censored_share, 3),
                  "reorder_point": None if rec.reorder_point is None else round(rec.reorder_point, 1),
                  "order_up_to": None if rec.order_up_to is None else round(rec.order_up_to, 1)},
        "data_caveats": caveats,
    }


def apply_min_order(lines: list[dict], min_by_supplier: dict[str, float]) -> list[dict]:
    """MOV is a warning only: never inflate a line to reach it; suggest consolidating instead."""
    totals: dict[str, float] = {}
    for ln in lines:
        totals[ln["supplier_id"]] = totals.get(ln["supplier_id"], 0.0) + ln["est_cost_usd"]
    for ln in lines:
        mov, total = min_by_supplier.get(ln["supplier_id"], 0.0), totals[ln["supplier_id"]]
        ln["min_order_warning"] = None if total >= mov else {
            "min_order_value": mov, "order_value_usd": round(total, 2),
            "suggestion": "Below the supplier minimum; consolidate with the next delivery day. "
                          "The quantity was not inflated (the minimum is rarely enforced)."}
    return lines
