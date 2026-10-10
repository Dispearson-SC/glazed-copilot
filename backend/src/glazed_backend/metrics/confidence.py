"""Confidence by backtest replay: the share of past decisions whose net outcome was positive."""
from __future__ import annotations

from dataclasses import dataclass

from .types import Config, DayRow

CAP_UNCALIBRATED = 0.3


@dataclass(frozen=True)
class Calibration:
    score: float  # share of replays with net > 0
    n_backtest: int
    effect_mean_usd: float
    method: str = "backtest_replay"


def realized_add_net(window: list[DayRow], demand: dict, qty: float, price: float, unit_cost: float,
                     perishable: bool) -> float:
    """Net USD of having received `qty` more units at the start of the outcome window.

    Extra sales are bounded by demand that was actually unmet (estimated demand minus sold). Leftover units
    are waste for perishables (lost cost) and stay as inventory at cost otherwise."""
    unmet = sum(max(0.0, demand.get(r.date, float(r.sold)) - r.sold) for r in window)
    extra = min(float(qty), unmet)
    salvage = 0.0 if perishable else unit_cost
    return price * extra - unit_cost * qty + salvage * (qty - extra)


def realized_reduce_net(window: list[DayRow], delta: float, price: float, unit_cost: float) -> float:
    """Net USD of having received `delta` fewer units: cost saved minus the sales that would have used them.

    Units that actually expired (or are still on the shelf at the end) were not needed."""
    expired = float(sum(r.expired for r in window))
    leftover = float(window[-1].closing) if window else 0.0
    sold_lost = max(0.0, delta - expired - leftover)
    return unit_cost * delta - price * sold_lost


def score_replays(nets: list[float], cfg: Config) -> Calibration:
    if not nets:
        return Calibration(0.0, 0, 0.0, "uncalibrated")
    return Calibration(sum(1 for n in nets if n > 0) / len(nets), len(nets), sum(nets) / len(nets))


def confidence_for(calib: Calibration | None, option_net: float, cfg: Config) -> dict:
    """Option confidence {score, n_backtest, method, ...}. Uncalibrated actions and effects under the noise
    floor are capped at 0.3 (the system then prefers not acting)."""
    if calib is None or calib.n_backtest == 0:
        return {"score": CAP_UNCALIBRATED, "n_backtest": 0, "method": "uncalibrated", "noise_capped": False,
                "effect_mean_usd": None, "noise_floor_usd": cfg.noise_floor_usd}
    capped = abs(option_net) < cfg.noise_floor_usd or abs(calib.effect_mean_usd) < cfg.noise_floor_usd
    return {"score": min(calib.score, CAP_UNCALIBRATED) if capped else round(calib.score, 4),
            "n_backtest": calib.n_backtest, "method": calib.method, "noise_capped": capped,
            "effect_mean_usd": round(calib.effect_mean_usd, 2), "noise_floor_usd": cfg.noise_floor_usd}


def line_confidence(calib: Calibration | None, option_net: float, cfg: Config) -> dict:
    """The confidence of an order-plan line: {score, calibrated} (+ the replay count and whether the noise floor capped it)."""
    c = confidence_for(calib, option_net, cfg)
    return {"score": c["score"], "calibrated": c["n_backtest"] > 0, "n_backtest": c["n_backtest"],
            "noise_capped": c["noise_capped"]}
