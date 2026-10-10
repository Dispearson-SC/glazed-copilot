"""Holdout counterfactual: what the stores actually did (A) vs. applying the system's recommendations (B).

Holdout = last 20% of the dataset (2026-07-20 .. 2026-09-30; the 80% cut is 2026-07-19).

Stages (each one resumable, all read-only on Dataset/clean/glazed.duckdb):
  decide    run the deterministic backend (glazed_backend.adapters.driven.duckdb_metrics) in-process for every store and
            decision day d with as_of=d (only data <= d) and cache the recommended option of every issue.
  simulate  replay the holdout with REAL demand under policy A (actual receipts) and policy B (A + recommended actions).
  report    CSV tables + PNG charts (+ numbers for the Spanish report).

Usage (from backend/):
  PYTHONPATH=.deps:src python3 scripts/holdout_counterfactual.py decide --workers 5
  PYTHONPATH=.deps:src python3 scripts/holdout_counterfactual.py simulate
  PYTHONPATH=.deps:src:<matplotlib dir> python3 scripts/holdout_counterfactual.py report

Assumptions are listed in docs/holdout-counterfactual/holdout-counterfactual-v1.md and in the SIM_* constants below.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from collections import defaultdict
from datetime import date, timedelta
from multiprocessing import Pool
from pathlib import Path
from typing import Any

import duckdb

REPO = Path(__file__).resolve().parents[2]
DB = os.environ.get("GLAZED_DUCKDB", str(REPO.parent / "Dataset" / "clean" / "glazed.duckdb"))
OUT = REPO / "docs" / "holdout-counterfactual"
CACHE = OUT / "cache"

CUT = date(2026, 7, 19)          # last day of the 80% training part
HOLD_START = date(2026, 7, 20)
HOLD_END = date(2026, 9, 30)
DECISION_FIRST = CUT             # the decision taken on the close of 07-19 acts on the first holdout day
DECISION_LAST = HOLD_END - timedelta(days=1)

# ---- simulation assumptions -------------------------------------------------------------------------------------
SIM_MARKDOWN_RECOVERY = 0.50     # share of otherwise-expiring units sold at the discount (backend's own mid assumption)
SIM_MARKDOWN_DISCOUNT = 0.30
SIM_TRANSFER_LEAD = {True: 1, False: 2}   # same site / cross site (backend transfers.LEAD_DAYS)
NON_INVENTORY_ACTIONS = {"data_fix_task", "shift_staff_hours", "run_promo", "block_promo", "review_promo",
                         "prepare_for_event", "adjust_staffing"}


# =====================================================================================================================
# Stage 1: decide
# =====================================================================================================================
def _make_metrics():
    from glazed_backend.adapters.driven.duckdb_metrics import DuckDBMetrics

    class WeeklyCalibMetrics(DuckDBMetrics):
        """Same backend; the backtest calibration (confidence -> N1 vs N2 label only) is refreshed on Mondays instead of
        daily. It is always computed with data <= the Monday <= as_of, so there is no look-ahead. The recommended
        option does not depend on it (best non-N0 net), only the N1/N2 split does."""

        def _calibration(self, store_id, as_of):
            monday = as_of - timedelta(days=as_of.weekday())
            return super()._calibration(store_id, monday)

    return WeeklyCalibMetrics(DB)


def _compact(issue: dict[str, Any]) -> dict[str, Any] | None:
    rec = next((o for o in issue.get("options") or [] if o.get("option_id") == issue.get("recommended_option_id")), None)
    if rec is None:
        return None
    return {"iid": issue["issue_id"], "kind": issue.get("kind"), "kinds": issue.get("kinds") or [issue.get("kind")],
            "sku": issue.get("sku"), "a": rec["action_type"], "tier": rec.get("tier"), "net": rec.get("net_usd_mid"),
            "cost": rec.get("cost_usd"), "sev": issue.get("severity_usd"), "p": rec.get("params") or {}}


def _decide_store(args: tuple[str, str]) -> tuple[str, int, float]:
    store_id, _ = args
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"decisions_{store_id}.jsonl"
    done: set[str] = set()
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                done.add(json.loads(line)["d"])
            except Exception:  # truncated last line of an interrupted run
                pass
    m = _make_metrics()
    info = m._rows("SELECT opened_date, closed_date FROM stores WHERE store_id=?", [store_id])[0]
    first = max(DECISION_FIRST, info["opened_date"] or DECISION_FIRST)
    last = DECISION_LAST if info["closed_date"] is None else min(DECISION_LAST, info["closed_date"] - timedelta(days=1))
    t0, n = time.time(), 0
    with path.open("a") as fh:
        d = first
        while d <= last:
            if d.isoformat() not in done:
                m._snaps.clear(); m._issues.clear(); m._xfers.clear()  # keep memory flat; calibration cache survives
                try:
                    issues = m.issues(store_id, d, limit=100_000)
                    err = None
                except Exception as e:  # noqa: BLE001 - a bad store-day must not kill the run; it is recorded
                    issues, err = [], f"{type(e).__name__}: {e}"
                acts = [c for c in (_compact(i) for i in issues) if c]
                fh.write(json.dumps({"d": d.isoformat(), "store": store_id, "n_issues": len(issues), "err": err,
                                     "acts": acts}, default=str) + "\n")
                fh.flush()
                n += 1
            d += timedelta(days=1)
    return store_id, n, time.time() - t0


def stage_decide(workers: int, stores: list[str] | None) -> None:
    con = duckdb.connect(DB, read_only=True)
    rows = con.execute("SELECT store_id FROM stores ORDER BY store_id").fetchall()
    all_stores = [r[0] for r in rows]
    con.close()
    todo = stores or all_stores
    t0 = time.time()
    with Pool(workers) as pool:
        for sid, n, secs in pool.imap_unordered(_decide_store, [(s, "") for s in todo]):
            print(f"[decide] {sid}: {n} new store-days in {secs:.0f}s (elapsed {time.time() - t0:.0f}s)", flush=True)



# =====================================================================================================================
# Stage 2: simulate (closed loop on the B-world, or replay of the cached A-world decisions)
# =====================================================================================================================
INF = 10 ** 9
FAMILIES = ("reduce", "add", "calendar", "markdown", "transfer")


def _od(d: date) -> int:
    return d.toordinal()


def _dd(o: int) -> date:
    return date.fromordinal(o)


def _round_case(q: float, case: int) -> int:
    case = max(1, int(case or 1))
    return int(math.floor(q / case + 0.5)) * case


class Unit:
    """FIFO lots of one (store, SKU). Lot = [last sellable day (ordinal), qty]."""
    __slots__ = ("lots", "life", "cost", "case", "supplier", "dept")

    def __init__(self, life: int | None, cost: float, case: int, supplier: str, dept: str) -> None:
        self.life = life if (life is not None and 0 < life < 100) else (1 if (life is not None and life <= 0) else None)
        self.cost, self.case, self.supplier, self.dept = cost, case, supplier, dept
        self.lots: list[list[int]] = []

    def exp_of(self, day: int) -> int:
        return INF if self.life is None else day + self.life - 1

    def add(self, exp: int, qty: int) -> None:
        if qty <= 0:
            return
        for lot in self.lots:
            if lot[0] == exp:
                lot[1] += qty
                return
        self.lots.append([exp, qty])
        self.lots.sort(key=lambda l: l[0])

    @property
    def stock(self) -> int:
        return sum(l[1] for l in self.lots)

    def take(self, n: int) -> int:
        got = 0
        for lot in self.lots:
            if got >= n:
                break
            k = min(lot[1], n - got)
            lot[1] -= k
            got += k
        self.lots = [l for l in self.lots if l[1] > 0]
        return got

    def expire(self, day: int) -> int:
        out = sum(l[1] for l in self.lots if l[0] <= day)
        self.lots = [l for l in self.lots if l[0] > day]
        return out

    def expiring_today(self, day: int) -> int:
        return sum(l[1] for l in self.lots if l[0] <= day)

    def take_expiring(self, day: int, n: int) -> int:
        got = 0
        for lot in self.lots:
            if lot[0] <= day and got < n:
                k = min(lot[1], n - got)
                lot[1] -= k
                got += k
        self.lots = [l for l in self.lots if l[1] > 0]
        return got

    def ship(self, n: int, min_exp: int) -> list[tuple[int, int]]:
        """Oldest-first lots that are still sellable at the receiver on arrival (last sellable >= arrival)."""
        out, left = [], n
        for lot in self.lots:
            if left <= 0:
                break
            if lot[0] >= min_exp:
                k = min(lot[1], left)
                lot[1] -= k
                left -= k
                out.append((lot[0], k))
        self.lots = [l for l in self.lots if l[1] > 0]
        return out


class PoLine:
    __slots__ = ("store", "sku", "po_id", "supplier", "order", "expected", "recv", "q_ord", "q_recv", "ratio", "cur_ord",
                 "cur_recv", "cal_done")

    def __init__(self, store, sku, po_id, supplier, order, expected, recv, q_ord, q_recv):
        self.store, self.sku, self.po_id, self.supplier = store, sku, po_id, supplier
        self.order, self.expected, self.recv, self.q_ord, self.q_recv = order, expected, recv, q_ord, q_recv
        self.ratio, self.cur_ord, self.cur_recv, self.cal_done = 1.0, q_ord, q_recv, False


class World:
    """Everything the simulation needs for a set of stores (a region), loaded read-only from the clean DuckDB."""

    def __init__(self, store_ids: list[str], censor_scale: float = 1.0) -> None:
        from glazed_backend.metrics.demand import uncensor
        from glazed_backend.metrics.schedule import parse_delivery_days
        from glazed_backend.metrics.types import DayRow
        con = duckdb.connect(DB, read_only=True)
        self.stores = store_ids
        ph = ",".join("'" + s + "'" for s in store_ids)
        self.prod = {r[0]: r[1:] for r in con.execute(
            "SELECT sku, unit_cost, list_price_base, case_size, shelf_life_days, supplier_id, department FROM products").fetchall()}
        self.store_info = {r[0]: r[1:] for r in con.execute(
            f"SELECT s.store_id, s.site_id, coalesce(s.typical_open_hours,12), s.opened_date, s.closed_date FROM stores s"
            f" WHERE s.store_id IN ({ph})").fetchall()}
        sup = con.execute("SELECT supplier_id, standard_lead_time_days, delivery_days FROM suppliers").fetchall()
        self.sup_days = {r[0]: parse_delivery_days(r[2]) for r in sup}
        self.sup_lead = {r[0]: int(r[1] or 1) for r in sup}
        inv = con.execute(
            f"SELECT store_id, sku, date, received_qty, units_sold, expired_qty, damaged_qty, closing_qty, stockout_hours"
            f" FROM inventory_daily WHERE store_id IN ({ph}) AND date >= ? AND date <= ? ORDER BY store_id, sku, date",
            [CUT - timedelta(days=120), HOLD_END]).fetchall()
        self.rows: dict[tuple[str, str], list[tuple]] = defaultdict(list)
        for r in inv:
            self.rows[(r[0], r[1])].append(r[2:])
        # actual (A) series for the holdout
        self.recv_A: dict[tuple[str, str], dict[int, int]] = defaultdict(dict)
        self.dem: dict[tuple[str, str], dict[int, int]] = defaultdict(dict)
        self.dmg: dict[tuple[str, str], dict[int, int]] = defaultdict(dict)
        self.has_row: dict[tuple[str, str], set[int]] = defaultdict(set)
        self.actual: dict[tuple[str, str, int], tuple] = {}
        self.units_init: dict[tuple[str, str], Unit] = {}
        for key, rs in self.rows.items():
            store, sku = key
            life = self.prod[sku][3]
            dayrows = [DayRow(r[0], int(r[1] or 0), int(r[2] or 0), int(r[3] or 0), int(r[5] or 0), float(r[6] or 0.0))
                       for r in rs if r[0] >= CUT - timedelta(days=56)]
            dem = uncensor(dayrows, float(self.store_info[store][1])).demand
            for r in rs:
                if HOLD_START <= r[0] <= HOLD_END:
                    o = _od(r[0])
                    self.has_row[key].add(o)
                    self.recv_A[key][o] = int(r[1] or 0)
                    sold0 = float(r[2] or 0)  # censor_scale: share of the backend's stockout correction that is believed (1 = all)
                    self.dem[key][o] = int(round(sold0 + censor_scale * (dem.get(r[0], sold0) - sold0)))
                    self.dmg[key][o] = int(r[4] or 0)
                    self.actual[(store, sku, o)] = (int(r[1] or 0), int(r[2] or 0), int(r[3] or 0), int(r[4] or 0),
                                                    int(r[5] or 0), float(r[6] or 0.0))
            hist = [r for r in rs if r[0] <= CUT]
            if not hist:
                continue
            u = Unit(life, float(self.prod[sku][0] or 0), int(self.prod[sku][2] or 1), self.prod[sku][4], self.prod[sku][5])
            left = int(hist[-1][5] or 0)
            for r in sorted(hist, key=lambda x: x[0], reverse=True):
                if left <= 0:
                    break
                k = min(left, int(r[1] or 0))
                if k > 0:
                    u.add(u.exp_of(_od(r[0])), k)
                    left -= k
            if left > 0:  # stock no receipt explains: assume it arrived the day before the cut
                u.add(u.exp_of(_od(CUT) - 1), left)
            self.units_init[key] = u
        # realised unit prices (net of discounts) by store, sku, day
        self.price: dict[tuple[str, str, int], float] = {}
        tot: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
        for st, sk, d, ns, un in con.execute(
                f"SELECT store_id, sku, date, sum(net_sales), sum(units_sold) FROM sales_daily WHERE store_id IN ({ph})"
                f" AND date >= ? GROUP BY 1,2,3", [HOLD_START]).fetchall():
            if un and un > 0 and ns is not None and (st, sk) in self.units_init:
                self.price[(st, sk, _od(d))] = float(ns) / float(un)
                tot[(st, sk)][0] += float(ns)
                tot[(st, sk)][1] += float(un)
        self.price_avg = {k: v[0] / v[1] for k, v in tot.items() if v[1] > 0}
        # purchase orders: plan of the holdout (B can modify) and lead history (A facts, only used with receipt <= d)
        self.po_plan: dict[tuple[str, str, int], list[PoLine]] = defaultdict(list)
        for r in con.execute(
                f"SELECT po_id, store_id, supplier_id, sku, order_date, expected_date, received_date, qty_ordered, qty_received"
                f" FROM purchase_orders WHERE store_id IN ({ph}) AND order_date >= ? AND order_date <= ?",
                [HOLD_START, HOLD_END]).fetchall():
            ln = PoLine(r[1], r[3], r[0], r[2], _od(r[4]), r[5], None if r[6] is None else _od(r[6]),
                        int(r[7] or 0), 0 if r[8] is None else int(r[8]))
            self.po_plan[(r[1], r[3], _od(r[4]))].append(ln)
        self.leads: dict[tuple[str, str], list[tuple[int, int, int]]] = defaultdict(list)  # (order, received, lead)
        for st, su, od, rd in con.execute(
                f"SELECT store_id, supplier_id, order_date, received_date FROM purchase_orders WHERE store_id IN ({ph})"
                f" AND received_date IS NOT NULL AND order_date >= ? ORDER BY received_date",
                [CUT - timedelta(days=260)]).fetchall():
            self.leads[(st, su)].append((_od(od), _od(rd), (rd - od).days))
        con.close()
        self._arr: dict[tuple[str, str, int], int] = {}

    def lead_mean(self, store: str, supplier: str, d: int) -> float:
        got = [x[2] for x in self.leads.get((store, supplier), []) if x[1] <= d and x[0] > d - 180]
        return sum(got) / len(got) if got else float(self.sup_lead.get(supplier, 1))

    def arrival(self, store: str, supplier: str, d: int) -> int:
        """Same rule as the backend (policy.delivery_window): lead = round(mean lead of orders received <= d),
        first supplier delivery weekday on or after d + lead."""
        key = (store, supplier, d)
        if key not in self._arr:
            lead = max(1, round(self.lead_mean(store, supplier, d)))
            x, days = d + lead, self.sup_days.get(supplier, frozenset(range(1, 8)))
            for _ in range(60):
                if _dd(x).isoweekday() in days:
                    break
                x += 1
            self._arr[key] = x
        return self._arr[key]

    def price_at(self, store: str, sku: str, o: int) -> float:
        p = self.price.get((store, sku, o)) or self.price_avg.get((store, sku))
        return p if p else float(self.prod[sku][1] or 0.0)


def _classify(a: dict) -> tuple[str, Any]:
    t, p = a["a"], a.get("p") or {}
    if t == "transfer_stock":
        return "transfer", None
    if t == "markdown_end_of_day":
        return "markdown", None
    if t == "skip_order":
        return "reduce", 0
    if t == "adjust_order_qty":
        if "event" in p:
            return "calendar", None
        if "typical_qty" in p:
            return "reduce", int(p.get("qty") or 0)
        return "add", None
    if t == "place_order":
        return "add", None
    return "other", None


class Sim:
    """Day-by-day replay of A (actual receipts) and B (A + approved recommendations) with real demand."""

    def __init__(self, world: World, families: set[str], guards: bool) -> None:
        self.w, self.fam, self.guards = world, families, guards
        self.uA = {k: _clone(u) for k, u in world.units_init.items()}
        self.uB = {k: _clone(u) for k, u in world.units_init.items()}
        self.recv_B: dict[tuple[str, str], dict[int, int]] = {k: dict(v) for k, v in world.recv_A.items()}
        self.tin: dict[tuple[str, str, int], list[tuple[int, int]]] = defaultdict(list)
        self.tout: dict[int, list[tuple]] = defaultdict(list)
        self.md_today: dict[tuple[str, str], int] = {}
        self.add_until: dict[tuple[str, str], int] = {}
        self.xfer_until: dict[tuple[str, str], int] = {}
        self.xfer_rx_until: dict[tuple[str, str], int] = {}
        # metrics[policy][(store, day)] = [rev, cogs, lost_rev, waste_cost, purch_cost, xfer_cost, md_rev, sold, lost_u, waste_u,
        #                                   purch_u, md_units, md_margin, stockout_u]
        self.m = {"A": defaultdict(lambda: [0.0] * 14), "B": defaultdict(lambda: [0.0] * 14)}
        self.sku_m: dict[str, dict[str, list[float]]] = {"A": {}, "B": {}}  # same layout, per SKU (all stores)
        self.rec = defaultdict(int)       # recommended (non-N0, non-do_nothing) actions by (action_type, tier)
        self.exe = defaultdict(float)     # executed effects by label
        self.rec_day = defaultdict(int)   # (day, action_type) -> n
        self.n_issues = 0

    # ---- applying one store-day of recommendations ----------------------------------------------------------------
    def apply(self, store: str, d: int, acts: list[dict], b_rows: list | None) -> None:
        w, t = self.w, d + 1
        for a in acts:
            if a["a"] == "do_nothing" or a.get("tier") in (None, "N0"):
                continue
            self.rec[(a["a"], a["tier"])] += 1
            self.rec_day[(d, a["a"])] += 1
            fam, tgt = _classify(a)
            if fam == "other" or fam not in self.fam:
                continue
            p, sku = a["p"], a.get("sku")
            if fam == "reduce":
                self._reduce(store, sku, t, tgt, p.get("pattern") == "alternate_days")
            elif fam == "add":
                lines = p.get("lines") or [{"sku": sku, "qty": p.get("qty")}]
                for ln in lines:
                    self._add(store, ln["sku"], d, int(ln["qty"] or 0), p.get("supplier_id") or a["p"].get("supplier_id"))
            elif fam == "calendar":
                self._calendar(store, d, p)
            elif fam == "markdown":
                self.md_today[(store, sku)] = max(self.md_today.get((store, sku), 0), int(p.get("units") or 0))
            elif fam == "transfer":
                self._transfer(store, sku, d, p)

    def _set_ratio(self, ln: PoLine, ratio: float, case: int) -> None:
        new_ord = _round_case(ln.q_ord * ratio, case) if ratio > 0 else 0
        new_ord = max(0, new_ord)
        ratio = new_ord / ln.q_ord if ln.q_ord else 1.0
        new_recv = int(round(ln.q_recv * ratio))
        if ln.recv is not None and HOLD_START.toordinal() <= ln.recv <= HOLD_END.toordinal():
            sched = self.recv_B.setdefault((ln.store, ln.sku), {})
            sched[ln.recv] = max(0, sched.get(ln.recv, 0) + new_recv - ln.cur_recv)
        ln.ratio, ln.cur_ord, ln.cur_recv = ratio, new_ord, new_recv

    def _reduce(self, store: str, sku: str, t: int, target: int, alternate: bool) -> None:
        for ln in self.w.po_plan.get((store, sku, t), []):
            case = self.w.prod[sku][2] or 1
            if target <= 0:
                newq = 0
            else:
                newq = _round_case(target, case)
            if newq < ln.cur_ord:
                self._set_ratio(ln, newq / ln.q_ord if ln.q_ord else 1.0, case)
        if alternate:  # every other day: tomorrow's order is skipped
            for ln in self.w.po_plan.get((store, sku, t + 1), []):
                self._set_ratio(ln, 0.0, self.w.prod[sku][2] or 1)

    def _add(self, store: str, sku: str, d: int, qty: int, supplier: str | None) -> None:
        w = self.w
        if qty <= 0 or (store, sku) not in self.uB:
            return
        if self.guards and self.add_until.get((store, sku), -1) >= d:
            return
        supplier = supplier or w.prod[sku][4]
        arr = w.arrival(store, supplier, d)
        if arr > HOLD_END.toordinal():
            return
        sched = self.recv_B.setdefault((store, sku), {})
        sched[arr] = sched.get(arr, 0) + qty
        self.add_until[(store, sku)] = arr
        self.exe["add_orders"] += 1
        self.exe["add_units"] += qty
        self.new_pos.append((store, sku, supplier, d, arr, qty))

    def _calendar(self, store: str, d: int, p: dict) -> None:
        w = self.w
        win = [_od(date.fromisoformat(x)) for x in p["window"]]
        eff = {e["department"]: e["effect_pct"] for e in p.get("effects", [])}
        for (st, sku, o), lines in w.po_plan.items():
            if st != store or o <= d or sku not in w.prod:
                continue
            dept = w.prod[sku][5]
            if dept not in eff:
                continue
            for ln in lines:
                if ln.cal_done or not (win[0] <= _od(ln.expected) <= win[1]):
                    continue
                ln.cal_done = True
                case = w.prod[sku][2] or 1
                self._set_ratio(ln, max(0.0, ln.ratio * (1.0 + eff[dept] / 100.0)), case)
                self.exe["calendar_lines"] += 1

    def _transfer(self, store: str, sku: str, d: int, p: dict) -> None:
        w = self.w
        rx, q = p["to_store"], int(p.get("qty") or 0)
        if (store, sku) not in self.uB or (rx, sku) not in self.uB or q <= 0:
            return
        life = self.uB[(store, sku)].life or 7
        if self.guards and (self.xfer_until.get((store, sku), -1) >= d or self.xfer_rx_until.get((rx, sku), -1) >= d):
            return
        same = w.store_info[store][0] == w.store_info.get(rx, (None,))[0]
        lead = SIM_TRANSFER_LEAD[bool(same)]
        self.tout[d + 1].append((store, sku, rx, q, d + lead, bool(same)))
        self.xfer_until[(store, sku)] = d + life
        self.xfer_rx_until[(rx, sku)] = d + lead + 1

    # ---- simulating day t -------------------------------------------------------------------------------------------
    def step_day(self, t: int, open_hours: dict[str, float]) -> dict[tuple[str, str], tuple]:
        """Advance A and B by one day; returns B's inventory rows {(store, sku): (open, recv, sold, expired, damaged, close,
        stockout_hours)} for the stores that traded that day."""
        w = self.w
        out: dict[tuple[str, str], tuple] = {}
        # transfers leave the sender at the start of the day
        for (s0, sku, rx, q, arr, same) in self.tout.pop(t, []):
            u = self.uB[(s0, sku)]
            got = u.ship(q, arr)
            n = sum(k for _, k in got)
            if n:
                from glazed_backend.metrics.transfers import transfer_cost
                cost = transfer_cost(n, same)
                self.m["B"][(s0, t)][5] += cost
                self.exe["transfer_units"] += n
                self.exe["transfer_cost_usd"] += cost
                self.exe["transfers"] += 1
                self.tin[(rx, sku, arr)] += got
                self.dmg_extra[(s0, sku, t)] = n
        for key in self.uB:
            store, sku = key
            cost = self.uB[key].cost
            for pol, units in (("A", self.uA), ("B", self.uB)):
                u = units[key]
                opening = u.stock
                recv = (w.recv_A[key].get(t, 0) if pol == "A" else self.recv_B.get(key, {}).get(t, 0))
                if recv:
                    u.add(u.exp_of(t), recv)
                tin = 0
                if pol == "B":
                    for exp, k in self.tin.pop((store, sku, t), []):
                        if exp >= t:
                            u.add(exp, k)
                            tin += k
                row = self.m[pol][(store, t)]
                before = list(row)
                active = t in w.has_row[key]
                sold = lost = dmg = reg_sold = 0
                price = w.price_at(store, sku, t) if active else 0.0
                if active:
                    dem = w.dem[key].get(t, 0)
                    sold = u.take(dem)
                    lost = dem - sold
                    reg_sold = sold
                    dmg = u.take(w.dmg[key].get(t, 0))
                    row[0] += sold * price
                    row[1] += sold * cost
                    row[2] += lost * price
                    row[7] += sold
                    row[8] += lost
                    if lost > 0:
                        row[13] += 1
                md_u = 0
                if pol == "B" and active and "markdown" in self.fam and (store, sku) in self.md_today:
                    cap = self.md_today[(store, sku)]
                    rem = u.expiring_today(t)
                    mark = min(rem, cap)
                    rec_units = int(mark * SIM_MARKDOWN_RECOVERY)
                    if rec_units > 0:
                        u.take_expiring(t, rec_units)
                        row[0] += rec_units * price * (1.0 - SIM_MARKDOWN_DISCOUNT)
                        row[1] += rec_units * cost
                        row[6] += rec_units * price * (1.0 - SIM_MARKDOWN_DISCOUNT)
                        row[11] += rec_units
                        row[12] += rec_units * (price * (1.0 - SIM_MARKDOWN_DISCOUNT) - cost)
                        row[7] += rec_units
                        md_u = rec_units
                        sold += rec_units
                        self.exe["markdown_units"] += rec_units
                exp_u = u.expire(t)
                row[3] += exp_u * cost
                row[4] += recv * cost
                row[9] += exp_u
                row[10] += recv
                acc = self.sku_m[pol].setdefault(sku, [0.0] * 14)
                for i in range(14):
                    acc[i] += row[i] - before[i]
                if pol == "B" and active:
                    xo = self.dmg_extra.pop((store, sku, t), 0)
                    dem = w.dem[key].get(t, 0)
                    frac = 0.0 if dem <= 0 or reg_sold >= dem else min(1.0, 1.0 - reg_sold / dem)
                    out[key] = (opening, recv + tin, sold, exp_u, dmg + xo, u.stock, frac * open_hours.get(store, 12.0))
        # markdown requests are valid for a single day
        self.md_today = {}
        return out

    def close_totals(self) -> dict[str, Any]:
        res = {}
        for pol, units in (("A", self.uA), ("B", self.uB)):
            res[pol] = {"units": sum(u.stock for u in units.values()),
                        "value": sum(u.stock * u.cost for u in units.values())}
        res["start"] = {"units": sum(u.stock for u in self.w.units_init.values()),
                        "value": sum(u.stock * u.cost for u in self.w.units_init.values())}
        return res


def _clone(u: Unit) -> Unit:
    c = Unit.__new__(Unit)
    c.life, c.cost, c.case, c.supplier, c.dept = u.life, u.cost, u.case, u.supplier, u.dept
    c.lots = [list(l) for l in u.lots]
    return c


def _lit(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def _insert(m, table: str, cols: list[str], rows: list[tuple]) -> None:
    for i in range(0, len(rows), 400):
        chunk = rows[i:i + 400]
        sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES " + ",".join("(" + ",".join(_lit(v) for v in r) + ")" for r in chunk)
        with m._lock:
            m._con.execute(sql)


def _po_rows(lines: list[PoLine], w: World, status: str = "Delivered") -> list[tuple]:
    out = []
    for ln in lines:
        cost = float(w.prod[ln.sku][0] or 0)
        out.append((ln.po_id, ln.store, ln.supplier, ln.sku, _dd(ln.order).isoformat(), ln.expected.isoformat(),
                    None if ln.recv is None else _dd(ln.recv).isoformat(), ln.cur_ord, ln.cur_recv, cost, status, None))
    return out


def run_region(args: tuple[str, list[str], str, list[str], str | None, float]) -> dict[str, Any]:
    """mode 'closed': the backend runs on the B-world (its own inventory and orders) every day, so what it recommends
    tomorrow reflects what it did today. mode 'replay': decisions cached from the A-world (stage decide) are applied
    open-loop with cooldown guards (no double counting of a persistent signal). Returns the metrics for the aggregator."""
    region, store_ids, mode, families, last, censor_scale = args
    t0 = time.time()
    w = World(store_ids, censor_scale)
    sim = Sim(w, set(families), guards=(mode == "replay"))
    sim.new_pos, sim.dmg_extra = [], {}
    open_hours = {s: float(w.store_info[s][1]) for s in store_ids}
    end = HOLD_END if last is None else date.fromisoformat(last)
    store_days: dict[str, set[int]] = defaultdict(set)
    for (st, _sku), rs in w.rows.items():
        store_days[st].update(_od(r[0]) for r in rs)
    po_days: dict[str, set[int]] = defaultdict(set)
    for (st, _sku, o) in w.po_plan:
        po_days[st].add(o)
    m = None
    cached: dict[tuple[str, str], list[dict]] = {}
    if mode == "closed":
        m = _make_metrics()
        sids = ",".join("'" + s + "'" for s in store_ids)
        with m._lock:  # session-private TEMP copies shadow the tables: the backend only ever sees the B-world
            m._con.execute(f"CREATE TEMP TABLE inventory_daily AS SELECT * FROM inventory_daily WHERE store_id IN ({sids})"
                           f" AND date <= DATE '{CUT.isoformat()}'")
            m._con.execute(f"CREATE TEMP TABLE purchase_orders AS SELECT * FROM purchase_orders WHERE store_id IN ({sids})"
                           f" AND order_date <= DATE '{CUT.isoformat()}'")
    else:
        for s in store_ids:
            p = CACHE / f"decisions_{s}.jsonl"
            if p.exists():
                for line in p.read_text().splitlines():
                    j = json.loads(line)
                    cached[(s, j["d"])] = j["acts"]
    inv_cols = ["date", "store_id", "sku", "opening_qty", "received_qty", "units_sold", "expired_qty", "damaged_qty",
                "closing_qty", "closing_qty_raw", "identity_ok", "on_order_qty", "stockout_hours", "dq_flags"]
    po_cols = ["po_id", "store_id", "supplier_id", "sku", "order_date", "expected_date", "received_date", "qty_ordered",
               "qty_received", "unit_cost", "status", "dq_flags"]
    for t in range(_od(HOLD_START), _od(end) + 1):
        d = t - 1
        sim.new_pos = []
        if mode == "closed":
            m._snaps.clear(); m._issues.clear(); m._xfers.clear()
            # no-look-ahead guard: the world the backend reads holds nothing after the decision day d
            with m._lock:
                last_inv = m._con.execute("SELECT max(date) FROM inventory_daily").fetchone()[0]
                last_po = m._con.execute("SELECT max(order_date) FROM purchase_orders").fetchone()[0]
            assert last_inv <= _dd(d) and last_po <= _dd(d), (last_inv, last_po, _dd(d))
        for s in store_ids:
            info = w.store_info[s]
            if (info[2] and _od(info[2]) > d) or (info[3] and _od(info[3]) <= d):
                continue
            if d not in store_days[s] and (d + 1) not in po_days[s]:
                continue  # closed on d and nothing to order tomorrow
            if mode == "closed":
                try:
                    issues = m.issues(s, _dd(d), limit=100_000)
                except Exception as e:  # noqa: BLE001 - recorded, the store-day simply yields no action
                    print(f"[{region}] {s} {_dd(d)} issues failed: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
                    issues = []
                sim.n_issues += len(issues)
                acts = [c for c in (_compact(i) for i in issues) if c]
            else:
                acts = cached.get((s, _dd(d).isoformat()), [])
            sim.apply(s, d, acts, None)
        if mode == "closed":
            # orders placed on day t (A's real orders, reduced / scaled when the system said so) and the extra orders of
            # day d become visible to the backend from the next decision on
            lines = [ln for (st, _k, o), ls in w.po_plan.items() if o == t for ln in ls]
            rows = _po_rows(lines, w)
            for (s, sku, sup, dd_, arr, q) in sim.new_pos:
                rows.append((f"B-{s}-{sku}-{_dd(dd_).isoformat()}", s, sup, sku, _dd(dd_).isoformat(), _dd(arr).isoformat(),
                             _dd(arr).isoformat(), q, q, float(w.prod[sku][0] or 0), "Delivered", None))
            _insert(m, "purchase_orders", po_cols, rows)
        out = sim.step_day(t, open_hours)
        if mode == "closed":
            _insert(m, "inventory_daily", inv_cols,
                    [(_dd(t).isoformat(), s, sku, op, rc, sd, ex, dm, cl, float(cl), True, 0, round(so, 3), None)
                     for (s, sku), (op, rc, sd, ex, dm, cl, so) in out.items()])
        if (t - _od(HOLD_START)) % 10 == 0:
            print(f"[{mode}:{region}] {_dd(t)} elapsed {time.time() - t0:.0f}s", flush=True)
    tot = sim.close_totals()
    lines_all = [ln for ls in w.po_plan.values() for ln in ls if ln.order <= _od(end)]
    sim.exe["po_units_A"] = sum(ln.q_ord for ln in lines_all)
    sim.exe["po_units_B_removed"] = sum(max(0, ln.q_ord - ln.cur_ord) for ln in lines_all)
    sim.exe["po_units_B_calendar_added"] = sum(max(0, ln.cur_ord - ln.q_ord) for ln in lines_all)
    sim.exe["po_lines_skipped"] = sum(1 for ln in lines_all if ln.cur_ord == 0 and ln.q_ord > 0)
    sim.exe["po_lines_reduced"] = sum(1 for ln in lines_all if 0 < ln.cur_ord < ln.q_ord)
    ref = _reference(w, end)
    return {"region": region, "mode": mode, "families": sorted(families), "stores": store_ids,
            "m": {pol: {f"{s}|{_dd(t).isoformat()}": v for (s, t), v in mm.items()} for pol, mm in sim.m.items()},
            "sku_m": sim.sku_m, "rec": {f"{a}|{b}": n for (a, b), n in sim.rec.items()},
            "rec_day": {f"{_dd(d).isoformat()}|{a}": n for (d, a), n in sim.rec_day.items()},
            "censor_scale": censor_scale, "exe": dict(sim.exe), "close": tot, "n_issues": sim.n_issues, "reference": ref,
            "seconds": round(time.time() - t0, 1)}


def _reference(w: World, end: date) -> dict[str, Any]:
    """What the dataset itself says about the holdout (policy A as recorded): sold, expired, received, stockout hours,
    plus the backend's own lost-sales model (stockout_hours x same-weekday hourly rate x list price)."""
    from glazed_backend.metrics.losses import lost_sales_window
    from glazed_backend.metrics.types import DayRow
    out: dict[str, dict[str, float]] = {}
    for (store, sku), rs in w.rows.items():
        cost, price = float(w.prod[sku][0] or 0), float(w.prod[sku][1] or 0)
        dayrows = [DayRow(r[0], int(r[1] or 0), int(r[2] or 0), int(r[3] or 0), int(r[5] or 0), float(r[6] or 0.0)) for r in rs]
        lost = lost_sales_window(dayrows, price, float(w.store_info[store][1]), HOLD_START, end)["mid"]
        o = out.setdefault(store, {"sold": 0, "expired": 0, "received": 0, "waste_cost": 0.0, "stockout_hours": 0.0,
                                   "lost_sales_backend_usd": 0.0, "revenue": 0.0})
        for r in rs:
            if HOLD_START <= r[0] <= end:
                o["sold"] += int(r[2] or 0)
                o["expired"] += int(r[3] or 0)
                o["received"] += int(r[1] or 0)
                o["waste_cost"] += int(r[3] or 0) * cost
                o["stockout_hours"] += float(r[6] or 0.0)
                o["revenue"] += int(r[2] or 0) * w.price_at(store, sku, _od(r[0]))
        o["lost_sales_backend_usd"] += lost
    return out


