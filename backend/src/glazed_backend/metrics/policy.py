"""Order quantity by shelf-life class: newsvendor (1 day), order-up-to (2-14 days), (s, S) (non-perishables)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import NormalDist

from .demand import horizon_demand
from .inventory import SkuState, is_short_life, usable_stock
from .schedule import first_delivery, next_delivery_after

_N = NormalDist()


def shelf_class(shelf_life: int | None) -> str:
    if shelf_life is not None and shelf_life <= 1:
        return "newsvendor"
    return "order_up_to" if is_short_life(shelf_life) else "sS"


def z_of(p: float) -> float:
    return _N.inv_cdf(min(0.999, max(0.001, p)))


def normal_quantile(mean: float, sd: float, p: float) -> float:
    return max(0.0, mean + z_of(p) * sd)


def loss_units(total: float, mean: float, sd: float) -> tuple[float, float]:
    """(expected leftover units, expected unmet units) when `total` units face demand ~ N(mean, sd)."""
    if sd <= 1e-9:
        return max(0.0, total - mean), max(0.0, mean - total)
    z = (total - mean) / sd
    under = sd * (_N.pdf(z) - z * (1.0 - _N.cdf(z)))
    return under + (total - mean), under


def round_to_cases(raw: float, case_size: int, base: float, mean: float, sd: float, cu: float, co: float) -> int:
    """Floor or ceil to whole cases, whichever has the lower expected cost Co*leftover + Cu*unmet."""
    case = max(1, case_size or 1)
    if raw <= 0:
        return 0
    lo = int(raw // case) * case
    hi = lo if lo == raw else lo + case

    def cost(q: int) -> float:
        over, under = loss_units(base + q, mean, sd)
        return co * over + cu * under
    return lo if cost(lo) <= cost(hi) else hi


@dataclass(frozen=True)
class Recommendation:
    method: str
    service: float
    qty_raw: float
    mean: float  # demand distribution over the cover window
    sd: float
    base: float  # usable stock + arrivals the order adds to
    usable: float
    arrivals: float
    cover_days: list[date]
    delivery: date  # arrival of an order placed at t
    next_delivery: date
    reorder_point: float | None = None
    order_up_to: float | None = None


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def delivery_window(state: SkuState) -> tuple[date, date]:
    sup, closed = state.supplier, state.store.closed_dates
    d1 = first_delivery(state.t, max(1, round(sup.lead_mean)), sup.delivery_days, closed)
    return d1, next_delivery_after(d1, sup.delivery_days, closed)


def recommend(state: SkuState, service: float) -> Recommendation:
    d1, d2 = delivery_window(state)
    sl = state.product.shelf_life_days
    method = shelf_class(sl)
    t = state.t
    receipts = [(r.date, r.received) for r in state.rows if r.received > 0]
    dem = state.censored.demand
    if method == "sS":
        return _recommend_sS(state, service, d1, d2)
    end = d1 if method == "newsvendor" else min(d2 - timedelta(days=1), d1 + timedelta(days=(sl or 1) - 1))
    end = max(end, d1)
    cover = [d1] if method == "newsvendor" else _days(t + timedelta(days=1), end)
    mean, sd = horizon_demand(dem, t, cover)
    usable = usable_stock(state.closing, receipts, sl, t, state.daily_mean, end)
    arrivals = state.arrivals_between(cover[0], end)
    raw = max(0.0, normal_quantile(mean, sd, service) - usable - arrivals)
    return Recommendation(method, service, raw, mean, sd, usable + arrivals, usable, arrivals, cover, d1, d2)


def _recommend_sS(state: SkuState, service: float, d1: date, d2: date) -> Recommendation:
    t, dem = state.t, state.censored.demand
    lead_days = _days(t + timedelta(days=1), d1)
    review_days = _days(d1 + timedelta(days=1), d2) if d2 > d1 else []
    mu_l, sd_l = horizon_demand(dem, t, lead_days)
    mu_r, sd_r = horizon_demand(dem, t, review_days) if review_days else (0.0, 0.0)
    mu_d = mu_l / max(1, len(lead_days))
    p = state.supplier.p_late  # lead time is nearly deterministic: +1 day with probability p_late
    mu_lead = mu_l + p * mu_d
    sd_lead = math.sqrt(sd_l ** 2 + (mu_d ** 2) * p * (1.0 - p))
    s = mu_lead + z_of(service) * sd_lead
    big_s = s + mu_r
    arrivals = float(sum(q for _, q in state.in_transit))
    position = float(state.closing) + arrivals
    raw = max(0.0, big_s - position) if position <= s else 0.0
    mean, sd = mu_lead + mu_r, math.sqrt(sd_lead ** 2 + sd_r ** 2)
    return Recommendation("sS", service, raw, mean, sd, position, float(state.closing), arrivals,
                          lead_days + review_days, d1, d2, reorder_point=s, order_up_to=big_s)
