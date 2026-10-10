"""Backtest replay: apply each option rule at past days t (data <= t only) and score the outcome at t+1..t+k <= as_of."""
from __future__ import annotations

from datetime import date, timedelta

from .confidence import Calibration, realized_add_net, realized_reduce_net, score_replays
from .demand import uncensor
from .detect import expiring_candidate, overstock_candidate, stockout_candidate
from .inventory import is_short_life
from .plan import recommended_qty, service_for
from .policy import delivery_window
from .snapshot import StoreSnapshot
from .types import Config

OUTCOME_DAYS = 3


def _window(rows: dict[date, object], start: date, days: int, ref: date) -> list:
    return [rows[start + timedelta(days=i)] for i in range(days)
            if start + timedelta(days=i) <= ref and (start + timedelta(days=i)) in rows]


def calibrate(snap: StoreSnapshot, ref: date, cfg: Config) -> dict[tuple[str, str], Calibration]:
    """Score (kind, action_type) rules by replay over the cfg.backtest_days days before ref.

    score = share of replays whose realized net was positive. Not isotonic-calibrated (documented limit)."""
    nets: dict[tuple[str, str], list[float]] = {}
    for sku, prod in snap.products.items():
        all_rows = snap.rows.get(sku, [])
        if not all_rows:
            continue
        by_date = {r.date: r for r in all_rows}
        demand = uncensor(all_rows, snap.store.open_hours).demand
        perishable = is_short_life(prod.shelf_life_days)
        for k in range(1, cfg.backtest_days + 1):
            t = ref - timedelta(days=k)
            state = snap.state_at(sku, t)
            if state is None:
                continue
            line = stockout_candidate(state, cfg)
            if line:
                d1, _ = delivery_window(state)
                win = _window(by_date, d1, OUTCOME_DAYS, ref)
                if win and d1 <= ref:
                    plan = line["qty"]
                    nets.setdefault(("stockout_risk", "place_order"), []).append(
                        realized_add_net(win, demand, plan, prod.price, prod.unit_cost, perishable))
                    for svc in (0.60, 0.85):
                        q = recommended_qty(state, svc)[1]
                        if q > 0 and q != plan:
                            nets.setdefault(("stockout_risk", "adjust_order_qty"), []).append(
                                realized_add_net(win, demand, q, prod.price, prod.unit_cost, perishable))
            kinds = []
            if overstock_candidate(state, cfg):
                kinds.append("overstock_waste")
            elif expiring_candidate(state):
                kinds.append("expiring")
            if kinds:
                win = _window(by_date, t + timedelta(days=1), OUTCOME_DAYS, ref)
                if len(win) == OUTCOME_DAYS:
                    rec, q_plan = recommended_qty(state, service_for(state, cfg))
                    q_typ = snap.typical_order_qty(sku, t)
                    q_typ = float(q_typ) if q_typ is not None else sum(r.received for r in state.rows) / len(state.rows)
                    for kind in kinds:
                        if kind == "overstock_waste" and q_typ > q_plan:
                            nets.setdefault((kind, "adjust_order_qty"), []).append(
                                realized_reduce_net(win, q_typ - q_plan, prod.price, prod.unit_cost))
                        if q_typ > 0:
                            nets.setdefault((kind, "skip_order"), []).append(
                                realized_reduce_net(win, q_typ, prod.price, prod.unit_cost))
    return {key: score_replays(v, cfg) for key, v in nets.items()}