def _regions() -> dict[str, list[str]]:
    con = duckdb.connect(DB, read_only=True)
    rows = con.execute("SELECT si.region, s.store_id FROM stores s JOIN sites si USING (site_id) ORDER BY 1, 2").fetchall()
    con.close()
    out: dict[str, list[str]] = defaultdict(list)
    for r, sid in rows:
        out[r].append(sid)
    return dict(out)


def stage_simulate(mode: str, only: list[str] | None, last: str | None, families: list[str], workers: int, tag: str,
                   censor_scale: float = 1.0) -> None:
    regs = _regions()
    todo = [(r, ids, mode, families, last, censor_scale) for r, ids in sorted(regs.items(), key=lambda kv: -len(kv[1]))
            if not only or r in only]
    CACHE.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with Pool(min(workers, len(todo))) as pool:
        for res in pool.imap_unordered(run_region, todo):
            path = CACHE / f"sim_{mode}_{tag}_{res['region'].replace(' ', '_')}.json"
            path.write_text(json.dumps(res))
            print(f"[simulate:{mode}:{tag}] {res['region']} done in {res['seconds']}s (total {time.time() - t0:.0f}s)", flush=True)


# =====================================================================================================================
# Stage 3: report (tables + charts + numbers); the narrative is rendered from these numbers by render_report()
# =====================================================================================================================
M = {"rev": 0, "cogs": 1, "lost": 2, "waste": 3, "purch": 4, "xfer": 5, "md_rev": 6, "sold_u": 7, "lost_u": 8, "waste_u": 9,
     "purch_u": 10, "md_u": 11, "md_margin": 12}


