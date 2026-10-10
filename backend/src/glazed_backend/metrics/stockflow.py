"""Stock flow over the next days: scheduled arrivals, next delivery, projected lost sales and the stock status rule.
Pure; every date it returns is after as_of and therefore a projection."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

STATUS_RULE = ("critical: la cobertura se agota antes de la próxima entrega; watch: la cobertura supera la entrega por "
               "menos de 1 día; ok: el resto")
FALLBACK_HORIZON_DAYS = 3


def arrivals_by_sku(pos: list[dict[str, Any]], as_of: date) -> dict[str, dict[date, float]]:
    """Open purchase orders known at as_of -> units arriving per date. An overdue order is counted for the next day,
    as the inventory projection does; receipts on or before as_of are already in the closing stock."""
    out: dict[str, dict[date, float]] = {}
    for p in pos:
        rec = p.get("received_date")
        if p["order_date"] > as_of or (rec is not None and rec <= as_of):
            continue
        d = max(p["expected_date"], as_of + timedelta(days=1))
        out.setdefault(p["sku"], {}).setdefault(d, 0.0)
        out[p["sku"]][d] += float(p["qty"])
    return out


def next_delivery(arrivals: dict[date, float], supplier_days: list[int] | None, as_of: date,
                  horizon: int = 14) -> tuple[date | None, str | None]:
    """(date, source): the first open purchase order, else the supplier's next scheduled delivery weekday."""
    if arrivals:
        return min(arrivals), "purchase_order"
    for i in range(1, horizon + 1):
        d = as_of + timedelta(days=i)
        if supplier_days and d.isoweekday() in supplier_days:
            return d, "supplier_schedule"
    return None, None


def project_lost_sales(on_hand: float, price: float, demand: list[tuple[float, float, float]],
                       arrivals: list[float]) -> list[dict[str, float]]:
    """USD of sales lost per day under the low/mid/high demand scenario (p10/p50/p90 of the forecast): stock opens the
    day with that day's arrivals, sells down to zero and the rest of the demand is lost."""
    out = [{"low": 0.0, "mid": 0.0, "high": 0.0} for _ in demand]
    for k, name in enumerate(("low", "mid", "high")):
        stock = max(on_hand, 0.0)
        for i, dem in enumerate(demand):
            stock += arrivals[i] if i < len(arrivals) else 0.0
            sold = min(stock, dem[k])
            out[i][name] = (dem[k] - sold) * price
            stock -= sold
    return out


def stock_status(cover_days: float | None, delivery: date | None, as_of: date, horizon: int = FALLBACK_HORIZON_DAYS) -> tuple[str, str]:
    """critical when the cover runs out before the next delivery, watch when it outlasts it by less than 1 day, ok
    otherwise. Without a known delivery the reference is the forecast window."""
    if cover_days is None:
        return "ok", "Sin demanda reciente: no hay riesgo de agotarse."
    days = (delivery - as_of).days if delivery else horizon
    ref = f"la próxima entrega ({delivery.isoformat()}, en {days} d)" if delivery else f"los próximos {horizon} días (sin entrega conocida)"
    if cover_days < days:
        return "critical", f"Crítico: la cobertura ({cover_days:.1f} d) se agota antes de {ref}."
    if cover_days < days + 1:
        return "watch", f"Vigilar: la cobertura ({cover_days:.1f} d) supera {ref} por menos de 1 día."
    return "ok", f"Cobertura suficiente ({cover_days:.1f} d) hasta {ref}."
