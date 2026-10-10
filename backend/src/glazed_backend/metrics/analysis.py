"""Deterministic Spanish analysis of an issue: pure templates over numbers that glazed_metrics already computed.
The recommendation is the best option by net_usd_mid, compared explicitly with doing nothing."""
from __future__ import annotations

import re
from typing import Any

APPROVAL_TIERS = ("N2", "N3")


def usd(x: float | None) -> str:
    if x is None:
        return "s/d"
    sign = "-" if x < 0 else ""
    x = abs(float(x))
    return f"{sign}${x:,.0f}" if x >= 100 else f"{sign}${x:,.2f}"


_TITLES = {"stockout_risk": "Riesgo de desabasto", "overstock_waste": "Sobreinventario y merma", "expiring": "Producto por caducar",
           "inflated_order": "Pedido inflado", "late_delivery": "Entrega retrasada", "min_order": "Pedido mínimo",
           "staffing": "Personal", "misleading_promo": "Promoción engañosa", "promo": "Promoción",
           "calendar_uplift": "Efecto de calendario", "supplier_variability": "Proveedor variable",
           "short_shipment": "Entrega incompleta", "sku_key_mismatch": "Inconsistencia de SKU", "orphan_sku": "SKU huérfano",
           "compliance_deviation": "Desviación de cumplimiento",
           "transfer_opportunity": "Oportunidad de traslado"}
_RISKS = [
    (re.compile(r"Supplier late on (\d+%) of orders\."), r"El proveedor se retrasa en \1 de los pedidos."),
    (re.compile(r"May leave ~\$([\d,.]+) of waste\."), r"Puede dejar ~$\1 de merma."),
    (re.compile(r"Ordering below a full case may need the supplier's agreement\."), "Pedir menos de una caja completa puede requerir el acuerdo del proveedor."),
    (re.compile(r"Lower stock raises the chance of a stockout\."), "Menos inventario aumenta la probabilidad de desabasto."),
    (re.compile(r"Skipping an order can cause a stockout before the next delivery\."), "Omitir el pedido puede causar un desabasto antes de la próxima entrega."),
    (re.compile(r"Sell-through at a discount is an assumption.*"), "La venta con descuento es un supuesto (no hay historial de rebajas ni datos por hora)."),
    (re.compile(r"Lift is estimated from (\d+) past promotion\(s\) in this scope \(confidence (\w+)\); the method's noise floor is \+-10 points\."),
     r"El efecto se estima con \1 promoción(es) pasada(s) del mismo alcance (confianza \2); el piso de ruido del método es de ±10 puntos."),
    (re.compile(r"A promotion also discounts the units that would have sold at full price\."), "La promoción también rebaja las unidades que se habrían vendido a precio completo."),
    (re.compile(r"The discount is deeper than any past promotion in this scope: the lift is extrapolated\."), "El descuento es mayor que el de cualquier promoción pasada del alcance: el efecto es una extrapolación."),
    (re.compile(r"Sell-through follows the lift of (\d+) past promotion\(s\) in this scope \((\d+)% at (\d+)% off, confidence (\w+)\); noise floor \+-10 points\."),
     r"La venta con descuento sigue el efecto de \1 promoción(es) pasada(s) del alcance (\2% con \3% de descuento, confianza \4); piso de ruido ±10 puntos."),
    (re.compile(r"The late order may arrive first and leave surplus\."), "El pedido atrasado puede llegar primero y dejar excedente."),
    (re.compile(r"Stock is held one extra day\."), "El inventario se mantiene un día más."),
    (re.compile(r"Values are per day, averaged over the 2-day cycle\."), "Los valores son por día, promediados en el ciclo de 2 días."),
]


def risk_es(text: str) -> str:
    for pat, rep in _RISKS:
        if pat.fullmatch(text):
            return pat.sub(rep, text)
    return text


def _name(issue: dict[str, Any]) -> str:
    return issue.get("product_name") or issue.get("supplier_name") or issue.get("sku") or issue.get("supplier_id") or "este elemento"


