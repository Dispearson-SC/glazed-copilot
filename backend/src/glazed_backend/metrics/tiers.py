"""Autonomy tier computed in code from the option's numbers; the LLM cannot choose it."""
from __future__ import annotations

from .types import Config

N1_ACTIONS = {"place_order", "adjust_order_qty"}
N3_ACTIONS = {"transfer_stock", "shift_staff_hours"}
CLOSE_OPTIONS = 0.10  # |net - runner_up| below 10% of the larger net
ADJUST_BAND = 0.15


def _n1_failures(o: dict, cfg: Config, plan_qty: float | None, case_size: int) -> list[str]:
    conf = o.get("confidence") or {}
    out = []
    if o["action_type"] not in N1_ACTIONS:
        out.append(f"{o['action_type']} is not an auto-executable action")
    if conf.get("score", 0.0) < cfg.n1_min_score:
        out.append(f"calibrated confidence {conf.get('score', 0.0):.2f} < {cfg.n1_min_score:.2f}")
    if conf.get("n_backtest", 0) < cfg.n1_min_backtest:
        out.append(f"only {conf.get('n_backtest', 0)} backtest cases (< {cfg.n1_min_backtest})")
    if o["cost_usd"] > cfg.store_threshold_usd:
        out.append(f"cost ${o['cost_usd']:.2f} exceeds the store threshold ${cfg.store_threshold_usd:.2f}")
    qty = (o.get("params") or {}).get("qty")
    if o["action_type"] in N1_ACTIONS and plan_qty is not None and qty is not None:
        band = max(ADJUST_BAND * plan_qty, float(case_size))
        if abs(qty - plan_qty) > band:
            out.append(f"quantity {qty} is outside the +-15% / 1-case band around the plan ({plan_qty:g})")
    return out


def classify(o: dict, runner_up_net: float | None, cfg: Config, plan_qty: float | None = None,
             case_size: int = 1) -> tuple[str, list[str]]:
    """(tier, tier_reasons). runner_up_net is the net of the second-best non-do_nothing option, if any."""
    action, net = o["action_type"], o["net_usd_mid"]
    if action == "do_nothing":
        return "N0", ["do_nothing: nothing to execute; record as healthy state"]
    if net <= 0:
        return "N0", ["do_nothing wins: net benefit is not positive"]
    if net < cfg.noise_floor_usd:
        return "N0", [f"net ${net:.2f} is below the noise floor ${cfg.noise_floor_usd:.2f}"]
    close = runner_up_net is not None and abs(net - runner_up_net) < CLOSE_OPTIONS * max(abs(net), abs(runner_up_net))
    params = o.get("params") or {}
    if action in N3_ACTIONS:
        return "N3", [f"{action} is high impact or irreversible: needs a conversation"]
    if action == "run_promo" and (params.get("discount_pct", 0) >= 20 or o["cost_usd"] > cfg.store_threshold_usd):
        return "N3", ["large promotion: needs a conversation"]
    if close:
        return "N3", ["options are close (net differs by <10%): needs a conversation"]
    if action == "markdown_end_of_day":
        return "N2", ["assumed elasticity: no discount history or hourly data, so autonomy is capped at N2"]
    if action == "activate_promo":
        return "N2", ["promotion lift is estimated from a handful of past promotions: needs the manager's approval (N2)"]
    fails = _n1_failures(o, cfg, plan_qty, case_size)
    if fails:
        return "N2", ["proposal: " + "; ".join(fails)]
    return "N1", ["calibrated confidence and backtest sample meet the N1 bar", "cost within store threshold",
                  "reversible action within +-15% of the plan", "clear margin over the next option"]
