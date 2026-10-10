"""MetricsPort over the cleaned Glazed DuckDB (read-only).

simple_v0 methods: replaced later by glazed_metrics behind the same port. All reads enforce
date <= as_of, except backtest_day which reads next-day outcomes on purpose.
"""
from __future__ import annotations

import math
import threading
from datetime import date, timedelta
from typing import Any

import duckdb

from ...domain import FutureDate, NotFound

METHOD = "simple_v0"
_DOW = {"Daily": {1, 2, 3, 4, 5, 6, 7}, "Mon": {1}, "Tue": {2}, "Wed": {3}, "Thu": {4}, "Fri": {5},
        "Sat": {6}, "Sun": {7}}


def _delivery_days(spec: str | None) -> set[int]:
    days: set[int] = set()
    for part in (spec or "Daily").replace(",", "/").split("/"):
        days |= _DOW.get(part.strip()[:5].strip() if part.strip() == "Daily" else part.strip()[:3], set())
    return days or {1, 2, 3, 4, 5, 6, 7}


def _f(x: Any, nd: int = 2) -> float | None:
    return None if x is None else round(float(x), nd)


class DuckDBMetrics:
    def __init__(self, path: str) -> None:
        self._con = duckdb.connect(path, read_only=True)
        self._lock = threading.Lock()

    # -- helpers -----------------------------------------------------------------
    def _q(self, sql: str, params: list[Any] | None = None) -> list[tuple]:
        with self._lock:
            return self._con.execute(sql, params or []).fetchall()

    def _rows(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._con.execute(sql, params or [])
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    @staticmethod
    def _guard(as_of: date, d: date) -> None:
        if d > as_of:
            raise FutureDate(f"{d} is after as_of {as_of}")

    def _ref_date(self, store_id: str, as_of: date) -> date:
        r = self._q("SELECT max(date) FROM inventory_daily WHERE store_id=? AND date<=?", [store_id, as_of])
        return r[0][0] or as_of

    def _same_weekday_dates(self, d: date, n: int = 8, include_d: bool = False) -> list[date]:
        return [d - timedelta(days=7 * k) for k in range(0 if include_d else 1, n + 1)]

    def stores(self) -> list[dict[str, Any]]:
        return self._rows("SELECT s.store_id, s.store_name AS name, s.format, s.site_id, si.region"
                          " FROM stores s LEFT JOIN sites si ON si.site_id=s.site_id ORDER BY s.store_id")

    # -- KPIs --------------------------------------------------------------------
    def kpis(self, store_id: str, as_of: date, date_from: date, date_to: date) -> dict[str, Any]:
        self._guard(as_of, date_to)
        k = self._rows(
            "SELECT coalesce(sum(net_sales),0) net_sales, coalesce(sum(units_sold),0) units,"
            " coalesce(sum(transactions),0) tx, coalesce(sum(footfall),0) footfall,"
            " coalesce(sum(staff_hours),0) staff_hours, count(*) n_days,"
            " coalesce(sum(CASE WHEN conversion_valid THEN transactions END),0) vtx,"
            " coalesce(sum(CASE WHEN conversion_valid THEN footfall END),0) vff"
            " FROM store_daily_kpis WHERE store_id=? AND date BETWEEN ? AND ?",
            [store_id, date_from, date_to])[0]
        inv = self._q(
            "SELECT coalesce((SELECT sum(waste_cost) FROM v_inventory_waste WHERE store_id=? AND date BETWEEN ? AND ?),0),"
            " coalesce((SELECT sum(stockout_hours) FROM inventory_daily WHERE store_id=? AND date BETWEEN ? AND ?),0)",
            [store_id, date_from, date_to] * 2)[0]
        return {
            "store_id": store_id, "date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
            "as_of": as_of.isoformat(), "days_with_data": k["n_days"],
            "net_sales": _f(k["net_sales"]), "units": int(k["units"]), "transactions": int(k["tx"]),
            "footfall": int(k["footfall"]),
            "conversion": _f(k["vtx"] / k["vff"], 4) if k["vff"] else None,
            "tx_per_staff_hour": _f(k["tx"] / k["staff_hours"]) if k["staff_hours"] else None,
            "waste_usd": _f(inv[0]), "stockout_hours": _f(inv[1]),
        }

    # -- Day summary -------------------------------------------------------------
    def day_summary(self, store_id: str, as_of: date, day: date) -> dict[str, Any]:
        self._guard(as_of, day)
        totals = self._rows("SELECT footfall, transactions, units_sold, net_sales, staff_hours FROM store_daily_kpis"
                            " WHERE store_id=? AND date=?", [store_id, day])
        dept = self._rows("SELECT department, round(sum(net_sales),2) net_sales, sum(units_sold) units"
                          " FROM v_sales_enriched WHERE store_id=? AND date=? GROUP BY 1 ORDER BY 2 DESC",
                          [store_id, day])
        top = self._rows("SELECT sku, product_name, round(sum(net_sales),2) net_sales, sum(units_sold) units"
                         " FROM v_sales_enriched WHERE store_id=? AND date=? GROUP BY 1,2 ORDER BY 3 DESC LIMIT 5",
                         [store_id, day])
        cal = self._rows("SELECT day_of_week, is_weekend, is_holiday, holiday_name, is_school_break"
                         " FROM calendar WHERE date=?", [day])
        wx = self._rows("SELECT temp_max_c, temp_min_c, precip_mm FROM v_store_day_weather WHERE store_id=? AND date=?",
                        [store_id, day])
        prev = self._same_weekday_dates(day)
        base = self._q("SELECT avg(net_sales), count(*) FROM store_daily_kpis WHERE store_id=? AND list_contains(?, date)",
                       [store_id, prev])[0]
        net = totals[0]["net_sales"] if totals else None
        vs = None
        if net is not None and base[0]:
            vs = {"baseline_net_sales": _f(base[0]), "weeks_used": base[1],
                  "delta_pct": _f((net - base[0]) / base[0] * 100, 1)}
        c = cal[0] if cal else {}
        return {
            "store_id": store_id, "date": day.isoformat(), "as_of": as_of.isoformat(),
            "totals": {k: _f(v) for k, v in totals[0].items()} if totals else None,
            "by_department": dept, "top_skus": top,
            "context": {"weekday": c.get("day_of_week"), "is_weekend": c.get("is_weekend"),
                        "is_holiday": c.get("is_holiday"), "holiday_name": c.get("holiday_name"),
                        "is_school_break": c.get("is_school_break"), "weather": wx[0] if wx else None},
            "vs_same_weekday_avg": vs,
        }

    # -- Issues ------------------------------------------------------------------
    def issues(self, store_id: str, as_of: date, limit: int = 5) -> list[dict[str, Any]]:
        ref = self._ref_date(store_id, as_of)
        out: list[dict[str, Any]] = []
        w0 = ref - timedelta(days=27)
        stock = self._rows(
            "WITH dem AS (SELECT sku, sum(units_sold)/28.0 AS avg_d, sum(received_qty) rec28, sum(units_sold) sold28,"
            "  sum(CASE WHEN date>? THEN waste_cost ELSE 0 END) waste14"
            "  FROM v_inventory_waste WHERE store_id=? AND date BETWEEN ? AND ? GROUP BY sku),"
            " cur AS (SELECT sku, closing_qty FROM inventory_daily WHERE store_id=? AND date=?),"
            " transit AS (SELECT sku, sum(qty_ordered) qty, min(expected_date) eta FROM purchase_orders"
            "  WHERE store_id=? AND order_date<=? AND (received_date IS NULL OR received_date>?) GROUP BY sku)"
            " SELECT p.sku, p.product_name, p.supplier_id, p.unit_cost, p.list_price_base price, p.shelf_life_days,"
            "  coalesce(s.standard_lead_time_days,1) lead, d.avg_d, d.rec28, d.sold28, d.waste14, c.closing_qty,"
            "  coalesce(t.qty,0) transit_qty, t.eta"
            " FROM cur c JOIN dem d USING (sku) JOIN products p USING (sku) LEFT JOIN suppliers s USING (supplier_id)"
            " LEFT JOIN transit t USING (sku)",
            [ref - timedelta(days=14), store_id, w0, ref, store_id, ref, store_id, as_of, as_of])
        for r in stock:
            avg_d = r["avg_d"] or 0.0
            if avg_d >= 1.0:
                cover = (r["closing_qty"] or 0) / avg_d
                arrives_in_time = r["transit_qty"] > 0 and r["eta"] is not None and (r["eta"] - ref).days <= max(r["lead"], 1)
                if cover < r["lead"] and not arrives_in_time:
                    sev = (r["lead"] - cover) * avg_d * (r["price"] or 0)
                    out.append(self._issue(store_id, "stockout_risk", r["sku"], ref, sev, {
                        "sku": r["sku"], "product_name": r["product_name"], "supplier_id": r["supplier_id"],
                        "closing_qty": r["closing_qty"], "avg_daily_demand": _f(avg_d),
                        "days_of_cover": _f(cover), "lead_time_days": r["lead"]}))
            sold, rec, waste = r["sold28"] or 0, r["rec28"] or 0, r["waste14"] or 0
            if waste >= 5 and rec > 1.3 * max(sold, 1):
                out.append(self._issue(store_id, "overstock_waste", r["sku"], ref, waste, {
                    "sku": r["sku"], "product_name": r["product_name"], "waste_usd_14d": _f(waste),
                    "received_28d": rec, "sold_28d": sold}))
            elif (r["shelf_life_days"] or 99) <= 3 and avg_d > 0:
                surplus = (r["closing_qty"] or 0) - avg_d * r["shelf_life_days"]
                if surplus >= 5:
                    out.append(self._issue(store_id, "expiring", r["sku"], ref, surplus * (r["unit_cost"] or 0), {
                        "sku": r["sku"], "product_name": r["product_name"], "surplus_units": _f(surplus),
                        "shelf_life_days": r["shelf_life_days"]}))
        late = self._rows(
            "SELECT supplier_id, count(*) lines, sum(qty_ordered*unit_cost) val, max(ref_gap) max_days_late FROM ("
            " SELECT *, date_diff('day', expected_date, ?::DATE) ref_gap FROM purchase_orders"
            " WHERE store_id=? AND order_date<=? AND (received_date IS NULL OR received_date>?) AND expected_date<?)"
            " GROUP BY 1", [as_of, store_id, as_of, as_of, as_of])
        for r in late:
            out.append(self._issue(store_id, "late_delivery", r["supplier_id"], ref, r["val"] or 0, {
                "supplier_id": r["supplier_id"], "overdue_lines": r["lines"], "max_days_late": r["max_days_late"]}))
        out.sort(key=lambda i: (-i["severity_usd"], i["issue_id"]))
        return out[:limit]

    @staticmethod
    def _issue(store_id: str, kind: str, key: str, as_of: date, severity: float, evidence: dict[str, Any]) -> dict[str, Any]:
        issue = {"issue_id": f"{store_id}|{kind}|{key}", "store_id": store_id, "kind": kind,
                 "as_of_date": as_of.isoformat(), "severity_usd": _f(severity), "evidence": evidence,
                 "engine_version": METHOD}
        if kind != "late_delivery":
            issue["sku"] = key
        else:
            issue["supplier_id"] = key
        return issue

    # -- Inventory projection ----------------------------------------------------
    def _weekday_demand(self, store_id: str, sku: str, ref: date) -> tuple[dict[int, float], float]:
        """Mean units per ISO weekday over the last 8 same-weekday samples, plus overall mean."""
        rows = self._q("SELECT isodow(date), avg(units_sold) FROM inventory_daily"
                       " WHERE store_id=? AND sku=? AND date<=? AND date>?  GROUP BY 1",
                       [store_id, sku, ref, ref - timedelta(days=56)])
        by = {int(d): float(v) for d, v in rows}
        overall = sum(by.values()) / len(by) if by else 0.0
        return by, overall

    def inventory_projection(self, store_id: str, as_of: date, sku: str, horizon: int = 7) -> dict[str, Any]:
        ref = self._ref_date(store_id, as_of)
        cur = self._q("SELECT closing_qty FROM inventory_daily WHERE store_id=? AND sku=? AND date=?", [store_id, sku, ref])
        closing = float(cur[0][0]) if cur else 0.0
        pos = self._rows("SELECT po_id, expected_date, qty_ordered FROM purchase_orders WHERE store_id=? AND sku=?"
                         " AND order_date<=? AND (received_date IS NULL OR received_date>?) ORDER BY expected_date",
                         [store_id, sku, as_of, as_of])
        by, overall = self._weekday_demand(store_id, sku, ref)
        stock, stockout, daily = closing, None, []
        for i in range(1, horizon + 1):
            d = ref + timedelta(days=i)
            arrivals = sum(p["qty_ordered"] for p in pos if max(p["expected_date"], ref + timedelta(days=1)) == d)
            dem = by.get(d.isoweekday(), overall)
            stock = stock + arrivals - dem
            daily.append({"date": d.isoformat(), "arrivals": arrivals, "demand": _f(dem), "projected_qty": _f(stock)})
            if stock < 0 and stockout is None:
                stockout = d.isoformat()
        return {"store_id": store_id, "sku": sku, "as_of": as_of.isoformat(), "method": METHOD, "horizon": horizon,
                "closing_qty": closing, "in_transit": [{"po_id": p["po_id"], "expected_date": p["expected_date"].isoformat(),
                                                        "qty": p["qty_ordered"]} for p in pos],
                "days_of_cover": _f(closing / overall) if overall else None, "daily": daily,
                "projected_stockout_date": stockout}

    # -- Order plan --------------------------------------------------------------
    def order_plan(self, store_id: str, as_of: date) -> dict[str, Any]:
        ref = self._ref_date(store_id, as_of)
        rows = self._rows(
            "SELECT i.sku, p.product_name, p.supplier_id, p.case_size, p.unit_cost, s.delivery_days,"
            " i.closing_qty, coalesce(t.qty,0) transit"
            " FROM inventory_daily i JOIN products p USING (sku) LEFT JOIN suppliers s USING (supplier_id)"
            " LEFT JOIN (SELECT sku, sum(qty_ordered) qty FROM purchase_orders WHERE store_id=? AND order_date<=?"
            "   AND (received_date IS NULL OR received_date>?) GROUP BY sku) t USING (sku)"
            " WHERE i.store_id=? AND i.date=? AND p.status IS DISTINCT FROM 'Discontinued'",
            [store_id, as_of, as_of, store_id, ref])
        p74 = {(r[0], int(r[1])): float(r[2]) for r in self._q(
            "SELECT sku, isodow(date), quantile_cont(units_sold, 0.74) FROM inventory_daily"
            " WHERE store_id=? AND date<=? AND date>? GROUP BY 1,2", [store_id, ref, ref - timedelta(days=56)])}
        lines = []
        for r in rows:
            days = _delivery_days(r["delivery_days"])
            nxt = next((k for k in range(1, 8) if (ref + timedelta(days=k)).isoweekday() in days), 1)
            need = sum(p74.get((r["sku"], (ref + timedelta(days=k)).isoweekday()), 0.0) for k in range(1, nxt + 1))
            usable = (r["closing_qty"] or 0) + r["transit"]
            short = need - usable
            if short <= 0:
                continue
            cs = r["case_size"] or 1
            qty = int(math.ceil(short / cs) * cs)
            lines.append({"sku": r["sku"], "product_name": r["product_name"], "supplier_id": r["supplier_id"],
                          "qty_units": qty, "case_size": cs, "cases": qty // cs, "est_cost_usd": _f(qty * (r["unit_cost"] or 0)),
                          "days_to_next_delivery": nxt, "usable_stock": usable, "demand_p74": _f(need)})
        lines.sort(key=lambda l: -l["est_cost_usd"])
        return {"store_id": store_id, "as_of": as_of.isoformat(), "method": METHOD,
                "note": "Placeholder plan (p74 same-weekday demand x days to next delivery - usable stock). "
                        "glazed_metrics will replace it.", "lines": lines[:50], "total_lines": len(lines)}

    # -- Suppliers ---------------------------------------------------------------
    def supplier_performance(self, store_id: str, as_of: date) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT s.supplier_id, s.supplier_name, count(*) pos, avg(date_diff('day', po.order_date, po.received_date)) lt_mean,"
            " quantile_cont(date_diff('day', po.order_date, po.received_date), 0.9) lt_p90,"
            " 100.0*avg(CASE WHEN po.received_date<=po.expected_date THEN 1 ELSE 0 END) on_time,"
            " 100.0*sum(po.qty_received)/nullif(sum(po.qty_ordered),0) fill,"
            " s.standard_lead_time_days std_lt, 100*s.contract_on_time_rate c_ot, 100*s.contract_fill_rate c_fill"
            " FROM purchase_orders po JOIN suppliers s USING (supplier_id)"
            " WHERE po.store_id=? AND po.received_date IS NOT NULL AND po.received_date<=? AND po.order_date>?"
            " GROUP BY ALL ORDER BY pos DESC", [store_id, as_of, as_of - timedelta(days=180)])
        return [{"supplier_id": r["supplier_id"], "supplier_name": r["supplier_name"], "received_pos": r["pos"],
                 "lead_time_mean_days": _f(r["lt_mean"]), "lead_time_p90_days": _f(r["lt_p90"]),
                 "on_time_pct": _f(r["on_time"], 1), "fill_pct": _f(r["fill"], 1),
                 "contract_lead_time_days": r["std_lt"], "contract_on_time_pct": _f(r["c_ot"], 1),
                 "contract_fill_pct": _f(r["c_fill"], 1), "window_days": 180} for r in rows]

    # -- Promos ------------------------------------------------------------------
    def promo_evaluation(self, store_id: str, as_of: date, promo_id: str) -> dict[str, Any]:
        pr = self._rows("SELECT * FROM promotions WHERE promo_id=?", [promo_id])
        if not pr:
            raise NotFound(f"promo {promo_id!r} not found")
        pr = pr[0]
        base = {"promo_id": promo_id, "promo_name": pr["promo_name"], "as_of": as_of.isoformat(),
                "start_date": pr["start_date"].isoformat(), "end_date": pr["end_date"].isoformat(),
                "expected_uplift_pct": pr["expected_uplift_pct"], "confidence": "low", "method": METHOD}
        if pr["start_date"] > as_of:
            return {**base, "status": "not_started", "uplift_pct": None}
        end = min(pr["end_date"], as_of)
        scope, sp = "department=? AND (?::VARCHAR IS NULL OR category=?)", [pr["department"], pr["category"], pr["category"]]
        def avg_daily(where: str, params: list[Any]) -> tuple[float | None, int]:
            r = self._q(f"SELECT sum(net_sales), count(DISTINCT date) FROM v_sales_enriched WHERE store_id=? AND {scope} AND {where}",
                        [store_id, *sp, *params])[0]
            return (r[0] / r[1], r[1]) if r[1] else (None, 0)
        promo_avg, promo_days = avg_daily("date BETWEEN ? AND ?", [pr["start_date"], end])
        pre = avg_daily("date BETWEEN ? AND ?", [pr["start_date"] - timedelta(days=28), pr["start_date"] - timedelta(days=1)])
        post_end = min(pr["end_date"] + timedelta(days=28), as_of)
        post = avg_daily("date BETWEEN ? AND ?", [pr["end_date"] + timedelta(days=1), post_end]) if post_end > pr["end_date"] else (None, 0)
        pools = [x for x in (pre, post) if x[0] is not None]
        baseline = sum(x[0] * x[1] for x in pools) / sum(x[1] for x in pools) if pools else None
        uplift = _f((promo_avg - baseline) / baseline * 100, 1) if promo_avg is not None and baseline else None
        return {**base, "status": "running" if pr["end_date"] > as_of else "finished", "scope": {
                "department": pr["department"], "category": pr["category"]}, "promo_days": promo_days,
                "promo_avg_daily_sales": _f(promo_avg), "baseline_avg_daily_sales": _f(baseline),
                "baseline_days": sum(x[1] for x in pools), "uplift_pct": uplift,
                "caveat": "Naive pre/post comparison, no seasonality control."}

    # -- History -----------------------------------------------------------------
    def history(self, store_id: str, as_of: date) -> dict[str, Any]:
        start = as_of - timedelta(days=84)
        rows = self._rows(
            "SELECT strftime(date_trunc('week', k.date), '%Y-%m-%d') week_start, round(sum(k.net_sales),2) net_sales,"
            " sum(k.units_sold) units, sum(k.transactions) transactions FROM store_daily_kpis k"
            " WHERE k.store_id=? AND k.date BETWEEN ? AND ? GROUP BY 1 ORDER BY 1", [store_id, start, as_of])
        waste = {r[0]: r[1] for r in self._q(
            "SELECT strftime(date_trunc('week', date), '%Y-%m-%d'), round(sum(waste_cost),2) FROM v_inventory_waste"
            " WHERE store_id=? AND date BETWEEN ? AND ? GROUP BY 1", [store_id, start, as_of])}
        for r in rows:
            r["waste_usd"] = waste.get(r["week_start"], 0.0)
        return {"store_id": store_id, "as_of": as_of.isoformat(), "weeks": rows}

    # -- Backtest ----------------------------------------------------------------
    def backtest_day(self, store_id: str, day: date, policy: str) -> dict[str, Any]:
        """Decide with data <= day; measure on day+1. simple_v0 counterfactual: receive ceil(p74 demand)."""
        d1 = day + timedelta(days=1)
        samples = self._same_weekday_dates(d1)
        oh = self._q("SELECT coalesce(typical_open_hours, 12) FROM stores WHERE store_id=?", [store_id])
        open_h = float(oh[0][0]) if oh and oh[0][0] else 12.0
        rows = self._rows(
            "SELECT i.received_qty, i.expired_qty, i.stockout_hours, p.unit_cost, p.list_price_base price,"
            " (SELECT quantile_cont(h.units_sold, 0.74) FROM inventory_daily h WHERE h.store_id=i.store_id AND h.sku=i.sku"
            "   AND list_contains(?, h.date)) tgt"
            " FROM inventory_daily i JOIN products p USING (sku) WHERE i.store_id=? AND i.date=?", [samples, store_id, d1])
        cw = pw = cl = pl = 0.0
        for r in rows:
            target = math.ceil(r["tgt"] or 0)
            cost, price = r["unit_cost"] or 0, r["price"] or 0
            expired, rec = r["expired_qty"] or 0, r["received_qty"] or 0
            w_cur = expired * cost
            excess = max(0, rec - target)
            w_pol = max(0, expired - excess) * cost
            lost_units = (r["tgt"] or 0) * min(r["stockout_hours"] or 0, open_h) / open_h
            l_cur = lost_units * price
            recovered = min(lost_units, max(0, target - rec))
            l_pol = (lost_units - recovered) * price
            cw, pw, cl, pl = cw + w_cur, pw + w_pol, cl + l_cur, pl + l_pol
        return {"date": day.isoformat(), "outcome_date": d1.isoformat(), "method": METHOD,
                "current": {"waste_usd": round(cw, 2), "lost_sales_usd": round(cl, 2)},
                "policy": {"waste_usd": round(pw, 2), "lost_sales_usd": round(pl, 2)}}