def _load(mode: str, tag: str) -> dict[str, Any]:
    files = sorted(CACHE.glob(f"sim_{mode}_{tag}_*.json"))
    if not files:
        raise SystemExit(f"no cached simulation for mode={mode} tag={tag}; run the simulate stage first")
    out: dict[str, Any] = {"m": {"A": {}, "B": {}}, "rec": defaultdict(int), "rec_day": defaultdict(int),
                           "exe": defaultdict(float), "close": {"A": [0, 0.0], "B": [0, 0.0], "start": [0, 0.0]},
                           "reference": {}, "stores": [], "n_issues": 0, "seconds": 0.0, "sku_m": {"A": {}, "B": {}}}
    for f in files:
        r = json.loads(f.read_text())
        for pol in "AB":
            out["m"][pol].update(r["m"][pol])
        for pol in "AB":
            for sku, v in (r.get("sku_m") or {}).get(pol, {}).items():
                acc = out["sku_m"][pol].setdefault(sku, [0.0] * 14)
                for i, x in enumerate(v):
                    acc[i] += x
        for k, v in r["rec"].items():
            out["rec"][k] += v
        for k, v in r["rec_day"].items():
            out["rec_day"][k] += v
        for k, v in r["exe"].items():
            out["exe"][k] += v
        for k in ("A", "B", "start"):
            out["close"][k][0] += r["close"][k]["units"]
            out["close"][k][1] += r["close"][k]["value"]
        out["reference"].update(r["reference"])
        out["stores"] += r["stores"]
        out["n_issues"] += r["n_issues"]
        out["seconds"] += r["seconds"]
    return out


