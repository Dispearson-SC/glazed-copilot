"""MetricsPort over the cleaned Glazed DuckDB (read-only).

simple_v0 methods: replaced later by glazed_metrics behind the same port. All reads enforce
date <= as_of, except backtest_day which reads next-day outcomes on purpose.
"""
from __future__ import annotations

import copy
import dataclasses
import math
import os
import threading
from datetime import date, timedelta
from typing import Any

import duckdb

from ...domain import FutureDate, NotFound
from ...metrics.backtest import backtest_sku
from ...metrics.integrity import integrity_issues, scan_sales
from ...metrics.issues import detect_issues, finalize_options, merge_same_action
from ...metrics.replay import calibrate
from ...metrics.losses import lost_sales_window
from ...metrics.confidence import line_confidence, realized_add_net, realized_reduce_net
from ...metrics.demand import uncensor
from ...metrics.forecast import same_weekday_dates
from ...metrics.inventory import is_short_life
from ...metrics.sentinel import HORIZON_DAYS
from ...metrics.calendar_effect import calendar_issue, event_effect
from ...metrics.plan import apply_min_order, plan_line
from ...metrics.promo_audit import BASELINE, PromoRef, audit_promo, promo_issue
from ...metrics.promo_lift import PromoLiftTable, PromoObs, did_uplift_pct
from ...metrics.deliveries import LATE_LOOKBACK_DAYS
from ...metrics.schedule import next_delivery_after, parse_delivery_days
from ...metrics import transfers as xfer
from ...metrics.snapshot import StoreSnapshot
from ...metrics.types import Config, DayRow, Product, PurchaseOrder, SkuSeries, StoreInfo

METHOD = "simple_v0"
METRICS_METHOD = "glazed_metrics_v1"
SNAPSHOT_DAYS = 120
_DOW = {"Daily": {1, 2, 3, 4, 5, 6, 7}, "Mon": {1}, "Tue": {2}, "Wed": {3}, "Thu": {4}, "Fri": {5},
        "Sat": {6}, "Sun": {7}}


def _delivery_days(spec: str | None) -> set[int]:
    days: set[int] = set()
    for part in (spec or "Daily").replace(",", "/").split("/"):
        days |= _DOW.get(part.strip()[:5].strip() if part.strip() == "Daily" else part.strip()[:3], set())
    return days or {1, 2, 3, 4, 5, 6, 7}


def _issue_dict(store_id: str, iid: str, as_of: date, ref: date, severity: float, evidence: list, options: list, rec: str,
                sku: str, name: str, supplier_id: str | None) -> dict[str, Any]:
    from ...metrics.issues import _issue
    return _issue(store_id, "transfer_opportunity", sku, as_of, ref, severity, evidence,
                  ["Transfer cost and lead time are assumptions; confidence is uncalibrated (no transfer backtest)."], options, rec,
                  sku=sku, product_name=name, supplier_id=supplier_id)


def _f(x: Any, nd: int = 2) -> float | None:
    return None if x is None else round(float(x), nd)


