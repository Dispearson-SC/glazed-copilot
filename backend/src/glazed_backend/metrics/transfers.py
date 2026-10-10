"""Inter-store transfer options. Pure: the adapter hands over per-store SKU states cut at the case date.

A transfer moves units that would expire unsold at the sender (projected surplus before expiry) to a nearby store
whose own projection runs short before its next delivery. Everything is the weekday demand model of the order plan,
nothing past as_of is read. All money is a {low, mid, high} range in USD."""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from .demand import weekday_stats
from .expiry import MAX_SHELF_LIFE_DAYS, expiring_items
from .inventory import SkuState
from .schedule import first_delivery

# $ fixed + $ per unit, and the days between the decision and the units landing at the receiver
COST = {"same_site": (15.0, 0.10), "cross_site": (35.0, 0.20)}
LEAD_DAYS = {"same_site": 1, "cross_site": 2}
Z = {"low": -0.674, "mid": 0.0, "high": 0.674}  # receiver demand scenarios (P25 / P50 / P75)
LEVELS = ("low", "mid", "high")

REASONS_ES = {
    "no_surplus": "Ningún producto de esta tienda tiene unidades que caduquen sin venderse con el ritmo de venta esperado.",
    "no_surplus_sku": "Este producto no proyecta unidades sin vender antes de caducar (o no es perecedero).",
    "no_candidates": "No hay otra tienda de la misma región abierta y con inventario de este producto.",
    "no_receiver_deficit": "Ninguna tienda cercana proyecta faltante antes de su próxima entrega, o el faltante llega después de que "
                           "las unidades se echarían a perder.",
    "not_profitable": "Hay faltante y sobrante, pero el traslado cuesta más de lo que evita (neto no positivo).",
}


@dataclass(frozen=True)
class Receiver:
    store_id: str
    name: str
    same_site: bool
    state: SkuState


def assumptions() -> dict[str, Any]:
    return {
        "transfer_cost_usd": {"same_site": {"fixed": COST["same_site"][0], "per_unit": COST["same_site"][1]},
                              "cross_site": {"fixed": COST["cross_site"][0], "per_unit": COST["cross_site"][1]}},
        "lead_days": dict(LEAD_DAYS),
        "surplus": "Units projected to expire unsold at the sender (FIFO lots inferred from receipts, weekday demand).",
        "deficit": "Units the receiver's weekday demand exceeds its stock plus open orders, from the day the transfer "
                   "lands until its next supplier delivery.",
        "net": "waste avoided at the sender's unit cost + lost sales avoided at the receiver's margin - transfer cost; "
               "ranges pair low with low and high with high.",
        "confidence": "No transfer backtest exists: uncalibrated, score 0.3.",
        "scope": "Stores of the same region that are open on the case date and sell the SKU (same site preferred).",
    }


def transfer_cost(qty: int, same_site: bool) -> float:
    fixed, per_unit = COST["same_site" if same_site else "cross_site"]
    return round(fixed + per_unit * qty, 2)


def sender_surplus(state: SkuState, lead: int) -> dict[str, Any] | None:
    """Unsold-before-expiry units of one SKU, per scenario, split in all lots and the lots that can still be sold after
    `lead` days of transit. None when the SKU cannot expire inside its shelf life or nothing is left over."""
    p = state.product
    life = p.shelf_life_days
    if life is None or not 0 < life <= MAX_SHELF_LIFE_DAYS:
        return None
    items = expiring_items(p.sku, {"product_name": p.name, "shelf_life_days": life, "unit_cost": p.unit_cost},
                           list(state.rows), state.t, life, state.store.open_hours)
    if not items:
        return None
    arrival = state.t + timedelta(days=lead)
    elig = [i for i in items if date.fromisoformat(i["expiry_date"]) > arrival]
    total = lambda rows, k: round(sum(i["waste_units"][k] for i in rows), 2)  # noqa: E731
    return {"all": {k: total(items, k) for k in LEVELS}, "eligible": {k: total(elig, k) for k in LEVELS},
            "first_expiry": min((i["expiry_date"] for i in elig), default=None),
            "last_sellable": max((date.fromisoformat(i["expiry_date"]) - timedelta(days=1) for i in elig), default=None)}


def receiver_deficit(state: SkuState, arrival: date) -> dict[str, Any] | None:
    """Units short from `arrival` to the day before the receiver's next supplier delivery, per demand scenario."""
    sup, closed = state.supplier, state.store.closed_dates
    end = first_delivery(state.t + timedelta(days=1), max(1, round(sup.lead_mean)), sup.delivery_days, closed) - timedelta(days=1)
    end = max(end, state.t + timedelta(days=1))
    if end < arrival:
        return None
    out = {}
    for name, z in Z.items():
        stock, short, d = float(state.closing), 0.0, state.t + timedelta(days=1)
        while d <= end:
            stock += state.arrivals_between(d, d)
            mean, sd = weekday_stats(state.censored.demand, state.t, d.isoweekday())
            need = max(0.0, mean + z * sd)
            if d >= arrival:
                short += max(0.0, need - max(0.0, stock))
            stock = max(0.0, stock - need)
            d += timedelta(days=1)
        out[name] = round(short, 2)
    return {"units": out, "until": end.isoformat()}


def _range(fn) -> dict[str, float]:
    return {k: round(fn(k), 2) for k in LEVELS}


