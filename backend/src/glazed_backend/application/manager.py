"""Manager metrics (Wave 12): one use case per view, shared by the public routes (UI) and the internal ones (agent
tools) so chat and screens quote the same numbers. Every view reads data <= the case date only (clipped again here,
whatever the adapter returned); what lies after it is a projection and carries `projected: true`."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..domain import Case, DomainError, NotFound
from ..metrics.deliveries import LATE_LOOKBACK_DAYS, build_delivery_days
from ..metrics.expiry import MAX_SHELF_LIFE_DAYS, expiring_items, summarize_expiry
from ..metrics.staffing import WINDOW_DAYS, productivity_p50, recommended_hours
from ..metrics.promos_view import STATUSES, in_window, promo_status, sort_promos
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


class PromosView(_View):
    """Promotions with the audit verdict the rule would give (known when the promo started, or today for a promo that has
    not) and, only for promos that ended on or before the case date, the store's naive pre/post uplift."""
    SOURCE = "promotions+promo_audit+promo_evaluation"
    MAX_DAYS = 365

    def execute(self, case: Case, status: str | None = None, days: int | None = None, limit: int | None = None) -> dict[str, Any]:
        if status is not None and status not in STATUSES:
            raise DomainError(f"status must be one of {', '.join(STATUSES)}")
        days = 14 if days is None else days
        if not 1 <= days <= self.MAX_DAYS:
            raise DomainError(f"days must be between 1 and {self.MAX_DAYS}")
        as_of, store = case.sim_today, case.store_id
        items = []
        for p in self.metrics.promotions(store, as_of):
            st = promo_status(p["start_date"], p["end_date"], as_of)
            if (status and st != status) or not in_window(st, p["start_date"], p["end_date"], as_of, days):
                continue
            audit = self.metrics.promo_audit(store, min(p["start_date"], as_of), p["department"], float(p["discount_pct"] or 0))
            ev = None
            if p["end_date"] <= as_of:  # NO LOOK-AHEAD: a promo that has not finished has no result yet
                got = self.metrics.promo_evaluation(store, as_of, p["promo_id"])
                ev = {"uplift_pct": got.get("uplift_pct"), "expected_uplift_pct": got.get("expected_uplift_pct"),
                      "confidence": got.get("confidence"), "caveat": got.get("caveat")}
            items.append({"promo_id": p["promo_id"], "name": p["promo_name"], "department": p["department"],
                          "category": p.get("category"), "discount_pct": p["discount_pct"],
                          "start_date": p["start_date"].isoformat(), "end_date": p["end_date"].isoformat(), "status": st,
                          "audit_verdict": audit.get("verdict"), "evaluation": ev,
                          "projected": p["end_date"] > as_of})
        return self.envelope(case, window_days=days, items=sort_promos(items)[:clamp_limit(limit)])


class StaffingView(_View):
    """Recommended staff hours per future day = forecast transactions / the format's median transactions per staff hour.
    Daily basis: there is no hourly staffing. No roster exists in the data, and staff hours dated after the case date are
    never read, so planned hours are null."""
    SOURCE = "store_daily_kpis (format benchmark)+flow forecast"
    MAX_DAYS = 14
    NOTE = "sin datos por hora"

    def __init__(self, metrics: Any, names: Any, flow_forecaster: Any) -> None:
        super().__init__(metrics, names)
        self.flow_forecaster = flow_forecaster

    def execute(self, case: Case, days: int | None = None) -> dict[str, Any]:
        from .forecast import FlowForecast
        days = 7 if days is None else days
        if not 1 <= days <= self.MAX_DAYS:
            raise DomainError(f"days must be between 1 and {self.MAX_DAYS}")
        as_of = case.sim_today
        hist = self.metrics.staffing_history(case.store_id, as_of, as_of - timedelta(days=WINDOW_DAYS))
        p50, n = productivity_p50(hist["rows"], as_of)
        if p50 is None or p50 <= 0:
            raise NotFound(f"no staffing history to benchmark store {case.store_id} before {as_of}")
        flow = FlowForecast(self.metrics, self.flow_forecaster)
        out = []
        for i in range(1, days + 1):
            d = as_of + timedelta(days=i)
            tx = flow.execute(case, d)["transactions"]
            rng = {"low": tx["p10"], "mid": tx["p50"], "high": tx["p90"]}
            out.append({"date": d.isoformat(), "forecast_transactions": rng,
                        "recommended_staff_hours": recommended_hours(rng, p50), "planned_staff_hours": None, "gap_hours": None,
                        "basis": "daily", "projected": True})
        return self.envelope(case, benchmark={"format": hist["format"], "tx_per_staff_hour_p50": round(p50, 2),
                                              "n_store_days": n, "window_days": WINDOW_DAYS},
                             days=out, note=self.NOTE,
                             planned_hours_note="no roster in the data; staff hours dated after the case date are never read")