def _agg(res: dict[str, Any], pol: str, key_fn) -> dict[Any, list[float]]:
    out: dict[Any, list[float]] = defaultdict(lambda: [0.0] * 14)
    for k, v in res["m"][pol].items():
        store, day = k.split("|")
        g = key_fn(store, day)
        a = out[g]
        for i, x in enumerate(v):
            a[i] += x
    return out


def _fin(v: list[float]) -> dict[str, float]:
    gm = v[0] - v[1]
    return {"ventas": v[0], "ventas_perdidas": v[2], "merma": v[3], "compras": v[4], "traslados": v[5], "margen_bruto": gm,
            "neto": gm - v[3] - v[5], "efectivo": v[0] - v[4] - v[5], "unid_vendidas": v[7], "unid_perdidas": v[8],
            "unid_merma": v[9], "unid_compradas": v[10], "unid_markdown": v[11], "aporte_markdown": v[6]}


def _pct(b: float, a: float) -> float | None:
    return None if abs(a) < 1e-9 else (b - a) / abs(a) * 100.0


def numbers(res: dict[str, Any]) -> dict[str, Any]:
    tot = {p: _fin(_agg(res, p, lambda s, d: "all")["all"]) for p in "AB"}
    by_store = {p: {s: _fin(v) for s, v in _agg(res, p, lambda s, d: s).items()} for p in "AB"}
    by_day = {p: {d: _fin(v) for d, v in sorted(_agg(res, p, lambda s, d: d).items())} for p in "AB"}
    by_week = {p: {w: _fin(v) for w, v in sorted(_agg(res, p, lambda s, d: _week(d)).items())} for p in "AB"}
    return {"total": tot, "by_store": by_store, "by_day": by_day, "by_week": by_week}


