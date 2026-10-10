"""Issue assembly: detectors -> options -> confidence (backtest) -> tier (code). Output follows the Wave 5 contract."""
from __future__ import annotations

from datetime import date

from .confidence import Calibration, confidence_for
from .detect import (avg_daily_demand, expiring_candidate, inflated_order_candidate, overstock_candidate,
                     stockout_candidate)
from .options import expiring_options, inflated_order_options, late_options, overstock_options, stockout_options
from .snapshot import StoreSnapshot
from .tiers import classify
from .types import Config

ENGINE = "glazed_metrics_v1"


def _ev(metric: str, value, unit: str, period: str, source: str) -> dict:
    return {"metric": metric, "value": value, "unit": unit, "period": period, "source": source}


def finalize_options(options: list[dict], kind: str, calib: dict[tuple[str, str], Calibration], cfg: Config) -> str:
    """Attach confidence and tier to every option; returns the recommended option_id."""
    actions = [o for o in options if o["action_type"] != "do_nothing"]
    for o in options:
        if o["action_type"] == "do_nothing":
            o["confidence"] = {"score": 1.0, "n_backtest": 0, "method": "baseline", "noise_capped": False,
                               "effect_mean_usd": None, "noise_floor_usd": cfg.noise_floor_usd}
            o["tier"], o["tier_reasons"] = classify(o, None, cfg)
            continue
        o["confidence"] = confidence_for(calib.get((kind, o["action_type"])), o["net_usd_mid"], cfg)
        others = [x["net_usd_mid"] for x in actions if x is not o]
        runner = max(others) if others else None
        tier, why = classify(o, runner, cfg, o["params"].get("plan_qty", o["params"].get("qty")),
                             o["params"].get("case_size", 1))
        if o["confidence"]["noise_capped"] and tier != "N0":
            why = why + [f"confidence capped at {o['confidence']['score']:.1f}: replayed effect is below the noise floor"]
        if o["confidence"]["n_backtest"] == 0 and tier != "N0":
            why = why + ["no backtest available for this action: uncalibrated"]
        o["tier"], o["tier_reasons"] = tier, why
    viable = [o for o in actions if o["tier"] != "N0"]
    best = max(viable, key=lambda o: (o["net_usd_mid"], o["option_id"]), default=None)
    dn = next(o for o in options if o["action_type"] == "do_nothing")
    return (best or dn)["option_id"]


def _issue(store_id: str, kind: str, key: str, as_of: date, ref: date, severity: float, evidence: list[dict],
           caveats: list[str], options: list[dict], recommended: str, **ident) -> dict:
    return {"issue_id": f"{store_id}|{kind}|{key}", "kind": kind, **ident, "store_id": store_id,
            "as_of": as_of.isoformat(), "as_of_date": ref.isoformat(), "severity_usd": round(severity, 2),
            "evidence": evidence, "data_caveats": caveats, "options": options,
            "recommended_option_id": recommended, "engine_version": ENGINE}


