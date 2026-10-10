"""Manager metrics (Wave 12): one use case per view, shared by the public routes (UI) and the internal ones (agent
tools) so chat and screens quote the same numbers. Every view reads data <= the case date only (clipped again here,
whatever the adapter returned); what lies after it is a projection and carries `projected: true`."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..domain import Case, DomainError
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