def _week(day: str) -> str:
    d = date.fromisoformat(day)
    return (d - timedelta(days=d.weekday())).isoformat()


def _bootstrap(by_store: dict[str, dict[str, dict[str, float]]], key: str = "neto", n: int = 4000) -> tuple[float, float]:
    import random
    rnd = random.Random(7)
    ids = sorted(by_store["A"])
    diffs = [by_store["B"][s][key] - by_store["A"][s][key] for s in ids]
    vals = sorted(sum(rnd.choice(diffs) for _ in ids) for _ in range(n))
    return vals[int(0.025 * n)], vals[int(0.975 * n)]


def _write_csv(path: Path, header: list[str], rows: list[list[Any]]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows:
            w.writerow([round(x, 2) if isinstance(x, float) else x for x in r])


def stage_report(tag: str, replay_tags: list[str]) -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    res = _load("closed", tag)
    nb = numbers(res)
    A, B = nb["total"]["A"], nb["total"]["B"]
    names = [("ventas", "Ventas"), ("ventas_perdidas", "Ventas perdidas (demanda no atendida x precio)"),
             ("merma", "Merma (unidades caducadas x costo)"), ("compras", "Compras (unidades recibidas x costo)"),
             ("traslados", "Costo de traslados"), ("margen_bruto", "Margen bruto (ventas - costo de lo vendido)"),
             ("neto", "Margen neto (margen bruto - merma - traslados)"),
             ("efectivo", "Flujo de caja (ventas - compras - traslados)")]
    rows = [[lab, A[k], B[k], B[k] - A[k], _pct(B[k], A[k])] for k, lab in names]
    _write_csv(OUT / "resumen_total.csv", ["concepto", "A_real", "B_sistema", "dif_usd", "dif_pct"], rows)
    stores = sorted(nb["by_store"]["A"])
    srows = []
    for s in stores:
        a, b = nb["by_store"]["A"][s], nb["by_store"]["B"][s]
        srows.append([s, a["ventas"], b["ventas"], a["ventas_perdidas"], b["ventas_perdidas"], a["merma"], b["merma"],
                      a["compras"], b["compras"], a["neto"], b["neto"], b["neto"] - a["neto"], _pct(b["neto"], a["neto"])])
    _write_csv(OUT / "por_tienda.csv", ["tienda", "ventas_A", "ventas_B", "perdidas_A", "perdidas_B", "merma_A", "merma_B",
                                        "compras_A", "compras_B", "neto_A", "neto_B", "mejora_neta_usd", "mejora_neta_pct"], srows)
    drows = []
    for dday in nb["by_day"]["A"]:
        a, b = nb["by_day"]["A"][dday], nb["by_day"]["B"][dday]
        drows.append([dday, a["ventas"], b["ventas"], a["ventas_perdidas"], b["ventas_perdidas"], a["merma"], b["merma"],
                      a["compras"], b["compras"], a["neto"], b["neto"], b["neto"] - a["neto"]])
    _write_csv(OUT / "serie_diaria.csv", ["fecha", "ventas_A", "ventas_B", "perdidas_A", "perdidas_B", "merma_A", "merma_B",
                                          "compras_A", "compras_B", "neto_A", "neto_B", "dif_neto"], drows)
    arows = sorted(((k.split("|")[0], k.split("|")[1], n) for k, n in res["rec"].items()), key=lambda r: (-r[2], r[0]))
    _write_csv(OUT / "acciones_recomendadas.csv", ["tipo_accion", "nivel", "recomendaciones"], [list(r) for r in arows])
    lo, hi = _bootstrap(nb["by_store"])
    # fidelity of A: simulated vs the dataset
    frows, ref_tot = [], defaultdict(float)
    for s in stores:
        r = res["reference"].get(s, {})
        a = nb["by_store"]["A"][s]
        frows.append([s, r.get("sold", 0), a["unid_vendidas"], r.get("expired", 0), a["unid_merma"], r.get("waste_cost", 0.0),
                      a["merma"], r.get("revenue", 0.0), a["ventas"], r.get("lost_sales_backend_usd", 0.0), a["ventas_perdidas"]])
        for k, v in r.items():
            ref_tot[k] += v
    _write_csv(OUT / "fidelidad_A.csv", ["tienda", "vendidas_dato", "vendidas_sim", "caducadas_dato", "caducadas_sim",
                                         "merma_usd_dato", "merma_usd_sim", "ventas_usd_dato", "ventas_usd_sim",
                                         "perdidas_usd_modelo_backend", "perdidas_usd_sim"], frows)
    sens: list[dict[str, Any]] = []
    for rt in replay_tags:
        try:
            rr = _load("replay", rt)
        except SystemExit:
            continue
        n2 = numbers(rr)["total"]
        sens.append({"tag": rt, "dif_neto": n2["B"]["neto"] - n2["A"]["neto"], "A_neto": n2["A"]["neto"],
                     "dif_merma": n2["B"]["merma"] - n2["A"]["merma"], "dif_perdidas": n2["B"]["ventas_perdidas"] - n2["A"]["ventas_perdidas"],
                     "dif_compras": n2["B"]["compras"] - n2["A"]["compras"], "dif_efectivo": n2["B"]["efectivo"] - n2["A"]["efectivo"]})
    if sens:
        _write_csv(OUT / "sensibilidad_repetido.csv", ["variante", "dif_neto_usd", "dif_merma_usd", "dif_perdidas_usd", "dif_compras_usd",
                                                       "dif_efectivo_usd"],
                   [[x["tag"], x["dif_neto"], x["dif_merma"], x["dif_perdidas"], x["dif_compras"], x["dif_efectivo"]] for x in sens])
    out = {"res": res, "nb": nb, "ci": (lo, hi), "sens": sens, "ref_tot": dict(ref_tot)}
    _charts(out)
    return out


def _charts(o: dict[str, Any]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    nb, res = o["nb"], o["res"]
    C_A, C_B, C_POS, C_NEG, C_GRID = "#7a7f8c", "#0f7b6c", "#0f7b6c", "#c0392b", "#e3e5ea"
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                         "grid.color": C_GRID, "axes.axisbelow": True, "figure.dpi": 130})
    days = list(nb["by_day"]["A"])
    dts = [date.fromisoformat(x) for x in days]
    money = matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}")
    # (a) cumulative net difference
    diff = [nb["by_day"]["B"][x]["neto"] - nb["by_day"]["A"][x]["neto"] for x in days]
    cum, acc = [], 0.0
    for v in diff:
        acc += v
        cum.append(acc)
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(dts, cum, color=C_B, lw=2.2)
    ax.fill_between(dts, 0, cum, color=C_B, alpha=0.12)
    ax.axhline(0, color="#444", lw=0.8)
    ax.yaxis.set_major_formatter(money)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.set_title("Diferencia acumulada de margen neto, sistema (B) menos real (A) - toda la cadena")
    ax.set_ylabel("USD acumulados")
    ax.annotate(f"${cum[-1]:,.0f}", (dts[-1], cum[-1]), textcoords="offset points", xytext=(-6, 8), ha="right", color=C_B,
                weight="bold")
    fig.tight_layout(); fig.savefig(OUT / "a_diferencia_acumulada.png"); plt.close(fig)
    # (b) daily waste and lost sales
    fig, axs = plt.subplots(2, 1, figsize=(9, 6.2), sharex=True)
    for ax, key, ttl in ((axs[0], "merma", "Merma diaria (USD al costo)"), (axs[1], "ventas_perdidas", "Ventas perdidas diarias (USD al precio)")):
        for pol, col, lab in (("A", C_A, "A: real (pedidos de las tiendas)"), ("B", C_B, "B: con recomendaciones del sistema")):
            ys = [nb["by_day"][pol][x][key] for x in days]
            ax.plot(dts, ys, color=col, lw=0.6, alpha=0.35)
            ma = [sum(ys[max(0, i - 6):i + 1]) / len(ys[max(0, i - 6):i + 1]) for i in range(len(ys))]
            ax.plot(dts, ma, color=col, lw=2.2, label=lab + " (media 7 dias)")
        ax.set_title(ttl); ax.yaxis.set_major_formatter(money)
    axs[0].legend(loc="upper right", frameon=False, fontsize=8.5)
    axs[1].xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    fig.tight_layout(); fig.savefig(OUT / "b_merma_y_ventas_perdidas.png"); plt.close(fig)
    # (c) by store
    st = sorted((s for s in nb["by_store"]["A"] if nb["by_store"]["A"][s]["ventas"] > 0),
                key=lambda s: nb["by_store"]["B"][s]["neto"] - nb["by_store"]["A"][s]["neto"])
    vals = [nb["by_store"]["B"][s]["neto"] - nb["by_store"]["A"][s]["neto"] for s in st]
    fig, ax = plt.subplots(figsize=(9, 7.6))
    ax.barh(st, vals, color=[C_POS if v >= 0 else C_NEG for v in vals])
    ax.axvline(0, color="#444", lw=0.8)
    ax.xaxis.set_major_formatter(money)
    ax.set_title("Mejora de margen neto por tienda en el periodo de prueba, B menos A (USD)")
    ax.tick_params(axis="y", labelsize=8)
    fig.tight_layout(); fig.savefig(OUT / "c_mejora_por_tienda.png"); plt.close(fig)
    # (d) recommended actions by type and tier
    types = defaultdict(lambda: defaultdict(int))
    for k, n in res["rec"].items():
        a, t = k.split("|")
        types[a][t] += n
    order = sorted(types, key=lambda a: -sum(types[a].values()))
    fig, ax = plt.subplots(figsize=(9, 4.4))
    left = [0] * len(order)
    for tier, col in (("N1", "#0f7b6c"), ("N2", "#4a7fb5"), ("N3", "#d98c2b")):
        vs = [types[a].get(tier, 0) for a in order]
        ax.barh(order, vs, left=left, color=col, label={"N1": "N1 auto", "N2": "N2 aprobacion", "N3": "N3 conversacion"}[tier])
        left = [l + v for l, v in zip(left, vs)]
    for i, l in enumerate(left):
        ax.text(l, i, f" {l:,}", va="center", fontsize=8.5)
    ax.invert_yaxis(); ax.legend(frameon=False, loc="lower right")
    ax.set_title("Acciones recomendadas por el sistema en el periodo (tienda x dia x SKU)")
    ax.set_xlabel("numero de recomendaciones")
    fig.tight_layout(); fig.savefig(OUT / "d_acciones_por_tipo.png"); plt.close(fig)
    # (e) sensitivity by action family (open-loop replay)
    if o["sens"]:
        lab = {"replay_all": "Todas", "replay_reduce": "Solo reducir/omitir pedidos", "replay_add": "Solo pedidos adicionales",
               "replay_calendar": "Solo ajuste por calendario", "replay_markdown": "Solo rebaja de caducos",
               "replay_transfer": "Solo traslados entre tiendas"}
        xs = [x for x in o["sens"] if x["tag"] in lab]
        fig, ax = plt.subplots(figsize=(9, 3.8))
        names = [lab[x["tag"]] for x in xs]; v = [x["dif_neto"] for x in xs]
        ax.barh(names, v, color=[C_POS if q >= 0 else C_NEG for q in v])
        ax.axvline(0, color="#444", lw=0.8); ax.invert_yaxis(); ax.xaxis.set_major_formatter(money)
        ax.set_title("Sensibilidad (repeticion en lazo abierto): mejora neta por familia de accion")
        fig.tight_layout(); fig.savefig(OUT / "e_sensibilidad_por_familia.png"); plt.close(fig)