def detect_issues(snap: StoreSnapshot, store_id: str, as_of: date, ref: date, cfg: Config,
                  calib: dict[tuple[str, str], Calibration], limit: int = 5) -> list[dict]:
    out: list[dict] = []
    for sku in snap.products:
        state = snap.state_at(sku, ref)
        if state is None:
            continue
        p, per = state.product, f"{ref.isoformat()}"
        base_cav = [f"{state.censored.censored_share:.0%} of days had stockouts; demand corrected upward (capped at p90)."] \
            if state.censored.censored_share > 0.2 else []
        line = stockout_candidate(state, cfg)
        if line:
            iid = f"{store_id}|stockout_risk|{sku}"
            opts = stockout_options(iid, state, cfg, line)
            rec = finalize_options(opts, "stockout_risk", calib, cfg)
            dn = next(o for o in opts if o["action_type"] == "do_nothing")
            ev = [_ev("closing_qty", state.closing, "units", per, "inventory_daily"),
                  _ev("avg_daily_demand", round(avg_daily_demand(state), 2), "units/day", "last 28 days",
                      "inventory_daily (stockout-corrected)"),
                  _ev("stockout_risk_without_order", line["stockout_risk_without_order"], "probability", "until next delivery",
                      "glazed_metrics"),
                  _ev("projected_stockout_date", line["projected_stockout_date"], "date", "14-day horizon", "glazed_metrics"),
                  _ev("lead_time_p90", round(state.supplier.lead_p90, 2), "days", "last 180 days", "purchase_orders")]
            out.append(_issue(store_id, "stockout_risk", sku, as_of, ref, dn["cost_usd"], ev, base_cav + line["data_caveats"],
                              opts, rec, sku=sku, product_name=p.name, supplier_id=p.supplier_id))
        over = overstock_candidate(state, cfg)
        exp = None if over else expiring_candidate(state)
        typical = snap.typical_order_qty(sku, ref)
        if over:
            iid = f"{store_id}|overstock_waste|{sku}"
            opts = overstock_options(iid, state, cfg, typical)
            rec = finalize_options(opts, "overstock_waste", calib, cfg)
            ev = [_ev("waste_usd_14d", round(over["waste_usd_14d"], 2), "USD", "last 14 days", "inventory_daily x unit_cost"),
                  _ev("received_28d", over["received_28d"], "units", "last 28 days", "inventory_daily"),
                  _ev("sold_28d", over["sold_28d"], "units", "last 28 days", "inventory_daily"),
                  _ev("received_to_sold", round(over["received_28d"] / max(over["sold_28d"], 1), 2), "ratio", "last 28 days",
                      "inventory_daily")]
            out.append(_issue(store_id, "overstock_waste", sku, as_of, ref, over["waste_usd_14d"], ev, base_cav, opts, rec,
                              sku=sku, product_name=p.name, supplier_id=p.supplier_id))
        infl = inflated_order_candidate(state, cfg, typical)
        if infl:
            iid = f"{store_id}|inflated_order|{sku}"
            opts = inflated_order_options(iid, state, cfg, infl)
            rec = finalize_options(opts, "inflated_order", calib, cfg)
            dn = next(o for o in opts if o["action_type"] == "do_nothing")
            ev = [_ev("ordered_qty", infl["ordered_qty"], "units", "plan / typical order", "purchase_orders"),
                  _ev("optimum_qty", infl["optimum_qty"], "units", per, "glazed_metrics"),
                  _ev("excess_over_optimum", infl["excess_units"], "units", per, "glazed_metrics"),
                  _ev("case_size", infl["case_size"], "units", "product", "products"),
                  _ev("waste_rate", infl["waste_rate"], "share of received", "last 56 days", "inventory_daily")]
            out.append(_issue(store_id, "inflated_order", sku, as_of, ref, dn["cost_usd"], ev, base_cav + [
                "Whether the supplier accepts less than a full case is unconfirmed."], opts, rec, sku=sku,
                product_name=p.name, supplier_id=p.supplier_id))
        if exp:
            iid = f"{store_id}|expiring|{sku}"
            opts = expiring_options(iid, state, cfg, typical)
            rec = finalize_options(opts, "expiring", calib, cfg)
            ev = [_ev("expiring_units", round(exp["units"], 1), "units", f"next {p.shelf_life_days} days", "glazed_metrics (FIFO)"),
                  _ev("closing_qty", state.closing, "units", per, "inventory_daily"),
                  _ev("shelf_life_days", p.shelf_life_days, "days", "product", "products")]
            cav = base_cav + ["Lot ages are inferred (FIFO from received_qty); inventory_daily has no lot detail."]
            out.append(_issue(store_id, "expiring", sku, as_of, ref, exp["value_usd"], ev, cav + [
                "markdown_end_of_day: assumed elasticity"], opts, rec, sku=sku, product_name=p.name, supplier_id=p.supplier_id))
    out.extend(_late_issues(snap, store_id, as_of, ref, cfg, calib))
    out.sort(key=lambda i: (-i["severity_usd"], i["issue_id"]))
    return out[:limit]