def label(o: dict[str, Any], issue: dict[str, Any]) -> str:
    p, name = o.get("params") or {}, _name(issue)
    qty, at = p.get("qty"), o["action_type"]
    if at == "place_order":
        return f"Pedir {int(qty)} unidades de {name}" if qty is not None else f"Hacer el pedido de {name}"
    if at == "adjust_order_qty":
        return f"Ajustar el pedido de {name} a {int(qty)} unidades" if qty is not None else f"Ajustar el pedido de {name}"
    if at == "skip_order":
        return f"Omitir el pedido de {name} en este ciclo"
    if at == "markdown_end_of_day":
        return f"Rebajar {name} {p.get('discount_pct', '')}% al cierre ({p.get('units', '?')} unidades)".replace("  ", " ")
    if at == "activate_promo":
        days = p.get('days', '?')
        return f"Activar promoción de {p.get('discount_pct', '')}% en {name} por {days} {'día' if days == 1 else 'días'}".replace("  ", " ")
    if at == "do_nothing":
        return "No hacer nada"
    return {"run_promo": f"Lanzar promoción en {name}", "transfer_stock": (f"Trasladar {int(qty)} unidades de {name} a {p.get('to_store_name') or p['to_store']}" if qty is not None and p.get("to_store")
                                      else f"Transferir inventario de {name}"),
            "shift_staff_hours": "Mover horas de personal", "data_fix_task": "Corregir el dato en el sistema"}.get(at, at)


def _ev(issue: dict[str, Any], metric: str) -> Any:
    return next((e.get("value") for e in issue.get("evidence", []) if e.get("metric") == metric), None)


def problem_text(issue: dict[str, Any]) -> str:
    kind, name = issue.get("kind"), _name(issue)
    sev = usd(issue.get("severity_usd"))
    if kind == "stockout_risk":
        d = _ev(issue, "projected_stockout_date")
        when = f" alrededor del {d}" if d else " antes de la próxima entrega"
        return f"{name} se quedaría sin inventario{when}. Sin acción, la pérdida esperada es {sev}."
    if kind == "overstock_waste":
        return f"Se recibe más {name} del que se vende y la merma de los últimos 14 días fue de {usd(_ev(issue, 'waste_usd_14d'))}."
    if kind == "expiring":
        return f"Hay {_ev(issue, 'expiring_units')} unidades de {name} por caducar; valen {sev} si no se venden."
    if kind == "inflated_order":
        opt = _ev(issue, "optimum_qty")
        target = "no hace falta pedir en este ciclo" if not opt else f"el óptimo es de {opt:g} unidades"
        return f"El pedido de {name} ({_ev(issue, 'ordered_qty')} unidades) es mayor al necesario: {target}; el costo esperado es {sev}."
    if kind == "late_delivery":
        return f"Hay {_ev(issue, 'overdue_lines')} líneas vencidas de {name}, con hasta {_ev(issue, 'max_days_late')} días de retraso; exposición {sev}."
    if kind == "transfer_opportunity":
        top = next((o for o in issue.get("options") or [] if o.get("action_type") == "transfer_stock"), None)
        return (top or {}).get("rationale_es") or f"Hay unidades de {name} que se perderían y otra tienda las necesita; valen {sev}."
    return f"{_TITLES.get(kind, str(kind).replace('_', ' '))}: {name}. Impacto estimado {sev}."


def title_text(issue: dict[str, Any]) -> str:
    return f"{_TITLES.get(issue.get('kind'), str(issue.get('kind')).replace('_', ' ').capitalize())}: {_name(issue)}"


def _net_range(o: dict[str, Any]) -> dict[str, float]:
    ben, cost = o.get("expected_benefit_usd") or {}, float(o.get("cost_usd") or 0.0)
    mid = float(o.get("net_usd_mid") or 0.0)
    if o["action_type"] == "do_nothing":
        return {"low": 0.0, "mid": 0.0, "high": 0.0}
    lo = round(float(ben["low"]) - cost, 2) if ben.get("low") is not None else mid
    hi = round(float(ben["high"]) - cost, 2) if ben.get("high") is not None else mid
    return {"low": min(lo, mid), "mid": mid, "high": max(hi, mid)}


def pick_best(options: list[dict[str, Any]]) -> dict[str, Any]:
    """Best action by net_usd_mid; do nothing wins unless an action strictly beats it."""
    dn = next((o for o in options if o["action_type"] == "do_nothing"), None)
    acts = [o for o in options if o["action_type"] != "do_nothing"]
    best = max(acts, key=lambda o: (float(o.get("net_usd_mid") or 0), o["option_id"]), default=None)
    if best is None:
        return dn if dn is not None else options[0]
    if dn is not None and float(best.get("net_usd_mid") or 0) <= float(dn.get("net_usd_mid") or 0):
        return dn
    return best


