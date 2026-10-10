"""Per-SKU decision state, FIFO usable stock and the inventory projection."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from functools import cached_property
from typing import Callable

from .demand import CensoredDemand, uncensor
from .types import DayRow, Product, StoreInfo, SupplierProfile

MAX_PERISHABLE_DAYS = 14


@dataclass(frozen=True)
class SkuState:
    """Everything known about one SKU at the end of day t (nothing later)."""
    product: Product
    t: date
    rows: tuple[DayRow, ...]
    in_transit: tuple[tuple[date, int], ...]  # (projected arrival date, qty): from the PO's expected date, never the real receipt
    supplier: SupplierProfile
    store: StoreInfo

    @cached_property
    def censored(self) -> CensoredDemand:
        return uncensor(list(self.rows), self.store.open_hours)

    @property
    def closing(self) -> int:
        return self.rows[-1].closing if self.rows else 0

    def arrival(self, eta: date) -> date:
        """An order already past its expected date is assumed to land tomorrow."""
        return max(eta, self.t + timedelta(days=1))

    def arrivals_between(self, start: date, end: date) -> float:
        return float(sum(q for eta, q in self.in_transit if start <= self.arrival(eta) <= end))

    def daily_mean(self, d: date) -> float:
        from .demand import weekday_stats
        return weekday_stats(self.censored.demand, self.t, d.isoweekday())[0]


def is_short_life(shelf_life: int | None) -> bool:
    return shelf_life is not None and shelf_life <= MAX_PERISHABLE_DAYS


def usable_stock(closing: float, receipts: list[tuple[date, int]], shelf_life: int | None, ref: date,
                 daily_mean: Callable[[date], float], until: date) -> float:
    """Stock on hand that can still be used, approximating FIFO from received_qty and shelf life.

    inventory_daily does not store lot ages, so the closing stock is assigned to the newest receipts. Each lot
    is sellable through (received + shelf_life - 1). Selling oldest-first at the expected daily demand, units
    whose lot expires before they sell are not usable."""
    if closing <= 0:
        return 0.0
    if not is_short_life(shelf_life):
        return float(closing)
    lots: list[list[float]] = []  # [last_sellable_ordinal, qty]
    left = float(closing)
    for rd, qty in sorted(receipts, key=lambda r: r[0], reverse=True):
        if left <= 0:
            break
        take = min(left, float(qty))
        if take > 0:
            lots.append([(rd + timedelta(days=shelf_life - 1)).toordinal(), take])
            left -= take
    if left > 0:  # age unknown: assume it arrived yesterday
        lots.append([(ref + timedelta(days=shelf_life - 2)).toordinal(), left])
    lots.sort(key=lambda lot: lot[0])
    wasted = 0.0
    d = ref + timedelta(days=1)
    while d <= until and lots:
        for lot in list(lots):
            if lot[0] < d.toordinal():
                wasted += lot[1]
                lots.remove(lot)
        need = daily_mean(d)
        for lot in lots:
            take = min(need, lot[1])
            lot[1] -= take
            need -= take
        lots = [lot for lot in lots if lot[1] > 1e-9]
        d += timedelta(days=1)
    return max(0.0, float(closing) - wasted)


def expiring_units(state: SkuState, horizon: int | None = None) -> float:
    """Units on hand that expire unsold within the shelf-life horizon at expected demand."""
    sl = state.product.shelf_life_days
    if not is_short_life(sl) or state.closing <= 0:
        return 0.0
    until = state.t + timedelta(days=horizon or max(1, sl))
    receipts = [(r.date, r.received) for r in state.rows if r.received > 0]
    return max(0.0, state.closing - usable_stock(state.closing, receipts, sl, state.t, state.daily_mean, until))