class DuckDBMetrics:
    def __init__(self, path: str, raw_dir: str | None = None, config: Config | None = None) -> None:
        self._con = duckdb.connect(path, read_only=True)
        self._raw_dir = raw_dir if raw_dir and os.path.exists(os.path.join(raw_dir, "sales_daily.csv")) else None
        self._raw_rows: list[tuple] | None = None
        self._raw_master: dict[str, str] = {}
        self._lock = threading.Lock()
        self._snaps: dict[tuple[str, date], StoreSnapshot] = {}
        self._calib: dict[tuple[str, date], Any] = {}
        self._issues: dict[tuple[str, date], list[dict[str, Any]]] = {}
        self._xfers: dict[tuple[str, date], dict[str, Any]] = {}
        self._fmt_days: dict[str, list[dict[str, Any]]] = {}
        self.config = config or Config()
        self._lift_obs: dict[tuple[str, date], PromoObs] = {}
        self._lift_tables: dict[date, PromoLiftTable] = {}

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
        return same_weekday_dates(d, n, include_d)  # shared with the forecast baseline

    def stores(self) -> list[dict[str, Any]]:
        return self._rows("SELECT s.store_id, s.store_name AS name, s.format, s.site_id, si.region,"
                          " si.site_name, si.site_type,"
                          " coalesce(si.site_name || ' · ', '') || s.store_name AS display_name,"
                          " strftime(s.opened_date, '%Y-%m-%d') AS opened_on, strftime(s.closed_date, '%Y-%m-%d') AS closed_on,"
                          " s.opening_time, s.closing_time"
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
            "lost_sales_usd": self._lost_sales(store_id, date_from, date_to),
            "window": {"from": date_from.isoformat(), "to": date_to.isoformat()},
        }

    def _lost_sales(self, store_id: str, date_from: date, date_to: date) -> dict[str, float]:
        """stockout_hours x same-weekday sales rate per open hour x price (low = partial-day stockouts only)."""
        oh = self._q("SELECT coalesce(typical_open_hours, 12) FROM stores WHERE store_id=?", [store_id])
        open_h = float(oh[0][0]) if oh and oh[0][0] else 12.0
        rows = self._rows(
            "SELECT i.sku, i.date, i.received_qty, i.units_sold, i.expired_qty, i.closing_qty, i.stockout_hours,"
            " p.list_price_base price FROM inventory_daily i JOIN products p USING (sku)"
            " WHERE i.store_id=? AND i.date BETWEEN ? AND ? ORDER BY i.sku, i.date",
            [store_id, date_from - timedelta(days=56), date_to])
        by: dict[str, tuple[float, list[DayRow]]] = {}
        for r in rows:
            by.setdefault(r["sku"], (float(r["price"] or 0), []))[1].append(DayRow(
                r["date"], int(r["received_qty"] or 0), int(r["units_sold"] or 0), int(r["expired_qty"] or 0),
                int(r["closing_qty"] or 0), float(r["stockout_hours"] or 0.0)))
        tot = {"low": 0.0, "mid": 0.0, "high": 0.0}
        for price, rs in by.values():
            for k, v in lost_sales_window(rs, price, open_h, date_from, date_to).items():
                tot[k] += v
        return {k: round(v, 2) for k, v in tot.items()}

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
    def _cfg(self, as_of: date) -> Config:
        """The configured policy; waste_aware also carries the promo lift known at as_of (history only)."""
        if not self.config.waste_aware:
            return self.config
        return dataclasses.replace(self.config, promo_lift=self.promo_lift_table(as_of))

    def promo_lift_table(self, as_of: date) -> PromoLiftTable:
        """Lift of every finished promotion measured with data <= as_of. Cached per week: the post-promo baseline
        window only grows with as_of, so a Monday cut loses at most six days of it and never looks ahead."""
        monday = as_of - timedelta(days=as_of.weekday())
        if monday not in self._lift_tables:
            promos = self._rows("SELECT promo_id, department, category, discount_pct, start_date, end_date FROM promotions"
                                " ORDER BY promo_id")
            obs = []
            for pr in promos:
                if pr["end_date"] > as_of or pr["promo_id"] not in BASELINE:
                    continue
                obs.append(self._promo_obs(pr, promos, min(pr["end_date"] + timedelta(days=28), max(monday, pr["end_date"]))))
            self._lift_tables[monday] = PromoLiftTable(obs, as_of)
            if len(self._lift_tables) > 8:
                self._lift_tables.pop(next(iter(self._lift_tables)))
        return self._lift_tables[monday]

    def _promo_obs(self, pr: dict[str, Any], promos: list[dict[str, Any]], post_end: date) -> PromoObs:
        key = (pr["promo_id"], post_end)
        if key in self._lift_obs:
            return self._lift_obs[key]
        start, end, dep, cat = pr["start_date"], pr["end_date"], pr["department"], pr["category"]
        scope = "p.department=? AND (?::VARCHAR IS NULL OR p.category=?)"
        sp = [dep, cat, cat]
        rows = self._q(
            f"SELECT s.date, sum(CASE WHEN {scope} THEN s.units_sold ELSE 0 END),"
            f" sum(CASE WHEN NOT ({scope}) AND s.promo_id IS NULL THEN s.units_sold ELSE 0 END)"
            " FROM sales_daily s JOIN products p USING (sku)"
            " WHERE s.date BETWEEN ? AND ? AND NOT coalesce(s.is_return, false) AND (s.promo_id IS NULL OR s.promo_id=?)"
            " GROUP BY 1", [*sp, *sp, start - timedelta(days=28), post_end, pr["promo_id"]])
        others = [o for o in promos if o["promo_id"] != pr["promo_id"] and o["department"] == dep
                  and (o["category"] is None or cat is None or o["category"] == cat)]
        w = [0.0, 0.0, 0.0, 0.0]
        n_win = n_base = 0
        for d, sc, ct in rows:
            if start <= d <= end:
                w[0] += sc; w[1] += ct; n_win += 1
            elif not any(o["start_date"] <= d <= o["end_date"] for o in others):  # baseline day free of other promos
                w[2] += sc; w[3] += ct; n_base += 1
        placebo = BASELINE[pr["promo_id"]][2] == "placebo"
        ob = PromoObs(pr["promo_id"], dep, cat, float(pr["discount_pct"] or 0), start, end,
                      did_uplift_pct(*w) if n_win and n_base else None, n_win, n_base, placebo)
        self._lift_obs[key] = ob
        return ob

    def _calibration(self, store_id: str, as_of: date):
        key = (store_id, as_of)
        if key not in self._calib:
            ref = self._ref_date(store_id, as_of)
            self._calib[key] = calibrate(self._snapshot(store_id, as_of), ref, self._cfg(as_of))
            if len(self._calib) > 16:
                self._calib.pop(next(iter(self._calib)))
        return self._calib[key]

    def _all_issues(self, store_id: str, as_of: date) -> list[dict[str, Any]]:
        key = (store_id, as_of)
        if key not in self._issues:
            ref = self._ref_date(store_id, as_of)
            self._issues[key] = detect_issues(self._snapshot(store_id, as_of), store_id, as_of, ref, self._cfg(as_of),
                                              self._calibration(store_id, as_of), limit=10_000)
            self._issues[key] += self._transfer_issues(store_id, as_of, ref) + self._promo_issues(store_id, as_of, ref) + self._calendar_issues(store_id, as_of, ref) \
                + self._integrity_issues(store_id, as_of, ref)
            self._issues[key] = merge_same_action(self._issues[key])
            self._issues[key].sort(key=lambda i: (-i["severity_usd"], i["issue_id"]))
            name = next((x.get("display_name") or x["name"] for x in self.stores() if x["store_id"] == store_id), store_id)
            for iss in self._issues[key]:
                iss["store_display_name"] = name
            if len(self._issues) > 16:
                self._issues.pop(next(iter(self._issues)))
        return self._issues[key]

    def _promo_refs(self) -> list[PromoRef]:
        if not hasattr(self, "_refs"):
            self._refs = [PromoRef(r["promo_id"], r["promo_name"], r["department"], r["category"], float(r["discount_pct"] or 0),
                                   r["start_date"], r["end_date"], BASELINE[r["promo_id"]][0], BASELINE[r["promo_id"]][1],
                                   BASELINE[r["promo_id"]][2], BASELINE[r["promo_id"]][2] == "placebo")
                          for r in self._rows("SELECT * FROM promotions ORDER BY promo_id") if r["promo_id"] in BASELINE]
        return self._refs

    def promo_audit(self, store_id: str, as_of: date, department: str, discount_pct: float) -> dict[str, Any]:
        out = audit_promo(self._promo_refs(), department, float(discount_pct), as_of)
        for s in out["similar"]:  # this store's own naive pre/post reading, next to the chain-wide one
            ev = self.promo_evaluation(store_id, as_of, s["promo_id"])
            s["store_evaluation"] = {"uplift_pct": ev.get("uplift_pct"), "caveat": ev.get("caveat"), "status": ev.get("status")}
        return out

    def _promo_issues(self, store_id: str, as_of: date, ref: date) -> list[dict[str, Any]]:
        """Promotions running or starting within 7 days are treated as proposed templates and audited."""
        region = (self._q("SELECT si.region FROM stores s LEFT JOIN sites si ON si.site_id=s.site_id WHERE s.store_id=?",
                          [store_id]) or [[None]])[0][0]
        n_stores = len(self.stores())
        out = []
        for r in self._promo_refs():
            if r.placebo or r.end < as_of or r.start > as_of + timedelta(days=7):
                continue
            scope = self._q("SELECT region_scope FROM promotions WHERE promo_id=?", [r.promo_id])[0][0]
            if scope and scope.upper() != "ALL" and scope != region:
                continue
            audit = audit_promo(self._promo_refs(), r.department, r.discount_pct, as_of)
            if audit["verdict"] == "block":
                out.append(promo_issue(store_id, as_of, ref, {"promo_id": r.promo_id, "name": r.name, "department": r.department,
                                                              "discount_pct": r.discount_pct, "start": r.start.isoformat()},
                                       audit, n_stores, self.config))
        return out

    def _raw_unmatched(self) -> list[tuple]:
        """(store, raw sku, date, net_sales) for raw sales whose SKU is not in the raw master, read once."""
        if self._raw_rows is None:
            raw = duckdb.connect()
            sales, prods = os.path.join(self._raw_dir, "sales_daily.csv"), os.path.join(self._raw_dir, "products.csv")
            self._raw_master = {r[0]: r[1] for r in raw.execute(
                f"SELECT sku, product_name FROM read_csv_auto('{prods}', all_varchar=true)").fetchall()}
            self._raw_rows = raw.execute(
                f"SELECT store_id, sku, try_cast(date AS DATE), coalesce(try_cast(net_sales AS DOUBLE), 0)"
                f" FROM read_csv_auto('{sales}', all_varchar=true) WHERE sku NOT IN"
                f" (SELECT sku FROM read_csv_auto('{prods}', all_varchar=true))").fetchall()
            raw.close()
        return self._raw_rows

    def _integrity_issues(self, store_id: str, as_of: date, ref: date) -> list[dict[str, Any]]:
        """Alert 9 from the raw layer when mounted (dollars, cut at as_of); otherwise only the dq_log orphan count."""
        if self._raw_dir is None:
            dq = self._q("SELECT affected_rows FROM dq_log WHERE rule_id='SD03'")
            if not dq or not dq[0][0]:
                return []
            out = integrity_issues(store_id, as_of, ref, [], [{"sku": "SKU-7xxxxx", "rows": int(dq[0][0]), "net_sales": 0.0,
                                                               "days": 0, "by_store": {}}], self.config)
            for i in out:
                i["data_caveats"].append("Dollar amounts and the SKU key mismatch need the raw layer (not mounted); "
                                         "only the dq_log row count (rule SD03) is available.")
            return out
        per: dict[tuple[str, str], list[Any]] = {}
        for st, sku, d, net in self._raw_unmatched():
            if d is not None and d <= as_of:
                a = per.setdefault((st, sku), [0, 0.0, set()])
                a[0] += 1
                a[1] += net
                a[2].add(d)
        mism, orphans = scan_sales([(st, sku, n, round(v, 2), len(days)) for (st, sku), (n, v, days) in per.items()],
                                   self._raw_master)
        return integrity_issues(store_id, as_of, ref, mism, orphans, self.config)

    def _format_days(self, store_id: str) -> tuple[list[dict[str, Any]], str]:
        """Daily units, sales and cost per store x department for every store of this store's format (all dates;
        callers cut at as_of). Cached per format."""
        fmt = self._q("SELECT format FROM stores WHERE store_id=?", [store_id])[0][0]
        if fmt not in self._fmt_days:
            self._fmt_days[fmt] = self._rows(
                "SELECT v.store_id, v.date, v.department, any_value(v.is_school_break) sb, any_value(v.is_holiday) hol,"
                " sum(v.units_sold) units, sum(v.net_sales) sales, sum(v.units_sold*p.unit_cost) cost_total"
                " FROM v_sales_enriched v JOIN products p USING (sku) WHERE v.store_id IN"
                " (SELECT store_id FROM stores WHERE format=?) GROUP BY 1,2,3", [fmt])
        return self._fmt_days[fmt], fmt

    def _calendar_issues(self, store_id: str, as_of: date, ref: date) -> list[dict[str, Any]]:
        ahead = self._rows("SELECT date, is_school_break sb, is_holiday hol, holiday_name FROM calendar"
                           " WHERE date>? AND date<=? ORDER BY date", [as_of, as_of + timedelta(days=7)])
        events = []
        for typ, name, pick in (("school_break", "School break", lambda r: r["sb"]),
                                ("holiday", "Holiday", lambda r: r["hol"])):
            days = [r for r in ahead if pick(r)]
            if days:
                label = name if typ == "school_break" else ", ".join(sorted({r["holiday_name"] or "holiday" for r in days}))
                events.append({"type": typ, "name": label, "days": [r["date"] for r in days]})
        if not events:
            return []
        rows, _ = self._format_days(store_id)
        rows = [r for r in rows if r["date"] <= as_of]
        recent = {r[0]: (r[1], r[2]) for r in self._q(
            "SELECT date, is_school_break, is_holiday FROM calendar WHERE date>? AND date<=?",
            [as_of - timedelta(days=14), as_of])}
        out = []
        for ev in events:
            idx = 0 if ev["type"] == "school_break" else 1
            if sum(1 for v in recent.values() if v[idx]) >= 7:
                continue  # the last 56 days of history already carry the effect: the plan reflects it
            flag = (lambda r: r["sb"] and not r["hol"]) if ev["type"] == "school_break" else (lambda r: r["hol"])
            ordinary = lambda r: not r["sb"] and not r["hol"]  # noqa: E731
            deps: list[dict[str, Any]] = []
            for dep in sorted({r["department"] for r in rows if r["store_id"] == store_id}):
                mine = [r for r in rows if r["department"] == dep and r["store_id"] == store_id]
                grp = [r for r in rows if r["department"] == dep]
                eff = event_effect([r["units"] for r in mine if flag(r)], [r["units"] for r in mine if ordinary(r)],
                                   [r["units"] for r in grp if flag(r)], [r["units"] for r in grp if ordinary(r)])
                recent28 = [r for r in mine if as_of - timedelta(days=28) < r["date"] <= as_of]
                units = sum(r["units"] for r in recent28)
                if eff is None or units <= 0:
                    continue
                deps.append({"department": dep, "effect": eff, "units_per_day": units / 28.0,
                             "avg_price": sum(r["sales"] for r in recent28) / units,
                             "avg_cost": sum(r["cost_total"] for r in recent28) / units})
            iss = calendar_issue(store_id, as_of, ref, ev, deps, self.config)
            if iss:
                out.append(iss)
        return out

    # -- Transfers ---------------------------------------------------------------
    def _transfer_stores(self, store_id: str, as_of: date) -> list[dict[str, Any]]:
        """Other stores of the same region that are open on as_of (opened, not closed, no closure in the calendar)."""
        return self._rows(
            "SELECT s.store_id, s.site_id, coalesce(si.site_name || ' · ', '') || s.store_name AS display_name"
            " FROM stores s LEFT JOIN sites si ON si.site_id=s.site_id"
            " WHERE s.store_id<>? AND si.region=(SELECT si2.region FROM stores s2 LEFT JOIN sites si2 ON si2.site_id=s2.site_id"
            " WHERE s2.store_id=?) AND s.opened_date<=? AND (s.closed_date IS NULL OR s.closed_date>?)"
            " AND NOT EXISTS (SELECT 1 FROM store_calendar c WHERE c.store_id=s.store_id AND c.date=? AND c.status<>'open')"
            " ORDER BY s.store_id", [store_id, store_id, as_of, as_of, as_of])

    def _transfer_data(self, store_id: str, as_of: date) -> dict[str, Any]:
        key = (store_id, as_of)
        if key in self._xfers:
            return self._xfers[key]
        snap, ref = self._snapshot(store_id, as_of), self._ref_date(store_id, as_of)
        me = next((x for x in self.stores() if x["store_id"] == store_id), {})
        name = me.get("display_name") or store_id
        senders = {}
        for sku in snap.products:
            st = snap.state_at(sku, ref)
            if st is not None and st.product.shelf_life_days is not None:
                senders[sku] = st
        others = []
        if any(xfer.sender_surplus(st, 1) for st in senders.values()):  # region snapshots only when something is left over
            for o in self._transfer_stores(store_id, as_of):
                osnap = self._snapshot(o["store_id"], as_of)
                if self._ref_date(o["store_id"], as_of) == ref:
                    others.append((o, osnap))
        receivers: dict[str, list[xfer.Receiver]] = {}
        for sku in senders:
            for o, osnap in others:
                st = osnap.state_at(sku, ref)
                if st is not None and sum(r.sold for r in st.rows if r.date > ref - timedelta(days=28)) > 0:
                    receivers.setdefault(sku, []).append(xfer.Receiver(
                        o["store_id"], o["display_name"] or o["store_id"], o["site_id"] == me.get("site_id"), st))
        out = xfer.compute(senders, store_id, name, receivers, as_of)
        out["region_candidates"] = len(others)
        if len(self._xfers) >= 16:
            self._xfers.pop(next(iter(self._xfers)))
        self._xfers[key] = out
        return out

    def transfer_options(self, store_id: str, as_of: date, sku: str | None = None, limit: int = 5) -> dict[str, Any]:
        """Surplus here (unsold before expiry) against the region's forecast deficits, with the transfer cost assumption."""
        data = self._transfer_data(store_id, as_of)
        opts = [o for o in data["options"] if sku in (None, o["sku"])]
        if sku is not None:
            waste = data["waste"].get(sku)
        else:
            skus = {o["sku"] for o in opts} or set(data["waste"])  # none offered: what the store stands to lose anyway
            waste = None
            for s in skus:
                w = data["waste"].get(s)
                waste = w if waste is None else {k: round(waste[k] + w[k], 2) for k in waste}
        reason = None
        if not opts:
            if sku is not None:
                reason = data["reasons"].get(sku, "no_surplus_sku")
            elif not data["waste"]:
                reason = "no_surplus"
            else:
                reason = "no_receiver_deficit" if "no_receiver_deficit" in data["reasons"].values() else \
                    ("not_profitable" if "not_profitable" in data["reasons"].values() else "no_candidates")
        out = {"as_of": as_of.isoformat(), "store_id": store_id,
               "options": [{k: v for k, v in o.items() if k not in ("same_site", "lead_days", "all_waste_usd")}
                           for o in opts[:max(1, limit)]],
               "do_nothing": {"expected_waste_usd": waste or {"low": 0.0, "mid": 0.0, "high": 0.0}},
               "assumptions": {**xfer.assumptions(), "region_candidate_stores": data["region_candidates"]}}
        if reason:
            out["reason"] = reason
            out["reason_es"] = xfer.REASONS_ES[reason]
        return out

    def _transfer_issues(self, store_id: str, as_of: date, ref: date) -> list[dict[str, Any]]:
        data = self._transfer_data(store_id, as_of)
        by_sku: dict[str, list[dict[str, Any]]] = {}
        for o in data["options"]:
            by_sku.setdefault(o["sku"], []).append(o)
        out = []
        prods = self.product_catalog(store_id) if by_sku else {}
        for sku, opts in by_sku.items():
            iid = f"{store_id}|transfer_opportunity|{sku}"
            waste = data["waste"][sku]
            options = xfer.transfer_issue_options(iid, opts, as_of, waste["mid"])
            rec = finalize_options(options, "transfer_opportunity", self._calibration(store_id, as_of), self.config)
            best = opts[0]
            ev = [{"metric": "surplus_units", "value": best["surplus_units"], "unit": "units", "period": "until expiry",
                   "source": "inventory projection (weekday demand)"},
                  {"metric": "expected_waste_usd", "value": waste["mid"], "unit": "USD", "period": "until expiry",
                   "source": "inventory projection x unit_cost"},
                  {"metric": "receiver_deficit_units", "value": best["deficit_units"], "unit": "units",
                   "period": "until the receiver's next delivery", "source": "receiver inventory projection"}]
            out.append(_issue_dict(store_id, iid, as_of, ref, waste["mid"], ev, options, rec, sku,
                                   (prods.get(sku) or {}).get("product_name") or sku, (prods.get(sku) or {}).get("supplier_id")))
        return out

    def issues(self, store_id: str, as_of: date, limit: int = 5) -> list[dict[str, Any]]:
        return copy.deepcopy(self._all_issues(store_id, as_of)[:limit])

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
            daily.append({"date": d.isoformat(), "arrivals": arrivals, "demand": _f(dem), "projected_qty": _f(stock),
                          "projected": True})
            if stock < 0 and stockout is None:
                stockout = d.isoformat()
        return {"store_id": store_id, "sku": sku, "as_of": as_of.isoformat(), "method": METHOD, "horizon": horizon,
                "closing_qty": closing, "in_transit": [{"po_id": p["po_id"], "expected_date": p["expected_date"].isoformat(),
                                                        "qty": p["qty_ordered"], "projected": True} for p in pos],
                "days_of_cover": _f(closing / overall) if overall else None, "daily": daily,
                "projected_stockout_date": stockout}

    # -- Snapshot (the only place that reads inputs for glazed_metrics) ----------
    def _snapshot(self, store_id: str, as_of: date) -> StoreSnapshot:
        key = (store_id, as_of)
        if key in self._snaps:
            return self._snaps[key]
        ref = self._ref_date(store_id, as_of)
        start = ref - timedelta(days=SNAPSHOT_DAYS)
        inv = self._rows("SELECT sku, date, received_qty, units_sold, expired_qty, closing_qty, stockout_hours"
                         " FROM inventory_daily WHERE store_id=? AND date>? AND date<=? ORDER BY sku, date",
                         [store_id, start, ref])
        rows: dict[str, list[DayRow]] = {}
        for r in inv:
            rows.setdefault(r["sku"], []).append(DayRow(
                r["date"], int(r["received_qty"] or 0), int(r["units_sold"] or 0), int(r["expired_qty"] or 0),
                int(r["closing_qty"] or 0), float(r["stockout_hours"] or 0.0)))
        prods = {r["sku"]: Product(r["sku"], r["product_name"], r["supplier_id"], float(r["list_price_base"] or 0),
                                   float(r["unit_cost"] or 0), int(r["case_size"] or 1), r["shelf_life_days"],
                                   r["department"], r["category"])
                 for r in self._rows("SELECT * FROM products WHERE sku IN (SELECT DISTINCT sku FROM inventory_daily"
                                     " WHERE store_id=?) AND status IS DISTINCT FROM 'Discontinued'", [store_id])}
        pos = [PurchaseOrder(r["po_id"], r["sku"], r["order_date"], r["expected_date"],
                             r["received_date"] if r["received_date"] and r["received_date"] <= as_of else None,
                             int(r["qty_ordered"] or 0), r["qty_received"])
               for r in self._rows("SELECT po_id, sku, order_date, expected_date, received_date, qty_ordered, qty_received"
                                   " FROM purchase_orders WHERE store_id=? AND order_date<=? AND order_date>?"
                                   " ORDER BY order_date, po_id", [store_id, as_of, ref - timedelta(days=200)])]
        sups = self._rows("SELECT supplier_id, supplier_name, standard_lead_time_days, min_order_value, delivery_days"
                          " FROM suppliers")
        oh = self._q("SELECT coalesce(typical_open_hours, 12) FROM stores WHERE store_id=?", [store_id])
        closed = frozenset(r[0] for r in self._q(
            "SELECT date FROM store_calendar WHERE store_id=? AND status<>'open' AND date>? AND date<=?",
            [store_id, start, as_of]))
        snap = StoreSnapshot(
            StoreInfo(float(oh[0][0]) if oh else 12.0, closed), prods, rows, pos,
            {s["supplier_id"]: (parse_delivery_days(s["delivery_days"]), int(s["standard_lead_time_days"] or 1),
                                float(s["min_order_value"] or 0)) for s in sups},
            {s["supplier_id"]: s["supplier_name"] for s in sups})
        if len(self._snaps) >= 48:
            self._snaps.pop(next(iter(self._snaps)))
        self._snaps[key] = snap
        return snap

    # -- Order plan --------------------------------------------------------------
    def _plan_lines(self, snap: StoreSnapshot, store_id: str, as_of: date) -> list[dict[str, Any]]:
        ref = self._ref_date(store_id, as_of)
        lines = []
        calib = self._calibration(store_id, as_of).get(("stockout_risk", "place_order"))
        for sku in snap.products:
            state = snap.state_at(sku, ref)
            if state is None:
                continue
            rec, sold = snap.window_totals(sku, ref)
            ln = plan_line(state, self._cfg(as_of), snap.typical_order_qty(sku, ref), rec, sold)
            if ln:
                ln["supplier_name"] = snap.supplier_names.get(ln["supplier_id"])
                ln["confidence"] = line_confidence(calib, ln["net_usd_mid"], self.config)
                lines.append(ln)
        apply_min_order(lines, {k: v[2] for k, v in snap.suppliers.items()})
        lines.sort(key=lambda l: (-l["stockout_risk_without_order"], -l["est_cost_usd"], l["sku"]))
        return lines

    def order_plan(self, store_id: str, as_of: date) -> dict[str, Any]:
        snap = self._snapshot(store_id, as_of)
        lines = self._plan_lines(snap, store_id, as_of)
        by_sku: dict[str, dict[str, Any]] = {}
        for iss in self._all_issues(store_id, as_of):
            if iss.get("sku") and (iss["sku"] not in by_sku or iss["kind"] == "stockout_risk"):
                by_sku[iss["sku"]] = iss
        for ln in lines:
            ln["issue"] = copy.deepcopy(by_sku.get(ln["sku"]))
        totals: dict[str, float] = {}
        for ln in lines:
            totals[ln["supplier_id"]] = totals.get(ln["supplier_id"], 0.0) + ln["est_cost_usd"]
        return {"store_id": store_id, "as_of": as_of.isoformat(), "method": METRICS_METHOD,
                "note": "Newsvendor (1-day), order-up-to (2-14 days) and (s,S) (non-perishables) with a per-SKU "
                        "service level Cu/(Cu+Co). Estimates, not guarantees.",
                "suppliers": [{"supplier_id": k, "supplier_name": snap.supplier_names.get(k),
                               "order_value_usd": round(v, 2), "min_order_value": snap.suppliers.get(k, (0, 0, 0.0))[2]}
                              for k, v in sorted(totals.items())],
                "lines": lines[:50], "total_lines": len(lines),
                "data_caveats": ["Salvage value 0 (no markdown history).",
                                 "Delivery days follow suppliers.delivery_days; closures are known only up to as_of."]}

    # -- Suppliers ---------------------------------------------------------------
    def supplier_performance(self, store_id: str, as_of: date) -> list[dict[str, Any]]:
        rows = self._rows(
            "SELECT s.supplier_id, s.supplier_name, count(*) pos, avg(date_diff('day', po.order_date, po.received_date)) lt_mean,"
            " quantile_cont(date_diff('day', po.order_date, po.received_date), 0.9) lt_p90,"
            " 100.0*avg(CASE WHEN po.received_date<=po.expected_date THEN 1 ELSE 0 END) on_time,"
            " 100.0*sum(po.qty_received)/nullif(sum(po.qty_ordered),0) fill,"
            " s.standard_lead_time_days std_lt, 100*s.contract_on_time_rate c_ot, 100*s.contract_fill_rate c_fill,"
            " s.delivery_days"
            " FROM purchase_orders po JOIN suppliers s USING (supplier_id)"
            " WHERE po.store_id=? AND po.received_date IS NOT NULL AND po.received_date<=? AND po.order_date>?"
            " GROUP BY ALL ORDER BY pos DESC", [store_id, as_of, as_of - timedelta(days=180)])
        return [{"supplier_id": r["supplier_id"], "supplier_name": r["supplier_name"], "received_pos": r["pos"],
                 "lead_time_mean_days": _f(r["lt_mean"]), "lead_time_p90_days": _f(r["lt_p90"]),
                 "on_time_pct": _f(r["on_time"], 1), "fill_pct": _f(r["fill"], 1),
                 "contract_lead_time_days": r["std_lt"], "contract_on_time_pct": _f(r["c_ot"], 1),
                 "contract_fill_pct": _f(r["c_fill"], 1), "window_days": 180,
                 "delivery_days": sorted(parse_delivery_days(r["delivery_days"])),
                 "next_delivery": next_delivery_after(as_of, parse_delivery_days(r["delivery_days"])).isoformat(),
                 "next_delivery_projected": True}
                for r in rows]

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

    # -- Forecast inputs ---------------------------------------------------------
    def demand_history(self, store_id: str, as_of: date, sku: str | None, start: date) -> list[SkuSeries]:
        """Daily rows (units sold, stockout hours) per SKU from `start` to as_of; the SQL itself stops at as_of."""
        rows = self._rows(
            "SELECT i.sku, i.date, i.received_qty, i.units_sold, i.expired_qty, i.closing_qty, i.stockout_hours,"
            " p.list_price_base price, p.shelf_life_days FROM inventory_daily i JOIN products p USING (sku)"
            " WHERE i.store_id=? AND i.date BETWEEN ? AND ? AND (?::VARCHAR IS NULL OR i.sku=?)"
            " ORDER BY i.sku, i.date", [store_id, start, as_of, sku, sku])
        by: dict[str, tuple[float, int | None, list[DayRow]]] = {}
        for r in rows:
            by.setdefault(r["sku"], (float(r["price"] or 0), r["shelf_life_days"], []))[2].append(DayRow(
                r["date"], int(r["received_qty"] or 0), int(r["units_sold"] or 0), int(r["expired_qty"] or 0),
                int(r["closing_qty"] or 0), float(r["stockout_hours"] or 0.0)))
        return [SkuSeries(k, price, life, tuple(rs)) for k, (price, life, rs) in by.items()]

    def flow_history(self, store_id: str, as_of: date, start: date) -> list[dict[str, Any]]:
        """Store daily transactions, footfall (null when the conversion data is not valid) and net sales to as_of."""
        return self._rows("SELECT date, transactions, CASE WHEN conversion_valid THEN footfall END footfall, net_sales"
                          " FROM store_daily_kpis WHERE store_id=? AND date BETWEEN ? AND ?"
                          " AND coalesce(dq_flags,'') NOT LIKE '%implausible_ticket%' ORDER BY date",
                          [store_id, start, as_of])

    def store_net_sales(self, store_id: str, as_of: date, start: date) -> dict[date, float]:
        rows = self._q("SELECT date, net_sales FROM store_daily_kpis WHERE store_id=? AND date BETWEEN ? AND ?"
                       " AND net_sales IS NOT NULL", [store_id, start, as_of])
        return {r[0]: float(r[1]) for r in rows}

    # -- Manager metrics inputs (Wave 12) ---------------------------------------
    def store_profile(self, store_id: str) -> dict[str, Any]:
        r = self._rows("SELECT s.format, si.region, coalesce(s.typical_open_hours, 12) open_hours FROM stores s"
                       " LEFT JOIN sites si ON si.site_id=s.site_id WHERE s.store_id=?", [store_id])
        if not r:
            raise NotFound(f"store {store_id!r} not found")
        return {"format": r[0]["format"], "region": r[0]["region"], "open_hours": float(r[0]["open_hours"] or 12.0)}

    def product_catalog(self, store_id: str) -> dict[str, dict[str, Any]]:
        rows = self._rows("SELECT sku, product_name, department, supplier_id, unit_cost, list_price_base price, shelf_life_days"
                          " FROM products WHERE sku IN (SELECT DISTINCT sku FROM inventory_daily WHERE store_id=?)", [store_id])
        return {r["sku"]: {"product_name": r["product_name"], "department": r["department"], "supplier_id": r["supplier_id"],
                           "unit_cost": float(r["unit_cost"] or 0), "price": float(r["price"] or 0),
                           "shelf_life_days": r["shelf_life_days"]} for r in rows}

    def selling_skus(self, store_id: str, as_of: date, start: date) -> set[str]:
        return {r[0] for r in self._q("SELECT DISTINCT sku FROM sales_daily WHERE store_id=? AND date BETWEEN ? AND ?"
                                      " AND units_sold>0", [store_id, start, as_of])}

    def staffing_history(self, store_id: str, as_of: date, start: date) -> dict[str, Any]:
        """Transactions and staff hours per store-day for every store of this store's format, start..as_of."""
        fmt = self.store_profile(store_id)["format"]
        rows = self._rows("SELECT k.store_id, k.date, k.transactions, k.staff_hours FROM store_daily_kpis k"
                          " JOIN stores s USING (store_id) WHERE s.format=? AND k.date BETWEEN ? AND ?"
                          " AND k.staff_hours>0 AND coalesce(k.dq_flags,'') NOT LIKE '%staff_hours_invalid%'"
                          " AND coalesce(k.dq_flags,'') NOT LIKE '%implausible%' ORDER BY k.date, k.store_id", [fmt, start, as_of])
        return {"format": fmt, "rows": rows}

    def promotions(self, store_id: str, as_of: date) -> list[dict[str, Any]]:
        """Promotions whose scope covers the store's region (ALL or the region); planned dates only, no result data."""
        region = self.store_profile(store_id)["region"]
        return self._rows("SELECT promo_id, promo_name, department, category, discount_pct, start_date, end_date, region_scope"
                          " FROM promotions WHERE upper(coalesce(region_scope,'ALL'))='ALL' OR region_scope=?"
                          " ORDER BY start_date, promo_id", [region])

    def holidays(self, as_of: date, until: date) -> dict[date, str]:
        return {r[0]: r[1] or "Feriado" for r in self._q(
            "SELECT date, holiday_name FROM calendar WHERE is_holiday AND date BETWEEN ? AND ? ORDER BY date", [as_of, until])}

    def delivery_inputs(self, store_id: str, as_of: date, until: date) -> dict[str, Any]:
        """Orders placed by as_of that are open, overdue (within the lookback) or received on as_of, expected by `until`;
        a receipt after as_of is reported as not received. Plus the delivery weekdays of the store's suppliers."""
        pos = self._rows(
            "SELECT po.po_id, po.supplier_id, s.supplier_name, po.sku, p.product_name, po.qty_ordered qty, po.unit_cost,"
            " po.order_date, po.expected_date, CASE WHEN po.received_date<=? THEN po.received_date END received_date"
            " FROM purchase_orders po LEFT JOIN suppliers s USING (supplier_id) LEFT JOIN products p USING (sku)"
            " WHERE po.store_id=? AND po.order_date<=? AND po.expected_date<=? AND po.expected_date>=?"
            " AND (po.received_date IS NULL OR po.received_date>=?) ORDER BY po.expected_date, po.po_id, po.sku",
            [as_of, store_id, as_of, until, as_of - timedelta(days=LATE_LOOKBACK_DAYS), as_of])
        sups = self._rows("SELECT supplier_id, supplier_name, delivery_days FROM suppliers WHERE supplier_id IN"
                          " (SELECT DISTINCT supplier_id FROM products WHERE sku IN"
                          " (SELECT DISTINCT sku FROM inventory_daily WHERE store_id=?)) ORDER BY supplier_id", [store_id])
        return {"pos": pos, "suppliers": [{"supplier_id": r["supplier_id"], "supplier_name": r["supplier_name"],
                                           "delivery_days": sorted(parse_delivery_days(r["delivery_days"]))} for r in sups]}

    # -- Sentinel ----------------------------------------------------------------
    def observed_outcome(self, store_id: str, as_of: date, action_type: str, params: dict[str, Any],
                         partial: bool = False) -> dict[str, Any] | None:
        sku, d0 = params.get("sku"), params.get("decision_as_of")
        if not sku or not d0 or action_type not in ("place_order", "adjust_order_qty", "skip_order"):
            return None
        d0 = date.fromisoformat(d0)
        snap = self._snapshot(store_id, as_of)
        prod, rows = snap.products.get(sku), snap.rows.get(sku, [])
        win = [r for r in rows if d0 < r.date <= d0 + timedelta(days=HORIZON_DAYS) and r.date <= as_of]
        if prod is None or len(win) < (1 if partial else HORIZON_DAYS):
            return None
        qty = float(params.get("qty") or 0)
        if params.get("typical_qty") is not None:  # a reduction against the usual order
            net = realized_reduce_net(win, float(params["typical_qty"]) - qty, prod.price, prod.unit_cost)
        else:
            net = realized_add_net(win, uncensor(rows, snap.store.open_hours).demand, qty, prod.price, prod.unit_cost,
                                   is_short_life(prod.shelf_life_days))
        lost = lost_sales_window(rows, prod.price, snap.store.open_hours, win[0].date, win[-1].date)
        return {"net_usd": round(net, 2), "window": [win[0].date.isoformat(), win[-1].date.isoformat()],
                "waste_usd": round(sum(r.expired for r in win) * prod.unit_cost, 2),  # realized, this SKU, this window
                "lost_sales_usd": round(lost["mid"], 2),  # realized (mid estimate), this SKU, this window
                "censored": any(r.stockout_hours > 0 for r in win),  # a stockout hid part of the demand
                "units_sold": sum(r.sold for r in win), "units_forecast": self._forecast_units(snap, sku, d0, win),
                "units_expired": sum(r.expired for r in win),
                "method": "replay of the calibration rule on the decision window"}

    @staticmethod
    def _forecast_units(snap: StoreSnapshot, sku: str, d0: date, win: list[DayRow]) -> float | None:
        """Units the weekday model, fed only with data up to the decision day, expected to sell over the window."""
        state = snap.state_at(sku, d0)
        return None if state is None else round(sum(state.daily_mean(r.date) for r in win), 1)

    # -- Backtest ----------------------------------------------------------------
    def backtest_day(self, store_id: str, day: date, policy: str) -> dict[str, Any]:
        """Score the reorder policy on day+1 (the only place that reads data after the decision day).

        Each SKU's decision uses only data up to (day+1 - supplier lead time): an order that lands on day+1 had to be
        placed that many days earlier. Supply = service-level quantile of that day's demand (see metrics.backtest)."""
        d1 = day + timedelta(days=1)
        snap = self._snapshot(store_id, d1)
        cw = pw = cl = pl = 0.0
        for sku, prod in snap.products.items():
            outcome = next((r for r in reversed(snap.rows.get(sku, [])) if r.date == d1), None)
            if outcome is None:
                continue
            lead = max(1, round(snap.profile(prod.supplier_id, day).lead_mean))
            t_dec = min(day, d1 - timedelta(days=lead))
            hist = [r for r in snap.rows[sku] if t_dec - timedelta(days=self.config.history_days) < r.date <= t_dec]
            out = backtest_sku(hist, outcome, prod, snap.store.open_hours, self.config)
            cw, cl = cw + out["current"]["waste_usd"], cl + out["current"]["lost_sales_usd"]
            pw, pl = pw + out["policy"]["waste_usd"], pl + out["policy"]["lost_sales_usd"]
        return {"date": day.isoformat(), "outcome_date": d1.isoformat(), "method": METRICS_METHOD,
                "current": {"waste_usd": round(cw, 2), "lost_sales_usd": round(cl, 2)},
                "policy": {"waste_usd": round(pw, 2), "lost_sales_usd": round(pl, 2)}}
