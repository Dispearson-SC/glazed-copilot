"""Plain inputs for the metrics package. Adapters build these from rows; nothing here does I/O."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class DayRow:
    """One closed day of one SKU in one store (inventory_daily)."""
    date: date
    received: int
    sold: int
    expired: int
    closing: int
    stockout_hours: float = 0.0


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    supplier_id: str
    price: float
    unit_cost: float
    case_size: int = 1
    shelf_life_days: int | None = None


@dataclass(frozen=True)
class PurchaseOrder:
    po_id: str
    sku: str
    order_date: date
    expected_date: date
    received_date: date | None
    qty_ordered: int
    qty_received: int | None = None


@dataclass(frozen=True)
class SupplierProfile:
    """Delivery behaviour of a supplier known at some date (see policy.supplier_profile)."""
    supplier_id: str
    delivery_days: frozenset[int]  # ISO weekdays on which the supplier delivers
    lead_mean: float
    lead_p90: float
    on_time_rate: float
    min_order_value: float = 0.0

    @property
    def p_late(self) -> float:
        return max(0.0, min(1.0, 1.0 - self.on_time_rate))


@dataclass(frozen=True)
class StoreInfo:
    open_hours: float = 12.0
    closed_dates: frozenset[date] = frozenset()


@dataclass(frozen=True)
class Config:
    """Tunable knobs. `store_threshold_usd` is the N1 cost ceiling for a store."""
    store_threshold_usd: float = 150.0
    non_perishable_service: float = 0.95
    history_days: int = 56
    horizon_days: int = 14
    stockout_risk_min: float = 0.30
    n1_min_score: float = 0.85
    n1_min_backtest: int = 30
    noise_floor_usd: float = 1.0
    backtest_days: int = 28
    markdown_discount: float = 0.30
    markdown_recovery: tuple[float, float, float] = (0.25, 0.50, 0.75)  # assumed elasticity (low, mid, high)
    extra: dict = field(default_factory=dict)
