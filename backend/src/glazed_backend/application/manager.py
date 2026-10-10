"""Manager metrics (Wave 12): one use case per view, shared by the public routes (UI) and the internal ones (agent
tools) so chat and screens quote the same numbers. Every view reads data <= the case date only (clipped again here,
whatever the adapter returned); what lies after it is a projection and carries `projected: true`."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..domain import Case, DomainError
from ..metrics.deliveries import LATE_LOOKBACK_DAYS, build_delivery_days
from ..metrics.expiry import MAX_SHELF_LIFE_DAYS, expiring_items, summarize_expiry
from ..metrics.inventory_view import SORTS, inventory_item, sort_items

DEFAULT_LIMIT, MAX_LIMIT = 50, 500
PROJECTION_HORIZON = 14
SELLING_DAYS = 28


def clamp_limit(limit: int | None, default: int = DEFAULT_LIMIT) -> int:
    return default if limit is None else max(1, min(int(limit), MAX_LIMIT))


class _View:
    SOURCE = ""

    def __init__(self, metrics: Any, names: Any) -> None:
        self.metrics, self.names = metrics, names

    def envelope(self, case: Case, **rest: Any) -> dict[str, Any]:
        return {"as_of": case.sim_today.isoformat(), "store_id": case.store_id,
                "store_display_name": self.names.of(case.store_id), "source": self.SOURCE, **rest}


class InventoryView(_View):
    SOURCE = "inventory_daily+sales_daily+products"

    def execute(self, case: Case, sort: str | None = None, limit: int | None = None) -> dict[str, Any]:
        sort = sort or "days_of_cover"
        if sort not in SORTS:
            raise DomainError(f"sort must be one of {', '.join(SORTS)}")
        as_of, store = case.sim_today, case.store_id
        profile, catalog = self.metrics.store_profile(store), self.metrics.product_catalog(store)
        history = self.metrics.demand_history(store, as_of, None, as_of - timedelta(days=56))
        items = []
        for s in history:
            it = inventory_item(s.sku, catalog.get(s.sku) or {"product_name": s.sku, "unit_cost": 0.0}, list(s.rows),
                                as_of, float(profile.get("open_hours") or 12.0))
            if it is not None:
                items.append(it)
        selling = self.metrics.selling_skus(store, as_of, as_of - timedelta(days=SELLING_DAYS - 1))
        shown = sort_items(items, sort)[:clamp_limit(limit)]
        for it in shown:  # the projection is only worth asking for a SKU that could run out within the horizon
            stock = None
            if it["days_of_cover"] is not None and it["days_of_cover"] <= PROJECTION_HORIZON:
                stock = self.metrics.inventory_projection(store, as_of, it["sku"], PROJECTION_HORIZON).get("projected_stockout_date")
            it["projected_stockout_date"], it["projected"] = stock, stock is not None
        return self.envelope(case, coverage={"skus_with_inventory": len(items), "skus_selling": len(selling)},
                             sort=sort, projection_horizon_days=PROJECTION_HORIZON, items=shown)


class ExpiringView(_View):
    SOURCE = "inventory_daily+products (lots inferred)"
    MAX_DAYS = 30

    def execute(self, case: Case, days: int | None = None, limit: int | None = None) -> dict[str, Any]:
        days = 7 if days is None else days
        if not 1 <= days <= self.MAX_DAYS:
            raise DomainError(f"days must be between 1 and {self.MAX_DAYS}")
        as_of, store = case.sim_today, case.store_id
        profile, catalog = self.metrics.store_profile(store), self.metrics.product_catalog(store)
        history = self.metrics.demand_history(store, as_of, None, as_of - timedelta(days=MAX_SHELF_LIFE_DAYS))
        items: list[dict[str, Any]] = []
        for s in history:
            product = catalog.get(s.sku)
            if product is not None:
                items += expiring_items(s.sku, product, [r for r in s.rows if r.date <= as_of], as_of, days,
                                        float(profile.get("open_hours") or 12.0))
        items.sort(key=lambda i: (-i["waste_usd"]["mid"], -i["waste_usd"]["high"], i["expiry_date"], i["sku"]))
        by_day, total = summarize_expiry(items)
        return self.envelope(case, days=days, total_items=len(items), items=items[:clamp_limit(limit)], by_day=by_day,
                             total_waste_usd=total)


def select_issues(metrics: Any, names: Any, served: dict, case: Case, limit: int = 5, kind: str | None = None,
                  category: str | None = None) -> list[dict[str, Any]]:
    """Default: operational issues only (integrity never crowds out alerts). `kind=` filters by kind;
    `category=integrity` returns integrity issues only; `category=all` returns both, ranked by severity_usd
    (operational) / exposure_usd (integrity). Every issue returned is registered as served for option lookup."""
    cap = max(1, min(limit, 20))
    pool = metrics.issues(case.store_id, case.sim_today, 10_000)
    if kind:
        pool = [i for i in pool if i.get("kind") == kind]
    if category == "all":
        pool = sorted(pool, key=lambda i: -float(i.get("exposure_usd") or 0) if i.get("category") == "integrity"
                      else -float(i.get("severity_usd") or 0))
    elif category:
        pool = [i for i in pool if i.get("category") == category]
    elif not kind:
        pool = [i for i in pool if i.get("category") != "integrity"]
    found = names.tag(pool[:cap], case.store_id)
    for issue in found:
        served[(case.case_id, issue["issue_id"])] = issue
    return found


def inventory_projection(metrics: Any, case: Case, sku: str, horizon: int = 7) -> dict[str, Any]:
    return metrics.inventory_projection(case.store_id, case.sim_today, sku, max(1, min(horizon, 30)))


def case_history(metrics: Any, checker: Any, case: Case, weeks: int | None = None) -> dict[str, Any]:
    """Weekly series (never a week starting after the case date) plus the decision log; `weeks` keeps the latest N."""
    if weeks is not None and not 1 <= weeks <= 52:
        raise DomainError("weeks must be between 1 and 52")
    out = metrics.history(case.store_id, case.sim_today)
    series = [w for w in out.get("weeks", []) if w["week_start"] <= case.sim_today.isoformat()]  # NO LOOK-AHEAD
    return {**out, "weeks": series[-weeks:] if weeks else series, "decision_log": checker.decision_log(case.case_id)}


class DeliveriesView(_View):
    SOURCE = "purchase_orders+suppliers.delivery_days"
    MAX_DAYS = 14

    def execute(self, case: Case, days: int | None = None) -> dict[str, Any]:
        days = 7 if days is None else days
        if not 1 <= days <= self.MAX_DAYS:
            raise DomainError(f"days must be between 1 and {self.MAX_DAYS}")
        as_of = case.sim_today
        got = self.metrics.delivery_inputs(case.store_id, as_of, as_of + timedelta(days=days))
        pos = [p for p in got["pos"] if p["order_date"] <= as_of]  # a PO placed after the case date is not known yet
        return self.envelope(case, window_days=days, late_lookback_days=LATE_LOOKBACK_DAYS,
                             days=build_delivery_days(pos, got["suppliers"], as_of, days))