def build_option(sender: SkuState, s_name: str, from_store: str, rx: Receiver, as_of: date) -> tuple[dict[str, Any] | None, str]:
    """(option, reason). The option is None with the reason it was dropped."""
    lead = LEAD_DAYS["same_site" if rx.same_site else "cross_site"]
    sur = sender_surplus(sender, lead)
    if sur is None or math.floor(sur["eligible"]["mid"]) < 1:
        return None, "no_surplus_sku"
    deficit = receiver_deficit(rx.state, as_of + timedelta(days=lead))
    if deficit is None or deficit["units"]["mid"] <= 0:
        return None, "no_receiver_deficit"
    qty = int(min(math.floor(sur["eligible"]["mid"]), math.ceil(deficit["units"]["mid"])))
    if qty < 1:
        return None, "no_receiver_deficit"
    sp, rp = sender.product, rx.state.product
    cost = transfer_cost(qty, rx.same_site)
    waste = _range(lambda k: min(qty, sur["eligible"][k]) * sp.unit_cost)
    lost = _range(lambda k: min(qty, deficit["units"][k]) * max(0.0, rp.price - rp.unit_cost))
    net = _range(lambda k: waste[k] + lost[k] - cost)
    if net["mid"] <= 0:
        return None, "not_profitable"
    ship_by = min(date.fromisoformat(deficit["until"]) - timedelta(days=lead),
                  (sur["last_sellable"] or as_of) - timedelta(days=lead))
    expires = max(as_of, ship_by)
    oid = hashlib.sha256(f"{from_store}|{rx.store_id}|{sp.sku}|{as_of}|{qty}".encode()).hexdigest()[:12]
    return {
        "option_id": oid, "sku": sp.sku, "product_name": sp.name, "from_store": from_store, "to_store": rx.store_id,
        "to_store_name": rx.name, "qty": qty, "surplus_units": round(sur["eligible"]["mid"], 1),
        "deficit_units": round(deficit["units"]["mid"], 1), "transfer_cost_usd": cost,
        "waste_avoided_usd": waste, "lost_sales_avoided_usd": lost, "net_usd": net,
        "confidence": {"score": 0.3, "calibrated": False}, "expires_on": expires.isoformat(),
        "same_site": rx.same_site, "lead_days": lead, "all_waste_usd": _range(lambda k: sur["all"][k] * sp.unit_cost),
        "rationale_es": (f"{s_name}: ~{sur['eligible']['mid']:.0f} unidades de {sp.name} caducarían sin venderse; "
                         f"{rx.name} se quedaría corto ~{deficit['units']['mid']:.0f} antes de su próxima entrega "
                         f"({deficit['until']}). Trasladar {qty} cuesta ${cost:,.2f} y evita ~${waste['mid']:,.2f} de merma "
                         f"y ~${lost['mid']:,.2f} de venta perdida."),
    }, ""


def compute(sender_states: dict[str, SkuState], from_store: str, from_name: str, receivers: dict[str, list[Receiver]],
            as_of: date) -> dict[str, Any]:
    """Every option of the store, best first, plus per-SKU waste at stake and the reason a SKU produced none.
    `receivers` maps sku -> the stores of the region that sell it."""
    options: list[dict[str, Any]] = []
    waste: dict[str, dict[str, float]] = {}
    reasons: dict[str, str] = {}
    for sku, state in sender_states.items():
        sur = sender_surplus(state, min(LEAD_DAYS.values()))
        if sur is None or sur["all"]["high"] <= 0:
            reasons[sku] = "no_surplus_sku"
            continue
        waste[sku] = _range(lambda k: sur["all"][k] * state.product.unit_cost)
        rxs = receivers.get(sku) or []
        if not rxs:
            reasons[sku] = "no_candidates"
            continue
        got, dropped = [], set()
        for rx in rxs:
            opt, reason = build_option(state, from_name, from_store, rx, as_of)
            if opt is not None:
                got.append(opt)
            else:
                dropped.add(reason)
        options += got
        if not got:
            reasons[sku] = "not_profitable" if "not_profitable" in dropped else "no_receiver_deficit"
    options.sort(key=lambda o: (-o["net_usd"]["mid"], not o["same_site"], o["option_id"]))
    return {"options": options, "waste": waste, "reasons": reasons}


def transfer_issue_options(issue_id: str, opts: list[dict[str, Any]], as_of: date, waste_mid: float) -> list[dict[str, Any]]:
    """Issue options (the shape of every other issue): one transfer per receiver plus do_nothing."""
    from .options import _do_nothing, make_option
    out = []
    for o in opts:
        gross = {k: o["waste_avoided_usd"][k] + o["lost_sales_avoided_usd"][k] for k in LEVELS}
        ev = {"benefit": gross, "cost_usd": o["transfer_cost_usd"], "net_mid": o["net_usd"]["mid"],
              "waste_delta": -o["waste_avoided_usd"]["mid"], "lost_delta": -o["lost_sales_avoided_usd"]["mid"]}
        params = {"sku": o["sku"], "from_store": o["from_store"], "to_store": o["to_store"], "to_store_name": o["to_store_name"], "qty": o["qty"],
                  "expires_on": o["expires_on"], "transfer_cost_usd": o["transfer_cost_usd"], "decision_date": as_of.isoformat()}
        opt = make_option(issue_id, "transfer_stock", params, ev,
                          {"deadline_date": o["expires_on"], "reason": "Ship before the units lose shelf life or the receiver restocks."},
                          ["Transfer lead time and cost are assumptions.", "The receiver may restock before the units land."])
        opt["option_id"] = o["option_id"]  # the id the transfer routes already served
        opt["rationale_es"] = o["rationale_es"]
        out.append(opt)
    out.append(_do_nothing(issue_id, waste_mid, 0.0, "Expected waste of the surplus units if they stay."))
    return out
