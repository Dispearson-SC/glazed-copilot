"""Units about to expire unsold. inventory_daily has no lot ages, so lots are inferred: the closing stock is assigned to
the newest receipts (as `inventory.usable_stock` does), each lot is sellable through received + shelf_life - 1 and is
written off the day after. Selling is oldest-first (FIFO) at the expected weekday demand; low/high waste use
demand +-0.84 sd (p80/p20). Pure; rows after `as_of` are ignored."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from .demand import SAMPLE_DAYS, uncensor, weekday_stats
from .types import DayRow

MAX_SHELF_LIFE_DAYS = 60  # a longer-lived SKU cannot expire inside a week-long window with any realistic lot age
Z_SPREAD = 0.84  # p80 / p20 of a normal
SCENARIOS = (("low", Z_SPREAD), ("mid", 0.0), ("high", -Z_SPREAD))  # z of demand: more demand means less waste


@dataclass(frozen=True)
class Lot:
    received: date
    qty: float
    last_sellable: date

    @property
    def expiry_date(self) -> date:
        return self.last_sellable + timedelta(days=1)


def infer_lots(closing: float, receipts: list[tuple[date, int]], shelf_life: int, as_of: date) -> list[Lot]:
    """Closing stock -> lots, newest receipts first; stock no receipt explains is assumed received yesterday."""
    lots: list[Lot] = []
    left = float(closing)
    for rd, qty in sorted(receipts, key=lambda r: r[0], reverse=True):
        take = min(left, float(qty))
        if take <= 0:
            continue
        lots.append(Lot(rd, take, rd + timedelta(days=shelf_life - 1)))
        left -= take
    if left > 0:
        rd = as_of - timedelta(days=1)
        lots.append(Lot(rd, left, rd + timedelta(days=shelf_life - 1)))
    return sorted(lots, key=lambda l: (l.last_sellable, l.received))


def _waste(lots: list[Lot], as_of: date, until: date, demand_on) -> dict[Lot, float]:
    """Units of each lot written off by `until` when the stock sells oldest-first at demand_on(day)."""
    left = {l: l.qty for l in lots}
    wasted: dict[Lot, float] = {}
    d = as_of + timedelta(days=1)
    while d <= until and left:
        for lot in [l for l in left if l.last_sellable < d]:
            wasted[lot] = left.pop(lot)
        need = demand_on(d)
        for lot in sorted(left, key=lambda l: (l.last_sellable, l.received)):
            take = min(need, left[lot])
            left[lot] -= take
            need -= take
        left = {l: q for l, q in left.items() if q > 1e-9}
        d += timedelta(days=1)
    return wasted


def expiring_items(sku: str, product: dict[str, Any], rows: list[DayRow], as_of: date, days: int,
                   open_hours: float) -> list[dict[str, Any]]:
    """One entry per lot written off within (as_of, as_of + days] that is not sold in time in at least one scenario."""
    life = product.get("shelf_life_days")
    known = sorted((r for r in rows if r.date <= as_of), key=lambda r: r.date)  # NO LOOK-AHEAD
    if life is None or not 0 < life <= MAX_SHELF_LIFE_DAYS or not known or known[-1].closing <= 0:
        return []
    until = as_of + timedelta(days=days)
    window = [r for r in known if r.date > as_of - timedelta(days=SAMPLE_DAYS)]
    demand = uncensor(window, open_hours).demand
    receipts = [(r.date, r.received) for r in known if r.received > 0 and r.date > as_of - timedelta(days=life)]
    lots = [l for l in infer_lots(known[-1].closing, receipts, life, as_of) if l.last_sellable >= as_of]
    if not lots:
        return []
    stats = {wd: weekday_stats(demand, as_of, wd) for wd in range(1, 8)}
    per = {name: _waste(lots, as_of, until, lambda d, z=z: max(0.0, stats[d.isoweekday()][0] + z * stats[d.isoweekday()][1]))
           for name, z in SCENARIOS}
    cost = float(product.get("unit_cost") or 0.0)
    out = []
    for lot in lots:
        units = {n: round(per[n].get(lot, 0.0), 2) for n, _ in SCENARIOS}
        if not as_of < lot.expiry_date <= until or units["high"] <= 0:
            continue
        out.append({"sku": sku, "product_name": product["product_name"], "expiring_units": round(lot.qty, 2),
                    "expiry_date": lot.expiry_date.isoformat(), "shelf_life_days": life, "waste_units": units,
                    "waste_usd": {n: round(u * cost, 2) for n, u in units.items()}, "lot_age_inferred": True,
                    "projected": True})
    return out


def summarize_expiry(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """(waste by expiry day, total waste), both as {low, mid, high} USD."""
    by_day: dict[str, dict[str, float]] = {}
    total = {"low": 0.0, "mid": 0.0, "high": 0.0}
    for it in items:
        day = by_day.setdefault(it["expiry_date"], {"low": 0.0, "mid": 0.0, "high": 0.0})
        for k in total:
            day[k] += it["waste_usd"][k]
            total[k] += it["waste_usd"][k]
    return ([{"date": d, "waste_usd": {k: round(v, 2) for k, v in w.items()}, "projected": True} for d, w in sorted(by_day.items())],
            {k: round(v, 2) for k, v in total.items()})
