"""A store's data as loaded by the adapter, cut to any decision day without looking at later information."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import median

from .inventory import SkuState
from .schedule import supplier_profile
from .types import DayRow, Product, PurchaseOrder, StoreInfo, SupplierProfile


@dataclass
class StoreSnapshot:
    store: StoreInfo
    products: dict[str, Product]
    rows: dict[str, list[DayRow]]  # per SKU, sorted by date
    pos: list[PurchaseOrder]  # received_date is only filled when it is <= the snapshot's as_of
    suppliers: dict[str, tuple[frozenset[int], int, float]]  # id -> (delivery days, standard lead, min order value)
    supplier_names: dict[str, str] = field(default_factory=dict)
    _by_sku: dict[str, list[PurchaseOrder]] = field(default_factory=dict, repr=False)
    _by_sup: dict[str, list[PurchaseOrder]] = field(default_factory=dict, repr=False)
    _profiles: dict[tuple[str, date], SupplierProfile] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        for p in self.pos:
            self._by_sku.setdefault(p.sku, []).append(p)
            sup = self.products[p.sku].supplier_id if p.sku in self.products else None
            if sup:
                self._by_sup.setdefault(sup, []).append(p)

    def profile(self, supplier_id: str, t: date) -> SupplierProfile:
        key = (supplier_id, t)
        if key not in self._profiles:
            days, lead, mov = self.suppliers.get(supplier_id, (frozenset(range(1, 8)), 1, 0.0))
            self._profiles[key] = supplier_profile(supplier_id, self._by_sup.get(supplier_id, []), t, days, lead, mov)
        return self._profiles[key]

    def in_transit(self, sku: str, t: date) -> tuple[tuple[date, int], ...]:
        return tuple((p.expected_date, p.qty_ordered) for p in self._by_sku.get(sku, [])
                     if p.order_date <= t and (p.received_date is None or p.received_date > t))

    def state_at(self, sku: str, t: date, history_days: int = 56) -> SkuState | None:
        prod = self.products.get(sku)
        rows = tuple(r for r in self.rows.get(sku, []) if t - timedelta(days=history_days) < r.date <= t)
        if prod is None or not rows:
            return None
        return SkuState(prod, t, rows, self.in_transit(sku, t), self.profile(prod.supplier_id, t), self.store)

    def typical_order_qty(self, sku: str, t: date, n: int = 8) -> float | None:
        qs = [p.qty_ordered for p in self._by_sku.get(sku, []) if p.order_date <= t][-n:]
        return float(median(qs)) if qs else None

    def window_totals(self, sku: str, t: date, days: int = 28) -> tuple[float, float]:
        """(received, sold) units over the last `days` days up to t."""
        rs = [r for r in self.rows.get(sku, []) if t - timedelta(days=days) < r.date <= t]
        return float(sum(r.received for r in rs)), float(sum(r.sold for r in rs))
