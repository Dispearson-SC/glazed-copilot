"""Deterministic options per issue: closed action list, numbers from the same loss model as the order plan."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import timedelta

from .detect import expiring_candidate  # noqa: F401  (re-export for callers building expiring issues)
from .inventory import SkuState, expiring_units, is_short_life
from .plan import recommended_qty, scenario_losses, service_for
from .policy import Recommendation, loss_units
from .types import Config

_Z = (-0.674, 0.0, 0.674)


def _r(x: float) -> float:
    return round(float(x), 2)


def make_option(issue_id: str, action_type: str, params: dict, ev: dict, urgency: dict, risk: list[str],
                **extra) -> dict:
    """Assemble an Option. option_id = hash(issue_id, action_type, sorted params). Confidence and tier are
    attached later by the issue builder, which knows the backtest calibration."""
    digest = hashlib.sha256(json.dumps([issue_id, action_type, params], sort_keys=True, default=str).encode()).hexdigest()
    return {"option_id": digest[:12], "action_type": action_type, "params": params,
            "expected_benefit_usd": {k: _r(v) for k, v in ev["benefit"].items()}, "cost_usd": _r(ev["cost_usd"]),
            "net_usd_mid": _r(ev["net_mid"]),
            "loss_impact": {"waste_usd_delta": _r(ev["waste_delta"]), "lost_sales_usd_delta": _r(ev["lost_delta"])},
            "confidence": None, "tier": None, "tier_reasons": [], "urgency": urgency, "risk": risk,
            "if_act": None, "if_not": None, **extra}


def eval_delta(rec: Recommendation, qty: float, base_qty: float, price: float, unit_cost: float,
               perishable: bool) -> dict:
    """Expected value of ordering `qty` instead of `base_qty` with demand at P25/P50/P75 of the cover window.

    net = price x extra sales - cost x extra units (+ cost recovered for leftovers of non-perishables).
    cost_usd is the extra purchase outlay, benefit = net + cost_usd."""
    salvage = 0.0 if perishable else unit_cost
    dq = qty - base_qty
    nets, waste, lost = [], [], []
    for z in _Z:
        mean = max(0.0, rec.mean + z * rec.sd)
        over_q, under_q = loss_units(rec.base + qty, mean, rec.sd)
        over_b, under_b = loss_units(rec.base + base_qty, mean, rec.sd)
        d_sold = (rec.base + qty - over_q) - (rec.base + base_qty - over_b)
        nets.append(price * d_sold - unit_cost * dq + salvage * (over_q - over_b))
        waste.append((over_q - over_b) * unit_cost if perishable else 0.0)
        lost.append((under_q - under_b) * price)
    cost = max(dq, 0.0) * unit_cost
    ben = [n + cost for n in nets]
    return {"benefit": {"low": min(ben), "mid": ben[1], "high": max(ben)}, "cost_usd": cost, "net_mid": nets[1],
            "waste_delta": waste[1], "lost_delta": lost[1]}


def _do_nothing(issue_id: str, waste: float, lost: float, reason: str) -> dict:
    """Baseline option. cost_usd is the expected cost of inaction; loss_impact holds the absolute expected losses."""
    ev = {"benefit": {"low": 0.0, "mid": 0.0, "high": 0.0}, "cost_usd": waste + lost, "net_mid": 0.0,
          "waste_delta": waste, "lost_delta": lost}
    return make_option(issue_id, "do_nothing", {}, ev, {"deadline_date": None, "reason": reason}, [],
                       cost_of_inaction_usd={"mid": _r(waste + lost)})


def _params(state: SkuState, qty: int, **more) -> dict:
    p, case = state.product, max(1, state.product.case_size or 1)
    return {"sku": p.sku, "supplier_id": p.supplier_id, "qty": int(qty), "cases": int(qty) // case,
            "case_size": case, "order_date": state.t.isoformat(), **more}


def _urgency(line: dict) -> dict:
    d, why = line.get("order_deadline"), line.get("order_deadline_status")
    if why == "ok":
        return {"deadline_date": d, "reason": f"Order by {d} to land before the projected stockout on "
                                              f"{line['projected_stockout_date']}."}
    if why == "deadline_passed":
        return {"deadline_date": None, "reason": f"Order deadline already passed; earliest delivery is "
                                                 f"{line['expected_delivery']}, stockout projected "
                                                 f"{line['projected_stockout_date']}."}
    return {"deadline_date": None, "reason": f"Risk of running out before the delivery on {line['expected_delivery']}."}


def stockout_options(issue_id: str, state: SkuState, cfg: Config, line: dict) -> list[dict]:
    p, perishable = state.product, is_short_life(state.product.shelf_life_days)
    service = service_for(state, cfg)
    rec, q_plan = recommended_qty(state, service)
    urgency = _urgency(line)
    late = state.supplier.p_late
    base_risk = [f"Supplier late on {late:.0%} of orders."] if late >= 0.1 else []
    out = []
    ev = eval_delta(rec, q_plan, 0, p.price, p.unit_cost, perishable)
    out.append(make_option(issue_id, "place_order", _params(state, q_plan, plan_qty=q_plan, variant="plan"), ev,
                           urgency, base_risk + ([f"May leave ~${ev['waste_delta']:.2f} of waste."] if ev["waste_delta"] > 0.5 else [])))
    for variant, svc in (("lean", 0.60), ("buffer", 0.85)):
        q = recommended_qty(state, svc)[1]
        if q <= 0 or q == q_plan:
            continue
        ev = eval_delta(rec, q, 0, p.price, p.unit_cost, perishable)
        pct = round((q - q_plan) / q_plan * 100, 1) if q_plan else 0.0
        out.append(make_option(issue_id, "adjust_order_qty", _params(state, q, plan_qty=q_plan, delta_pct=pct, variant=variant),
                               ev, urgency, base_risk))
    base = scenario_losses(rec, 0, p.price, p.unit_cost, perishable)
    out.append(_do_nothing(issue_id, base["waste_usd"]["mid"], base["lost_sales_usd"]["mid"],
                           "Expected lost sales if no order is placed."))
    return out


def _typical(state: SkuState, rec: Recommendation, typical_qty: float | None) -> float:
    if typical_qty is not None:
        return float(typical_qty)
    days = max(1, len(state.rows))
    return sum(r.received for r in state.rows) / days * max(1, len(rec.cover_days))


def _reduction_options(issue_id: str, state: SkuState, cfg: Config, typical_qty: float | None) -> tuple[list[dict], dict]:
    p, perishable = state.product, is_short_life(state.product.shelf_life_days)
    rec, q_plan = recommended_qty(state, service_for(state, cfg))
    q_typ = _typical(state, rec, typical_qty)
    urgency = {"deadline_date": state.t.isoformat(), "reason": "Applies to the next order for this SKU."}
    out = []
    if 0 < q_plan < q_typ:  # q_plan == 0 is exactly skip_order
        ev = eval_delta(rec, q_plan, q_typ, p.price, p.unit_cost, perishable)
        pct = round((q_plan - q_typ) / q_typ * 100, 1) if q_typ else 0.0
        out.append(make_option(issue_id, "adjust_order_qty", _params(state, q_plan, plan_qty=q_plan, typical_qty=q_typ,
                                                                    delta_pct=pct), ev, urgency,
                               ["Lower stock raises the chance of a stockout."]))
    if q_typ > 0:
        ev = eval_delta(rec, 0, q_typ, p.price, p.unit_cost, perishable)
        out.append(make_option(issue_id, "skip_order", {"sku": p.sku, "supplier_id": p.supplier_id, "cycle_date": state.t.isoformat(),
                                                         "typical_qty": q_typ}, ev, urgency,
                               ["Skipping an order can cause a stockout before the next delivery."]))
    base = scenario_losses(rec, q_typ, p.price, p.unit_cost, perishable)
    return out, {"waste": base["waste_usd"]["mid"], "lost": base["lost_sales_usd"]["mid"], "rec": rec, "q_typ": q_typ}


def overstock_options(issue_id: str, state: SkuState, cfg: Config, typical_qty: float | None) -> list[dict]:
    out, base = _reduction_options(issue_id, state, cfg, typical_qty)
    return out + [_do_nothing(issue_id, base["waste"], base["lost"], "Expected waste per cycle if the current order size continues.")]


def expiring_options(issue_id: str, state: SkuState, cfg: Config, typical_qty: float | None) -> list[dict]:
    p = state.product
    units = expiring_units(state)
    d = cfg.markdown_discount
    low, mid, high = (r * units * p.price * (1 - d) for r in cfg.markdown_recovery)
    ev = {"benefit": {"low": low, "mid": mid, "high": high}, "cost_usd": 0.0, "net_mid": mid,
          "waste_delta": -cfg.markdown_recovery[1] * units * p.unit_cost, "lost_delta": 0.0}
    md = make_option(issue_id, "markdown_end_of_day",
                     {"sku": p.sku, "discount_pct": round(d * 100), "units": math.ceil(units), "date": state.t.isoformat()},
                     ev, {"deadline_date": state.t.isoformat(), "reason": "Mark down before closing; the units expire unsold otherwise."},
                     ["Sell-through at a discount is an assumption (no discount history, no hourly data)."],
                     data_caveat="assumed elasticity", tier_cap="N2")
    out, base = _reduction_options(issue_id, state, cfg, typical_qty)
    out = [o for o in out if o["action_type"] == "skip_order"]
    return [md, *out, _do_nothing(issue_id, units * p.unit_cost, 0.0, "Expected waste of the units that expire unsold.")]


def late_options(issue_id: str, supplier_id: str, states: list[SkuState], ref_date_iso: str) -> list[dict]:
    """Options for an overdue delivery. Scenarios: the late order lands tomorrow / in 2 / in 3 days (low/mid/high
    delay). Without it a SKU loses sales once on-hand stock runs out; a complementary order helps only for the
    days after its own delivery."""
    from .policy import delivery_window, round_to_cases

    def unmet(s: SkuState, d: int) -> float:
        need = sum(s.daily_mean(s.t + timedelta(days=i)) for i in range(1, d))
        return max(0.0, need - s.closing)

    def post_need(s: SkuState, d: int) -> float:
        o = (delivery_window(s)[0] - s.t).days
        pre = sum(s.daily_mean(s.t + timedelta(days=i)) for i in range(1, o))
        after = sum(s.daily_mean(s.t + timedelta(days=i)) for i in range(o, d))
        return max(0.0, after - max(0.0, s.closing - pre))

    nothing = [sum(unmet(s, d) * s.product.price for s in states) for d in (1, 2, 3)]
    lines, ben, cost_total, waste_mid, lost_mid = [], [0.0, 0.0, 0.0], 0.0, 0.0, 0.0
    nets = [0.0, 0.0, 0.0]
    for s in states:
        p, case = s.product, max(1, s.product.case_size or 1)
        need_hi = post_need(s, 3)
        if need_hi <= 0:
            continue
        q = round_to_cases(need_hi, case, 0.0, need_hi, max(1.0, need_hi * 0.3), p.price - p.unit_cost, p.unit_cost)
        if q <= 0:
            continue
        perishable = is_short_life(p.shelf_life_days)
        lines.append({"sku": p.sku, "qty": q, "cases": q // case})
        cost_total += q * p.unit_cost
        for i, d in enumerate((1, 2, 3)):
            sold = min(float(q), post_need(s, d))
            net = p.price * sold - p.unit_cost * q + (0.0 if perishable else p.unit_cost) * (q - sold)
            nets[i] += net
            ben[i] += net + q * p.unit_cost
            if i == 1:
                waste_mid += (q - sold) * p.unit_cost if perishable else 0.0
                lost_mid -= p.price * sold
    out = []
    if lines:
        ev = {"benefit": {"low": min(ben), "mid": ben[1], "high": max(ben)}, "cost_usd": cost_total, "net_mid": nets[1],
              "waste_delta": waste_mid, "lost_delta": lost_mid}
        out.append(make_option(issue_id, "place_order",
                               {"supplier_id": supplier_id, "lines": lines, "qty": sum(l["qty"] for l in lines),
                                "order_date": ref_date_iso}, ev,
                               {"deadline_date": ref_date_iso, "reason": "Complementary order must go out today to land before the late delivery does."},
                               ["The late order may arrive first and leave surplus."]))
    out.append(_do_nothing(issue_id, 0.0, nothing[1], "Expected lost sales if the overdue delivery lands in 2 days."))
    out[-1]["cost_of_inaction_usd"] = {"low": _r(nothing[0]), "mid": _r(nothing[1]), "high": _r(nothing[2])}
    return out