def _usd(x: float, sign: bool = False) -> str:
    return (f"{x:+,.0f}" if sign else f"{x:,.0f}").replace(",", " ").replace("+", "+") + " USD"


def _p(x: float | None, sign: bool = True) -> str:
    return "n/a" if x is None else (f"{x:+.1f} %" if sign else f"{x:.1f} %")


def _supplier_breakdown(res: dict[str, Any]) -> list[dict[str, Any]]:
    """Per supplier: B - A for waste, lost sales and net margin, from the per-SKU accumulators."""
    con = duckdb.connect(DB, read_only=True)
    sup = {r[0]: (r[1], r[2], r[3]) for r in con.execute(
        "SELECT p.sku, p.supplier_id, s.supplier_name || ' (' || coalesce(s.delivery_days,'?') || ')', p.shelf_life_days"
        " FROM products p LEFT JOIN suppliers s USING (supplier_id)").fetchall()}
    con.close()
    out: dict[str, dict[str, Any]] = {}
    for sku in set(res["sku_m"]["A"]) | set(res["sku_m"]["B"]):
        a = res["sku_m"]["A"].get(sku, [0.0] * 14)
        b = res["sku_m"]["B"].get(sku, [0.0] * 14)
        sid, name, life = sup.get(sku, ("?", "?", None))
        o = out.setdefault(sid, {"supplier": sid, "name": name, "d_waste": 0.0, "d_lost": 0.0, "d_net": 0.0, "d_purch": 0.0,
                                 "waste_A": 0.0, "waste_B": 0.0})
        o["d_waste"] += b[3] - a[3]
        o["d_lost"] += b[2] - a[2]
        o["d_purch"] += b[4] - a[4]
        o["d_net"] += (b[0] - b[1] - b[3] - b[5]) - (a[0] - a[1] - a[3] - a[5])
        o["waste_A"] += a[3]
        o["waste_B"] += b[3]
    return sorted(out.values(), key=lambda o: -o["d_waste"])