def _pros(o: dict[str, Any]) -> list[str]:
    if o["action_type"] == "do_nothing":
        return ["No requiere gasto ni acción."]
    n, rng = float(o.get("net_usd_mid") or 0), _net_range(o)
    out = [f"Efecto neto esperado {usd(n)} (rango {usd(rng['low'])} a {usd(rng['high'])})."]
    li = o.get("loss_impact") or {}
    if (li.get("waste_usd_delta") or 0) < -0.005:
        out.append(f"Reduce la merma en {usd(-li['waste_usd_delta'])}.")
    if (li.get("lost_sales_usd_delta") or 0) < -0.005:
        out.append(f"Evita {usd(-li['lost_sales_usd_delta'])} de venta perdida.")
    c = o.get("confidence") or {}
    if (c.get("n_backtest") or 0) > 0:
        out.append(f"Respaldado por {c['n_backtest']} casos de backtest (confianza {c.get('score', 0):.0%}).")
    return out


def _cons(o: dict[str, Any], dn: dict[str, Any] | None) -> list[str]:
    if o["action_type"] == "do_nothing":
        return [f"Costo esperado de no actuar: {usd(o.get('cost_usd'))}."]
    out = []
    if float(o.get("cost_usd") or 0) > 0:
        out.append(f"Requiere un desembolso de {usd(o['cost_usd'])}.")
    out += [risk_es(r) for r in o.get("risk") or []]
    c = o.get("confidence") or {}
    if (c.get("n_backtest") or 0) == 0:
        out.append("Sin respaldo de backtest para esta acción: la confianza no está calibrada.")
    if c.get("noise_capped"):
        out.append("El efecto medido en backtest es menor que el ruido: la confianza se limita.")
    return out


def build_analysis(issue: dict[str, Any]) -> dict[str, Any]:
    options = issue["options"]
    best = pick_best(options)
    dn = next((o for o in options if o["action_type"] == "do_nothing"), None)
    conf = best.get("confidence") or {}
    tier = best.get("tier")
    rng = _net_range(best)
    inaction = float((dn or {}).get("cost_usd") or 0.0)
    if best["action_type"] == "do_nothing":
        why = (f"Ninguna acción supera a no hacer nada: la mejor alternativa rinde "
               f"{usd(max((float(o.get('net_usd_mid') or 0) for o in options if o is not best), default=0.0))} netos.")
        accept = "Si lo apruebas no se ejecuta nada y se registra como estado saludable."
    else:
        why = (f"Es la opción con mayor efecto neto esperado ({usd(best.get('net_usd_mid'))}) frente a no hacer nada, "
               f"que cuesta {usd(inaction)}.")
        accept = (f"Si apruebas: {label(best, issue)}. Efecto neto esperado {usd(best.get('net_usd_mid'))} "
                  f"(entre {usd(rng['low'])} y {usd(rng['high'])}).")
    li = (dn or {}).get("loss_impact") or {}
    parts = []
    if (li.get("waste_usd_delta") or 0) > 0:
        parts.append(f"merma {usd(li['waste_usd_delta'])}")
    if (li.get("lost_sales_usd_delta") or 0) > 0:
        parts.append(f"venta perdida {usd(li['lost_sales_usd_delta'])}")
    not_act = f"Si no actúas: pérdida esperada {usd(inaction)}" + (f" ({', '.join(parts)})" if parts else "") + "."
    return {"issue_id": issue["issue_id"], "title": title_text(issue), "tier": tier,
            "deadline": (best.get("urgency") or {}).get("deadline_date"), "impact_usd": rng,
            "confidence": {"score": conf.get("score"), "calibrated": (conf.get("n_backtest") or 0) > 0},
            "problem": problem_text(issue),
            "recommendation": {"option_id": best["option_id"], "label": label(best, issue),
                               "action_type": best["action_type"], "params": best.get("params") or {}},
            "pros": _pros(best), "cons": _cons(best, dn), "requires_approval": tier in APPROVAL_TIERS,
            "dialog": {"why": why, "if_accept": accept, "if_not_act": not_act,
                       "alternatives": [{"option_id": o["option_id"], "label": label(o, issue),
                                         "net_usd_mid": o.get("net_usd_mid"), "action_type": o["action_type"],
                                         "params": o.get("params") or {}, "data_caveat": o.get("data_caveat")}
                                        for o in options if o is not best]}}