def _late_issues(snap: StoreSnapshot, store_id: str, as_of: date, ref: date, cfg: Config,
                 calib: dict[tuple[str, str], Calibration]) -> list[dict]:
    by_sup: dict[str, list] = {}
    for po in snap.pos:
        if po.received_date is None and po.expected_date < as_of and po.sku in snap.products:
            by_sup.setdefault(snap.products[po.sku].supplier_id, []).append(po)
    out = []
    for sup, pos in by_sup.items():
        states = [s for s in (snap.state_at(sku, ref) for sku in sorted({p.sku for p in pos})) if s is not None]
        iid = f"{store_id}|late_delivery|{sup}"
        opts = late_options(iid, sup, states, ref.isoformat())
        rec = finalize_options(opts, "late_delivery", calib, cfg)
        dn = next(o for o in opts if o["action_type"] == "do_nothing")
        value = sum(p.qty_ordered * snap.products[p.sku].unit_cost for p in pos)
        ev = [_ev("overdue_lines", len(pos), "lines", f"expected before {as_of.isoformat()}", "purchase_orders"),
              _ev("max_days_late", max((as_of - p.expected_date).days for p in pos), "days", "as of", "purchase_orders"),
              _ev("overdue_order_value", round(value, 2), "USD", "overdue lines", "purchase_orders x unit_cost")]
        out.append(_issue(store_id, "late_delivery", sup, as_of, ref, dn["cost_of_inaction_usd"]["high"], ev,
                          ["Late-order arrival is modelled as 1/2/3 days from today (assumption)."], opts, rec,
                          supplier_id=sup, supplier_name=snap.supplier_names.get(sup)))
    return out


def _recommended(issue: dict) -> dict | None:
    return next((o for o in issue.get("options") or [] if o.get("option_id") == issue.get("recommended_option_id")), None)


def _action_signature(issue: dict) -> tuple | None:
    """store + SKU + recommended action_type + the params that define the action; None when nothing is recommended."""
    rec = _recommended(issue)
    if rec is None or rec.get("action_type") == "do_nothing" or not issue.get("sku"):
        return None
    p = rec.get("params") or {}
    return (issue.get("store_id"), issue["sku"], rec["action_type"], p.get("supplier_id"), p.get("plan_qty", p.get("qty")))


def _rank(issue: dict) -> tuple:
    c = (_recommended(issue) or {}).get("confidence") or {}
    return (1 if (c.get("n_backtest") or 0) > 0 else 0, float(c.get("score") or 0.0), float(issue.get("severity_usd") or 0.0),
            issue["issue_id"])


def merge_same_action(issues: list[dict]) -> list[dict]:
    """One item per (store, SKU, recommended action): two detectors firing on the same root cause become one issue.
    The primary is the calibrated / higher-confidence one and keeps its issue_id; evidence and caveats are unioned."""
    groups: dict[tuple, list[dict]] = {}
    for i in issues:
        sig = _action_signature(i)
        if sig is not None:
            groups.setdefault(sig, []).append(i)
    drop: set[str] = set()
    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort(key=_rank, reverse=True)
        primary, rest = members[0], members[1:]
        seen = {(e.get("metric"), e.get("period")) for e in primary["evidence"]}
        for m in rest:
            primary["evidence"] += [e for e in m["evidence"] if (e.get("metric"), e.get("period")) not in seen
                                    and not seen.add((e.get("metric"), e.get("period")))]
            primary["data_caveats"] += [c for c in m["data_caveats"] if c not in primary["data_caveats"]]
            drop.add(m["issue_id"])
        primary["kinds"] = [primary["kind"], *[m["kind"] for m in rest if m["kind"] != primary["kind"]]]
        primary["merged_issue_ids"] = [m["issue_id"] for m in rest]
        primary["severity_usd"] = max(float(m.get("severity_usd") or 0.0) for m in members)
    out = [i for i in issues if i["issue_id"] not in drop]
    for i in out:
        i.setdefault("kinds", [i.get("kind")])
        i.setdefault("merged_issue_ids", [])
    return out