def render_report(o: dict[str, Any], robust: dict[str, dict[str, Any]]) -> str:
    nb, res = o["nb"], o["res"]
    A, B = nb["total"]["A"], nb["total"]["B"]
    lo, hi = o["ci"]
    d = lambda k: B[k] - A[k]  # noqa: E731
    stores = [s for s in nb["by_store"]["A"] if nb["by_store"]["A"][s]["ventas"] > 0]
    imp = {s: nb["by_store"]["B"][s]["neto"] - nb["by_store"]["A"][s]["neto"] for s in stores}
    order = sorted(stores, key=lambda s: -imp[s])
    worse = [s for s in order if imp[s] < 0]
    wk = nb["by_week"]
    weeks = list(wk["A"])
    md = B["aporte_markdown"]
    exe = res["exe"]
    ref = o["ref_tot"]
    close = res["close"]
    tot_rec = sum(res["rec"].values())
    fam_names = {"replay_reduce": "Solo reducir / omitir pedidos", "replay_add": "Solo pedidos adicionales (riesgo de faltante)",
                 "replay_calendar": "Solo ajuste por calendario", "replay_markdown": "Solo rebaja de caducos",
                 "replay_transfer": "Solo traslados entre tiendas", "replay_all": "Todas juntas"}
    L: list[str] = []
    w = L.append
    w("# Contrafactual del periodo de prueba: tiendas reales (A) contra sistema (B)\n")
    w(f"Periodo de prueba: **{HOLD_START} a {HOLD_END}** (el ultimo 20 % del dataset; el corte del 80 % es {CUT}). "
      f"{len(stores)} tiendas con operacion, {len(nb['by_day']['A'])} dias. Todo en USD. Version 1.\n")
    pts = sorted([(1.0, d("neto"))] + [({"cs78": 0.78, "cs50": 0.5, "cs00": 0.0}[k], robust[k]["B"]["neto"] - robust[k]["A"]["neto"])
                                       for k in robust])
    be = next((x0 + (0 - y0) * (x1 - x0) / (y1 - y0) for (x0, y0), (x1, y1) in zip(pts, pts[1:]) if y0 < 0 <= y1), None)
    sb0 = _supplier_breakdown(res) if res["sku_m"]["A"] else []
    top = max(sb0, key=lambda o_: o_["d_net"]) if sb0 else None
    w("## 1. Resultado\n")
    w(f"Aplicando la opcion recomendada de cada issue que requiere aprobacion (aprobada en automatico), con el estimado de demanda "
      f"censurada del backend completo, el margen neto de la cadena pasa de **{_usd(A['neto'])}** (A, lo que hicieron las tiendas) a "
      f"**{_usd(B['neto'])}** (B, con el sistema): **{_usd(d('neto'), True)} ({_p(_pct(B['neto'], A['neto']))})**. "
      f"Intervalo al 95 % por remuestreo de tiendas: {_usd(lo, True)} a {_usd(hi, True)}.\n")
    w("**Advertencia: la cifra depende del supuesto de demanda en dias con quiebre.** "
      + (f"Si solo se cree el 78 % de esa correccion (el nivel consistente con el modelo de ventas perdidas del propio backend) la mejora es "
         f"{_usd(pts[[x for x, _ in pts].index(0.78)][1], True)}; " if 0.78 in [x for x, _ in pts] else "")
      + (f"con 50 % es {_usd(pts[[x for x, _ in pts].index(0.5)][1], True)}; con 0 % (cota inferior: B no puede vender lo que A no registro) "
         f"{_usd(pts[0][1], True)}. " if 0.5 in [x for x, _ in pts] else "")
      + (f"El punto de equilibrio esta cerca de creer **{be * 100:.0f} %** de la correccion. " if be is not None else "")
      + (f"Ademas la mejora esta concentrada: el proveedor {top['supplier']} ({top['name']}) aporta {_usd(top['d_net'], True)} "
         f"({top['d_net'] / max(d('neto'), 1) * 100:.0f} % del total). " if top else "")
      + "Ver secciones 3 y 7.\n")
    w("| Concepto | A real | B sistema | Dif. USD | Dif. % |\n|---|---:|---:|---:|---:|")
    for k, lab in (("ventas", "Ventas"), ("ventas_perdidas", "Ventas perdidas"), ("merma", "Merma (al costo)"),
                   ("compras", "Compras (al costo)"), ("traslados", "Costo de traslados"), ("margen_bruto", "Margen bruto"),
                   ("neto", "**Margen neto**"), ("efectivo", "Flujo de caja")):
        w(f"| {lab} | {A[k]:,.0f} | {B[k]:,.0f} | {d(k):+,.0f} | {_p(_pct(B[k], A[k])) if A[k] else 'n/a'} |")
    w("")
    w("Margen neto = ventas - costo de lo vendido - merma - traslados. Ventas perdidas = demanda no atendida por precio "
      "(no entra en el margen: es el dinero que no se vendio). Flujo de caja = ventas - compras - traslados "
      "(penaliza el inventario que B termina acumulando).\n")
    w("Lectura honesta: B vende mas y pierde menos ventas, **pero tira mas producto** (merma "
      f"{_p(_pct(B['merma'], A['merma']))}) y compra mas ({_p(_pct(B['compras'], A['compras']))}). La mejora viene de "
      f"atender demanda que A perdia por faltantes, no de gastar menos. "
      f"B cierra el periodo con {close['B'][0]:,.0f} unidades en inventario ({close['B'][1]:,.0f} USD al costo) contra "
      f"{close['A'][0]:,.0f} ({close['A'][1]:,.0f} USD) de A.\n")
    w("![Diferencia acumulada](a_diferencia_acumulada.png)\n")
    w("## 2. Metodo\n")
    w(f"- **A (linea base)**: lo que el dataset registra. Las recepciones reales de cada tienda y SKU; demanda real de `sales_daily` / "
      f"`inventory_daily`. Se simula con el mismo motor que B para que la unica diferencia sea la politica. "
      f"Ajuste del motor contra el dato: unidades vendidas {A['unid_vendidas']:,.0f} simuladas contra {ref['sold']:,.0f} reales "
      f"({_pct(A['unid_vendidas'], ref['sold']):+.1f} %), caducadas {A['unid_merma']:,.0f} contra {ref['expired']:,.0f} "
      f"({_pct(A['unid_merma'], ref['expired']):+.1f} %), merma {A['merma']:,.0f} contra {ref['waste_cost']:,.0f} USD, "
      f"ventas {A['ventas']:,.0f} contra {ref['revenue']:,.0f} USD (`fidelidad_A.csv`).")
    w(f"- **B (sistema)**: lazo cerrado. Cada dia d, para cada tienda abierta, se corre el backend determinista en proceso "
      f"(`DuckDBMetrics.issues`, as_of = d) y se toma la opcion recomendada de cada issue. Se aprueban todas las que no son "
      f"`do_nothing` ni N0 (N1, N2 y N3; solo {sum(n for k, n in res['rec'].items() if k.endswith('|N1'))} fueron N1). "
      f"Las decisiones se toman del cierre del {CUT} al {HOLD_END - timedelta(days=1)}: {res['n_issues']:,} issues, "
      f"{tot_rec:,} recomendaciones accionables. El backend ve **el inventario y los pedidos de B**, no los de A: "
      f"tablas temporales privadas de la sesion sustituyen `inventory_daily` y `purchase_orders` con las filas que B genero hasta d "
      f"(el script verifica cada dia que no existe ninguna fila posterior a d). Asi lo que se recomienda manana refleja lo que se hizo hoy.")
    w("- **Frecuencia**: decision **diaria para todas las tiendas** (sin muestreo). La calibracion de confianza del backend "
      "(solo cambia la etiqueta N1/N2, no la opcion recomendada) se refresca los lunes con datos hasta ese lunes.")
    w("- **Como se aplica cada accion**: `skip_order` y `adjust_order_qty` de reduccion cambian el siguiente pedido real de ese SKU "
      f"(el del dia d+1) a la cantidad recomendada, redondeada a multiplos de caja; el surtido se escala por la tasa de surtido real de ese pedido. "
      f"`place_order` y `adjust_order_qty` de faltante agregan un pedido que llega en la primera entrega valida del proveedor "
      f"(plazo medio historico, dias de entrega del proveedor). `transfer_stock` mueve las unidades mas viejas aun vendibles al "
      f"llegar (1 dia mismo sitio, 2 dias distinto sitio), con el costo fijo + por unidad del backend. `markdown_end_of_day` rebaja 30 % "
      f"las unidades que de otro modo caducarian ese dia. `calendar_uplift` escala los pedidos de los departamentos afectados. "
      f"`data_fix_task` no tiene efecto de inventario (se cuenta pero no se simula).")
    w("- **Inventario**: lotes FIFO; un lote recibido el dia r se vende hasta r + vida util - 1 y caduca al cierre (misma convencion que "
      "el backend; reproduce la caducidad real con +2 %). Inventario inicial = cierre del 19 de julio, repartido en los recibos mas nuevos.")
    w(f"- **Demanda real**: ventas reales. En dias con quiebre la demanda se estima con la correccion de demanda censurada del backend "
      f"(`metrics.demand.uncensor`), **igual para A y B**.")
    w("- **Dinero**: ventas = unidades vendidas x precio neto real del dia (`sales_daily`); costo = `products.unit_cost`.\n")
    w("## 3. Merma y ventas perdidas\n")
    w("![Merma y ventas perdidas diarias](b_merma_y_ventas_perdidas.png)\n")
    sb = _supplier_breakdown(res) if res["sku_m"]["A"] else []
    wdw: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0, 0])
    for dday in nb["by_day"]["A"]:
        k_ = date.fromisoformat(dday).weekday()
        wdw[k_][0] += nb["by_day"]["A"][dday]["merma"]
        wdw[k_][1] += nb["by_day"]["B"][dday]["merma"]
        wdw[k_][2] += 1
    dnames = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    wk_top = max(wdw, key=lambda k_: wdw[k_][1] / wdw[k_][2])
    w(f"La merma de B es {_p(_pct(B['merma'], A['merma']))} respecto de A y tiene picos semanales: el dia de mayor merma de B es el "
      f"{dnames[wk_top]} ({wdw[wk_top][1] / wdw[wk_top][2]:,.0f} USD por dia contra {wdw[wk_top][0] / wdw[wk_top][2]:,.0f} en A). "
      f"Es consistente con SUP03 (26 SKU con 3 dias de vida util y entrega martes y viernes): un pedido mas grande el martes se vende "
      f"miercoles y jueves y lo que sobra caduca el jueves. Las ventas perdidas de B cambian {_pct(B['ventas_perdidas'], A['ventas_perdidas']):+.0f} %.\n")
    if sb:
        w("Por proveedor (B menos A, USD):\n")
        w("| Proveedor (dias de entrega) | Merma | Ventas perdidas | Compras | Margen neto |\n|---|---:|---:|---:|---:|")
        for o_ in sb:
            w(f"| {o_['supplier']} {o_['name']} | {o_['d_waste']:+,.0f} | {o_['d_lost']:+,.0f} | {o_['d_purch']:+,.0f} | {o_['d_net']:+,.0f} |")
        w("")
    w("## 4. Por tienda\n")
    w("![Mejora por tienda](c_mejora_por_tienda.png)\n")
    w("Mejores 5 tiendas: " + "; ".join(f"{s} ({imp[s]:+,.0f} USD, {_p(_pct(nb['by_store']['B'][s]['neto'], nb['by_store']['A'][s]['neto']))})" for s in order[:5]) + ".\n")
    w("Peores 5 tiendas: " + "; ".join(f"{s} ({imp[s]:+,.0f} USD, {_p(_pct(nb['by_store']['B'][s]['neto'], nb['by_store']['A'][s]['neto']))})" for s in order[-5:][::-1]) + ".\n")
    w(f"**B es peor en {len(worse)} de {len(stores)} tiendas** ({', '.join(worse)}): "
      f"{_usd(sum(imp[s] for s in worse), True)} en conjunto. Tabla completa en `por_tienda.csv`.\n")
    w("## 5. Que acciones recomienda\n")
    w("![Acciones](d_acciones_por_tipo.png)\n")
    w(f"En el periodo B ejecuto {exe['po_lines_skipped']:,.0f} lineas de pedido omitidas y {exe['po_lines_reduced']:,.0f} reducidas "
      f"({exe['po_units_B_removed']:,.0f} de {exe['po_units_A']:,.0f} unidades pedidas por A, "
      f"{exe['po_units_B_removed'] / max(exe['po_units_A'], 1) * 100:.0f} %), {exe['add_orders']:,.0f} pedidos adicionales "
      f"({exe['add_units']:,.0f} unidades), {exe['transfers']:,.0f} traslados ({exe['transfer_units']:,.0f} unidades, "
      f"{exe['transfer_cost_usd']:,.0f} USD) y rebajas sobre {exe['markdown_units']:,.0f} unidades.\n")
    w("## 6. Estabilidad en el tiempo\n")
    w("| Semana | Mejora neta | Ventas | Merma | Ventas perdidas | Compras |\n|---|---:|---:|---:|---:|---:|")
    for wkk in weeks:
        a, b = wk["A"][wkk], wk["B"][wkk]
        w(f"| {wkk} | {b['neto'] - a['neto']:+,.0f} | {b['ventas'] - a['ventas']:+,.0f} | {b['merma'] - a['merma']:+,.0f} | "
          f"{b['ventas_perdidas'] - a['ventas_perdidas']:+,.0f} | {b['compras'] - a['compras']:+,.0f} |")
    w("\nLa mejora semanal baja con el tiempo (primeras semanas contra ultimas): al principio B repone los faltantes acumulados y despues "
      "la merma extra se estabiliza. La semana del 28 de septiembre tiene solo 3 dias.\n")
    w("## 7. Sensibilidad y robustez\n")
    if robust:
        w("**Demanda en dias con quiebre.** El mayor supuesto: cuanta de la demanda censurada es real. Se repitio el lazo cerrado completo "
          "creyendo solo una parte de la correccion del backend:\n")
        w("| Supuesto | Mejora neta B - A | Ventas perdidas A | Ventas perdidas B | Merma B - A |\n|---|---:|---:|---:|---:|")
        w(f"| 100 % de la correccion (cifra principal) | {d('neto'):+,.0f} | {A['ventas_perdidas']:,.0f} | {B['ventas_perdidas']:,.0f} | {d('merma'):+,.0f} |")
        for k, lab in (("cs78", "78 % (consistente con el modelo de ventas perdidas del backend)"), ("cs50", "50 %"),
                       ("cs00", "0 % (solo ventas observadas; cota inferior)")):
            if k in robust:
                ra, rb = robust[k]["A"], robust[k]["B"]
                w(f"| {lab} | {rb['neto'] - ra['neto']:+,.0f} | {ra['ventas_perdidas']:,.0f} | {rb['ventas_perdidas']:,.0f} | {rb['merma'] - ra['merma']:+,.0f} |")
        w("")
        w(f"El modelo de ventas perdidas del backend (horas de quiebre x tasa horaria de dias sin quiebre x precio de lista) estima "
          f"{ref['lost_sales_backend_usd']:,.0f} USD perdidos en A; el estimado de demanda censurada usado aqui da {A['ventas_perdidas']:,.0f} USD "
          f"({ref['lost_sales_backend_usd'] / max(A['ventas_perdidas'], 1) * 100:.0f} %). Es la razon del escenario de 78 %.\n")
    w(f"**Rebajas (elasticidad asumida).** Aportan {md:,.0f} USD de B ({exe['markdown_units']:,.0f} unidades, recuperacion 50 % a -30 %, "
      f"supuesto propio del backend sin historial). Sin rebajas la mejora seria {d('neto') - md:+,.0f} USD.\n")
    if o["sens"]:
        w("**Repeticion en lazo abierto (solo informativa).** Aplicar las decisiones del mundo A (sin que el sistema vea sus efectos) con "
          "bloqueos para no duplicar una senal persistente da otra cifra, porque una senal que sigue encendida en A llevaria a omitir pedidos "
          "dia tras dia:\n")
        w("![Sensibilidad por familia](e_sensibilidad_por_familia.png)\n")
        w("| Variante | Mejora neta | Merma | Ventas perdidas | Compras |\n|---|---:|---:|---:|---:|")
        for x in o["sens"]:
            w(f"| {fam_names.get(x['tag'], x['tag'])} | {x['dif_neto']:+,.0f} | {x['dif_merma']:+,.0f} | {x['dif_perdidas']:+,.0f} | {x['dif_compras']:+,.0f} |")
        w("\nLectura: en lazo abierto omitir pedidos cuesta ventas porque el sistema no puede dejar de recomendar omitir; el lazo cerrado corrige "
          "eso porque cada dia ve el inventario que dejo. Es el motivo por el que la cifra principal es la de lazo cerrado.\n")
    w("## 8. Supuestos y limites\n")
    for t in (
        "Es un periodo de **verano** (julio a septiembre): la estacionalidad, el calendario y los eventos pueden no representar el resto del anio.",
        "La demanda de los dias con quiebre es **estimada** (demanda censurada del backend, tope p90). La mayor parte de la mejora viene de "
        "vender lo que A perdio por faltantes, asi que depende de ese estimado (ver sensibilidad).",
        "Las recomendaciones se aplican **sin criterio del gerente**: ni rechazos, ni ajustes, ni retrasos en la aprobacion. Un gerente real "
        "descartaria algunas (por ejemplo omitir pedidos de SKU con promociones locales).",
        "No se modela el **minimo de compra por proveedor** (MOV), ni que el proveedor acepte menos de una caja; las cantidades se redondean a cajas.",
        "Los pedidos adicionales llegan completos y en la primera entrega valida segun el plazo medio historico; no se simula retraso ni surtido parcial.",
        "El mundo B conserva la secuencia de pedidos reales de cada tienda (cuando y para que SKU piden); solo cambian cantidades o se agregan pedidos.",
        "Los traslados usan el costo y plazo supuestos del backend; las rebajas, la elasticidad supuesta del backend.",
        "Mermas por daño (`damaged_qty`, menos del 0.5 % de la merma) se aplican igual en A y B. No se contabiliza el valor del inventario final "
        "(se informa aparte) ni el costo de oportunidad del capital.",
        "No hay efecto de precio ni de elasticidad en el resto del surtido; las promociones, el personal y las correcciones de datos "
        "(`data_fix_task`, `run_promo`, turnos) no se simulan.",
        "El intervalo de confianza solo refleja la variacion entre tiendas, no la incertidumbre de los supuestos anteriores.",
    ):
        w(f"- {t}")
    w("\n## 9. Archivos y como reproducir\n")
    w("- Script: `backend/scripts/holdout_counterfactual.py` (etapas `decide`, `simulate`, `report`). Tablas: `resumen_total.csv`, "
      "`por_tienda.csv`, `serie_diaria.csv`, `acciones_recomendadas.csv`, `fidelidad_A.csv`, `sensibilidad_repetido.csv`.")
    w("- Lectura de solo lectura de `Dataset/clean/glazed.duckdb`; no se toca Postgres ni los contenedores.")
    w(f"- Calculo: {res['seconds'] / 60:.0f} minutos de CPU sumados en 8 regiones (corre en paralelo por region porque los traslados solo ocurren dentro de una region).")
    w("")
    return "\n".join(L)


