"""One-SKU, one-day backtest of the reorder policy against what actually happened."""
from __future__ import annotations

from .demand import uncensor, weekday_stats
from .inventory import is_short_life
from .policy import normal_quantile
from .service_level import service_target
from .types import Config, DayRow, Product


def _arm(waste: float, lost: float) -> dict:
    return {"waste_usd": round(waste, 4), "lost_sales_usd": round(lost, 4)}


def backtest_sku(history: list[DayRow], outcome: DayRow, prod: Product, open_hours: float,
                 cfg: Config | None = None) -> dict:
    """Compare current practice with the policy on `outcome.date`.

    history holds only days <= the decision day (the caller cuts it lead-time days before the outcome day); the
    outcome row is read only to score. Policy supply = the service-level quantile of that day's demand
    (CR for perishables, >= 95% for non-perishables); current supply = what the day actually had
    (sold + expired + closing). Extra units can only sell what was actually unmet; unsold extras are waste for
    perishables and kept stock otherwise. Lost sales use the same hourly rate as the KPI."""
    cfg = cfg or Config()
    cost, price = prod.unit_cost, prod.price
    perishable = is_short_life(prod.shelf_life_days)
    cur_w = outcome.expired * cost
    frac = min(outcome.stockout_hours, open_hours) / open_hours if open_hours > 0 else 0.0
    dem = uncensor(history, open_hours).demand
    ref = max((r.date for r in history), default=None)
    if ref is None:
        return {"current": _arm(cur_w, 0.0), "policy": _arm(cur_w, 0.0)}
    mean, sd = weekday_stats(dem, ref, outcome.date.isoweekday())
    clean = [float(r.sold) for r in history if r.stockout_hours <= 0 and r.date.isoweekday() == outcome.date.isoweekday()]
    rate = sum(clean) / len(clean) if clean else mean
    lost_units = rate * frac
    cur_l = lost_units * price
    service = service_target(price, cost, perishable, cfg)
    target = normal_quantile(mean, sd, service)
    available = float(outcome.sold + outcome.expired + outcome.closing)
    if target >= available:
        extra = target - available
        sold_extra = min(extra, lost_units)
        pol_w = cur_w + ((extra - sold_extra) * cost if perishable else 0.0)
        pol_l = (lost_units - sold_extra) * price
    else:
        cut = available - target
        avoided = min(cut, float(outcome.expired)) if perishable else 0.0
        short = max(0.0, cut - outcome.expired - outcome.closing)  # cut units that would have sold
        pol_w = (outcome.expired - avoided) * cost
        pol_l = cur_l + short * price
    return {"current": _arm(cur_w, cur_l), "policy": _arm(pol_w, pol_l)}
