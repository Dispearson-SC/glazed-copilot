"""Issue detectors: pure functions of a SkuState, so the same rules run on today's data and in backtest replays."""
from __future__ import annotations

from datetime import timedelta

from .inventory import SkuState, expiring_units
from .plan import plan_line
from .types import Config

MIN_DAILY_DEMAND = 1.0
MIN_WASTE_USD = 5.0
OVER_RECEIVING = 1.3
MIN_EXPIRING_UNITS = 3.0
MAX_EXPIRING_SHELF_LIFE = 7


def avg_daily_demand(state: SkuState, days: int = 28) -> float:
    xs = [v for d, v in state.censored.demand.items() if state.t - timedelta(days=days) < d <= state.t]
    return sum(xs) / len(xs) if xs else 0.0


def stockout_candidate(state: SkuState, cfg: Config) -> dict | None:
    """Plan line (with qty > 0) when the chance of running out before the next delivery is high enough."""
    if avg_daily_demand(state) < MIN_DAILY_DEMAND:
        return None
    line = plan_line(state, cfg, None, 0.0, 0.0)
    return line if line and line["stockout_risk_without_order"] >= cfg.stockout_risk_min else None


def overstock_candidate(state: SkuState, cfg: Config) -> dict | None:
    """Chronic over-receiving with real waste: >=$5 expired in 14 days and received > 1.3x sold over 28 days."""
    cost = state.product.unit_cost
    waste14 = sum(r.expired for r in state.rows if r.date > state.t - timedelta(days=14)) * cost
    last28 = [r for r in state.rows if r.date > state.t - timedelta(days=28)]
    rec28, sold28 = sum(r.received for r in last28), sum(r.sold for r in last28)
    if waste14 >= MIN_WASTE_USD and rec28 > OVER_RECEIVING * max(sold28, 1):
        return {"waste_usd_14d": waste14, "received_28d": rec28, "sold_28d": sold28}
    return None


def expiring_candidate(state: SkuState) -> dict | None:
    sl = state.product.shelf_life_days
    if sl is None or sl > MAX_EXPIRING_SHELF_LIFE:
        return None
    units = expiring_units(state)
    if units >= MIN_EXPIRING_UNITS:
        return {"units": units, "value_usd": units * state.product.unit_cost}
    return None