def render_pdf(md_path: Path, pdf_path: Path, fonts: str) -> int:
    """Markdown -> PDF with xhtml2pdf and DejaVu fonts (needs `markdown` and `xhtml2pdf` importable)."""
    import re
    import markdown
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from xhtml2pdf import default, pisa
    for name, f in (("Dv", "DejaVuSans.ttf"), ("DvB", "DejaVuSans-Bold.ttf"), ("DvMono", "DejaVuSansMono.ttf")):
        pdfmetrics.registerFont(TTFont(name, os.path.join(fonts, f)))
    for face in (0, 1):
        for it in (0, 1):
            addMapping("Dv", face, it, "DvB" if face else "Dv")
            addMapping("DvMono", face, it, "DvMono")
    default.DEFAULT_FONT["dv"] = "Dv"
    default.DEFAULT_FONT["dvmono"] = "DvMono"
    body = markdown.markdown(md_path.read_text(encoding="utf-8"), extensions=["tables", "fenced_code", "sane_lists"])
    body = re.sub(r'<img alt="([^"]*)" src="([^"]+)"\s*/?>', lambda m: f'<img alt="{m.group(1)}" src="{m.group(2)}" width="480" />', body)
    css = """
@page { size: letter; margin: 1.6cm 1.4cm; @frame footer { -pdf-frame-content: foot; bottom: 0.6cm; height: 0.6cm; left: 1.4cm; right: 1.4cm; } }
body { font-family: Dv; font-size: 9.2pt; line-height: 1.38; color: #1d1d27; }
h1 { font-size: 16pt; color: #1f3a4d; border-bottom: 2px solid #0f7b6c; padding-bottom: 4px; }
h2 { font-size: 12.5pt; color: #1f3a4d; margin-top: 12px; border-bottom: 1px solid #cccccc; padding-bottom: 2px; -pdf-keep-with-next: true; }
table { width: 100%; margin: 4px 0 8px 0; font-size: 8pt; }
th { background-color: #1f3a4d; color: #ffffff; text-align: left; padding: 3px; border: 1px solid #1f3a4d; }
td { border: 1px solid #cfcfd8; padding: 3px; vertical-align: top; }
code { font-family: DvMono; font-size: 8pt; color: #1f3a4d; }
li { margin-bottom: 2px; }
#foot { text-align: right; font-size: 7.5pt; color: #888888; }
"""
    html = (f"<html><head><meta charset='utf-8'><style>{css}</style></head><body><div id='foot'>Contrafactual del periodo de prueba · "
            f"pagina <pdf:pagenumber/> de <pdf:pagecount/></div>{body}</body></html>")
    with open(pdf_path, "wb") as fh:
        r = pisa.CreatePDF(html, dest=fh, encoding="utf-8", path=str(md_path.parent) + os.sep)
    return int(r.err)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("decide")
    d.add_argument("--workers", type=int, default=5)
    d.add_argument("--stores", default="")
    sm = sub.add_parser("simulate")
    sm.add_argument("--mode", choices=["closed", "replay"], default="closed")
    sm.add_argument("--regions", default="")
    sm.add_argument("--last", default="", help="stop after this holdout day (smoke test)")
    sm.add_argument("--families", default=",".join(FAMILIES))
    sm.add_argument("--workers", type=int, default=5)
    sm.add_argument("--tag", default="all")
    sm.add_argument("--censor-scale", type=float, default=1.0,
                    help="share of the stockout-day demand correction that is believed (1 = backend estimate, 0 = none)")
    rp = sub.add_parser("report")
    rp.add_argument("--tag", default="all")
    rp.add_argument("--fonts", default="", help="directory with DejaVuSans*.ttf (needed for --pdf)")
    rp.add_argument("--pdf", action="store_true")
    a = ap.parse_args()
    if a.cmd == "decide":
        stage_decide(a.workers, [s for s in a.stores.split(",") if s] or None)
    if a.cmd == "simulate":
        stage_simulate(a.mode, [r for r in a.regions.split(",") if r] or None, a.last or None,
                       [f for f in a.families.split(",") if f], a.workers, a.tag, a.censor_scale)
    if a.cmd == "report":
        o = stage_report(a.tag, ["replay_all", "replay_reduce", "replay_add", "replay_calendar", "replay_markdown", "replay_transfer"])
        robust = {}
        for rt in ("cs78", "cs50", "cs00"):
            try:
                robust[rt] = numbers(_load("closed", rt))["total"]
            except SystemExit:
                pass
        md_path = OUT / "holdout-counterfactual-v1.md"
        md_path.write_text(render_report(o, robust), encoding="utf-8")
        print(f"wrote {md_path}")
        if a.pdf:
            err = render_pdf(md_path, OUT / "holdout-counterfactual-v1.pdf", a.fonts)
            print("pdf errors:", err)
    return 0


if __name__ == "__main__":
    sys.exit(main())
