"""Pending decisions of the manager inbox: approvals (N2/N3 issues) and technical items (order-plan lines and N1
options). Pure: Spanish templates over the numbers glazed_metrics already computed."""
from __future__ import annotations

from typing import Any

from .analysis import APPROVAL_TIERS, build_analysis, label, pick_best, usd


def approval_item(issue: dict[str, Any]) -> dict[str, Any] | None:
    """The issue plus its winning option when that option is an action that needs approval (N2/N3)."""
    a = build_analysis(issue)
    if a["recommendation"]["action_type"] == "do_nothing" or a["tier"] not in APPROVAL_TIERS:
        return None
    return {k: a[k] for k in ("issue_id", "title", "tier", "deadline", "impact_usd", "confidence", "problem",
                              "recommendation", "requires_approval")} | {"kind": issue.get("kind"), "sku": issue.get("sku"),
                                                                        "product_name": issue.get("product_name"),
                                                                        "kinds": issue.get("kinds") or [issue.get("kind")],
                                                                        "merged_issue_ids": issue.get("merged_issue_ids") or []}


def technical_from_issue(issue: dict[str, Any]) -> dict[str, Any] | None:
    """An N1 (or lower) winning action outside the order plan."""
    a = build_analysis(issue)
    if a["recommendation"]["action_type"] == "do_nothing" or a["tier"] in APPROVAL_TIERS:
        return None
    best = pick_best(issue["options"])
    p = best.get("params") or {}
    return {"issue_id": issue["issue_id"], "option_id": best["option_id"], "sku": issue.get("sku"),
            "action_type": best["action_type"], "kinds": issue.get("kinds") or [issue.get("kind")],
            "merged_issue_ids": issue.get("merged_issue_ids") or [], "product_name": issue.get("product_name"), "supplier_id": issue.get("supplier_id"),
            "supplier_name": issue.get("supplier_name"), "qty": p.get("qty"), "expected_delivery": None,
            "cost_usd": {"low": best.get("cost_usd") or 0.0, "mid": best.get("cost_usd") or 0.0, "high": best.get("cost_usd") or 0.0},
            "why": a["dialog"]["why"], "impact_chips": [f"Efecto neto esperado {usd(best.get('net_usd_mid'))}"],
            "deadline": a["deadline"], "confidence": a["confidence"], "tier": a["tier"],
            "label": a["recommendation"]["label"]}


def line_warning(line: dict[str, Any]) -> tuple[str | None, list[str]]:
    parts, codes = [], []
    m = line.get("min_order_warning")
    if m:
        who = line.get("supplier_name") or line.get("supplier_id")
        parts.append(f"El pedido a {who} ({usd(m.get('order_value_usd'))}) está por debajo del mínimo del proveedor "
                     f"({usd(m.get('min_order_value'))}); conviene consolidarlo con la siguiente entrega. Es un aviso, no un bloqueo.")
        codes.append("below_min_order")
    if line.get("order_deadline_status") == "deadline_passed":
        parts.append(f"La fecha límite para pedir ya pasó; la entrega más temprana es el {line.get('expected_delivery')}.")
        codes.append("deadline_passed")
    return (" ".join(parts) or None), codes


def _chips(line: dict[str, Any]) -> list[str]:
    chips = []
    lost = (line.get("expected_lost_sales_usd") or {}).get("mid")
    waste = (line.get("expected_waste_usd") or {}).get("mid")
    if lost:
        chips.append(f"Venta perdida esperada {usd(lost)}")
    if waste:
        chips.append(f"Merma esperada {usd(waste)}")
    if line.get("stockout_risk_without_order") is not None:
        chips.append(f"Riesgo de desabasto sin pedido {line['stockout_risk_without_order']:.0%}")
    return chips


def _do_nothing_of(issue: dict[str, Any] | None) -> dict[str, Any] | None:
    """The issue's do_nothing option as the order-line comparison (absolute expected losses of not acting)."""
    dn = next((o for o in (issue or {}).get("options") or [] if o.get("action_type") == "do_nothing"), None)
    if dn is None:
        return None
    imp = dn.get("loss_impact") or {}
    waste, lost = float(imp.get("waste_usd_delta") or 0.0), float(imp.get("lost_sales_usd_delta") or 0.0)
    cost = float((dn.get("cost_of_inaction_usd") or {}).get("mid", dn.get("cost_usd") or 0.0))
    return {"net_usd_mid": round(-cost, 2), "expected_lost_sales_usd": {"mid": round(lost, 2)},
            "expected_waste_usd": {"mid": round(waste, 2)}}


def technical_from_line(line: dict[str, Any], issue: dict[str, Any] | None) -> dict[str, Any]:
    name = line.get("product_name") or line.get("name") or line["sku"]
    qty, cost = line.get("qty"), float(line.get("est_cost_usd") or 0.0)
    rng = line.get("qty_range") or {}
    lo, hi = (cost * rng["low"] / qty, cost * rng["high"] / qty) if qty and rng.get("low") is not None and rng.get("high") is not None else (cost, cost)
    stock = line.get("projected_stockout_date")
    why = (f"{name} se agotaría el {stock} sin pedido" if stock else f"{name} necesita reposición") + \
          f"; el pedido llega el {line.get('expected_delivery')}."
    warning, codes = line_warning(line)
    best = pick_best(issue["options"]) if issue and issue.get("options") else None
    bc = (best or {}).get("confidence") or {}
    conf = line.get("confidence") if isinstance(line.get("confidence"), dict) else (
        {"score": bc.get("score"), "calibrated": (bc.get("n_backtest") or 0) > 0} if bc else None)
    conf = {"score": conf.get("score"), "calibrated": conf.get("calibrated")} if conf else None
    out = {"issue_id": (issue or {}).get("issue_id"), "option_id": (best or {}).get("option_id"), "sku": line["sku"],
           "product_name": name, "supplier_id": line.get("supplier_id"), "supplier_name": line.get("supplier_name"),
           "qty": qty, "expected_delivery": line.get("expected_delivery"),
           "cost_usd": {"low": round(min(lo, cost), 2), "mid": round(cost, 2), "high": round(max(hi, cost), 2)},
           "why": why, "impact_chips": _chips(line), "deadline": line.get("order_deadline"), "confidence": conf,
           "do_nothing": line.get("do_nothing") or _do_nothing_of(issue), "lead_time_days": line.get("lead_time_days"),
           "next_delivery_date": line.get("next_delivery_date") or line.get("expected_delivery"),
           "min_order_warning": line.get("min_order_warning"),
           "tier": (best or {}).get("tier"), "label": label(best, issue) if best and issue else f"Pedir {qty} unidades de {name}"}
    if warning:
        out["warning"], out["warning_codes"] = warning, codes
    return out