ZERO = {"low": 0.0, "mid": 0.0, "high": 0.0}


class OutlookView(_View):
    """Tomorrow onwards, day by day: net sales, transactions and average ticket as ranges, plus expected waste (lots
    that expire, from the expiring view) and expected lost sales (stock vs the SKU forecast quantiles, counting the
    open purchase orders). Every day is a projection. There is no weather feed: weather is null."""
    SOURCE = "forecast+inventory_daily+purchase_orders"
    MAX_DAYS = 7
    WEATHER_NOTE = "Sin pronóstico"

    def __init__(self, metrics: Any, names: Any, forecasters: list, flow_forecaster: Any) -> None:
        super().__init__(metrics, names)
        self.forecasters, self.flow_forecaster = forecasters, flow_forecaster

    def execute(self, case: Case, days: int | None = None) -> dict[str, Any]:
        from ..domain import Unprocessable  # noqa: F401
        from .forecast import FlowForecast, ForecastLoader, StoreMetricForecast
        days = 2 if days is None else days
        if not 1 <= days <= self.MAX_DAYS:
            raise DomainError(f"days must be between 1 and {self.MAX_DAYS}")
        as_of = case.sim_today
        dates = [as_of + timedelta(days=i) for i in range(1, days + 1)]
        sales = {}
        try:
            got = StoreMetricForecast(None, self.metrics, self.forecasters, self.flow_forecaster, self.names)
            sales = {p["date"]: p for p in got.execute_case(case, "net_sales", dates[0], dates[-1])["points"]}
        except NotFound:
            pass
        flow = FlowForecast(self.metrics, self.flow_forecaster)
        waste = {d["date"]: d["waste_usd"] for d in ExpiringView(self.metrics, self.names).execute(case, days)["by_day"]}
        lost = self._lost_sales(case, dates, ForecastLoader(self.metrics, self.forecasters))
        out = []
        for i, d in enumerate(dates):
            iso = d.isoformat()
            try:
                f = flow.execute(case, d)
            except NotFound:
                f = {"transactions": None, "avg_ticket": None}
            s = sales.get(iso)
            out.append({"date": iso, "projected": True,
                        "net_sales": {"low": s["p10"], "mid": s["forecast"], "high": s["p90"]} if s else None,
                        "transactions": _range(f["transactions"]), "avg_ticket": _range(f["avg_ticket"]),
                        "expected_waste_usd": waste.get(iso, dict(ZERO)),
                        "expected_lost_sales_usd": lost[i], "weather": None, "weather_note": self.WEATHER_NOTE})
        return self.envelope(case, days=out)

    def _lost_sales(self, case: Case, dates: list[date], loader: Any) -> list[dict[str, float]]:
        from ..metrics.stockflow import arrivals_by_sku, project_lost_sales
        as_of, store = case.sim_today, case.store_id
        total = [dict(ZERO) for _ in dates]
        try:
            loaded = loader.load(store, as_of, None, dates[0], dates[-1])
        except NotFound:
            return total
        got = self.metrics.delivery_inputs(store, as_of, as_of + timedelta(days=PROJECTION_HORIZON))
        arrivals = arrivals_by_sku([p for p in got["pos"] if p["order_date"] <= as_of], as_of)
        rows: dict[str, dict[date, Any]] = {}
        for r in loaded.result.rows:
            rows.setdefault(r.sku, {})[r.date] = r
        for s in loaded.history:
            known = [r for r in s.rows if r.date <= as_of]  # NO LOOK-AHEAD
            if not known or s.sku not in rows or not any(r.sold > 0 for r in known if r.date > as_of - timedelta(days=SELLING_DAYS)):
                continue  # inactive SKUs do not sell tomorrow either
            fc = rows[s.sku]
            if any(d not in fc for d in dates):
                continue
            demand = [(fc[d].quantile(0.1) or 0.0, fc[d].forecast, fc[d].quantile(0.9) or 0.0) for d in dates]
            arr = [arrivals.get(s.sku, {}).get(d, 0.0) for d in dates]
            for i, day in enumerate(project_lost_sales(float(max(known, key=lambda r: r.date).closing), s.price, demand, arr)):
                for k in ZERO:
                    total[i][k] += day[k]
        return [{k: round(v, 2) for k, v in t.items()} for t in total]


def _range(band: dict[str, float] | None) -> dict[str, float] | None:
    return None if not band else {"low": band["p10"], "mid": band["p50"], "high": band["p90"]}
