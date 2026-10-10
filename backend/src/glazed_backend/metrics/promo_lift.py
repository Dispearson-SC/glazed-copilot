"""Promotion lift estimated from the dataset's own promotion history, with honest uncertainty. No I/O.

Each finished promotion gives one difference-in-differences observation (units of the promoted scope relative to a
control group of products never on promo, window vs. +-28 days around it). Observations are chain-wide and few (12
usable promos), and the never-run PR013 shows the method drifts by about +-10 points, so every observation carries that
noise floor as its standard error. Lift is modelled as proportional to the discount depth (uplift = e x discount%),
estimated per scope (department / category) and shrunk toward the chain-wide elasticity, because one promo per scope
says little. The result is a mid value with an 80% band, a confidence label, and nothing when the scope has no history
(the caller then keeps its assumption)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt

NOISE_FLOOR_PCT = 10.0   # +-10 points: PR013 placebo
PRIOR_SD = 0.30          # between-scope sd of the elasticity (uplift points per discount point) around the chain mean
Z80 = 1.2816             # 80% two-sided band
MIN_PRIOR_PROMOS = 3
SOURCE = "promotions table + sales_daily (difference-in-differences vs. never-promoted products, +-28 days)"


def did_uplift_pct(win_scope: float, win_ctrl: float, base_scope: float, base_ctrl: float) -> float | None:
    """Uplift in %: (scope/control ratio in the promo window) / (same ratio in the baseline) - 1. Inputs are unit sums."""
    if win_ctrl <= 0 or base_ctrl <= 0 or base_scope <= 0:
        return None
    return ((win_scope / win_ctrl) / (base_scope / base_ctrl) - 1.0) * 100.0


@dataclass(frozen=True)
class PromoObs:
    promo_id: str
    department: str
    category: str | None
    discount_pct: float
    start: date
    end: date
    uplift_pct: float | None  # None: no usable baseline
    promo_days: int = 0
    baseline_days: int = 0
    placebo: bool = False

    def covers(self, department: str | None, category: str | None) -> bool:
        return self.department == department and (self.category is None or self.category == category)


@dataclass(frozen=True)
class LiftEstimate:
    scope: str
    discount_pct: float
    lift_pct: float          # mid
    lift_low_pct: float      # 80% band, floored at 0
    lift_high_pct: float
    se_pct: float
    n_promos: int
    promo_ids: tuple[str, ...]
    confidence: str          # "medium" | "low"
    extrapolated: bool       # asked depth is well beyond the deepest promo observed in the scope
    source: str = SOURCE

    def brief(self) -> dict:
        return {"scope": self.scope, "discount_pct": self.discount_pct, "lift_pct": round(self.lift_pct, 1),
                "lift_low_pct": round(self.lift_low_pct, 1), "lift_high_pct": round(self.lift_high_pct, 1),
                "n_promos": self.n_promos, "promo_ids": list(self.promo_ids), "confidence": self.confidence,
                "extrapolated": self.extrapolated, "noise_floor_pct": NOISE_FLOOR_PCT, "source": self.source}


def _elasticity(obs: list[PromoObs]) -> tuple[float, float]:
    """Least squares through the origin of uplift on discount; (e, se) with the placebo noise as per-promo sd."""
    sdd = sum(o.discount_pct ** 2 for o in obs)
    e = sum(o.uplift_pct * o.discount_pct for o in obs) / sdd
    return e, NOISE_FLOOR_PCT / sqrt(sdd)


class PromoLiftTable:
    """Finished-promo observations known at `as_of`; answers lift questions per (department, category, depth)."""

    def __init__(self, obs: list[PromoObs] | tuple[PromoObs, ...], as_of: date) -> None:
        self.as_of = as_of
        self.obs = tuple(o for o in obs if not o.placebo and o.end <= as_of and o.uplift_pct is not None
                         and o.discount_pct > 0)

    def pooled(self) -> tuple[float, float] | None:
        return _elasticity(list(self.obs)) if len(self.obs) >= MIN_PRIOR_PROMOS else None

    def estimate(self, department: str | None, category: str | None, discount_pct: float) -> LiftEstimate | None:
        fam = [o for o in self.obs if o.covers(department, category)]
        if not fam or discount_pct <= 0:
            return None
        e, se = _elasticity(fam)
        prior = self.pooled()
        if prior is not None:  # precision-weighted shrinkage toward the chain-wide elasticity
            w_f, w_p = 1.0 / se ** 2, 1.0 / PRIOR_SD ** 2
            e, se = (e * w_f + prior[0] * w_p) / (w_f + w_p), sqrt(1.0 / (w_f + w_p))
        lift, se_l = e * discount_pct, se * discount_pct
        medium = len(fam) >= 2 and se_l > 0 and lift / se_l >= 2.0
        scope = f"{department}/{category}" if any(o.category for o in fam) and category else str(department)
        return LiftEstimate(scope, discount_pct, lift, max(0.0, lift - Z80 * se_l), max(0.0, lift + Z80 * se_l), se_l,
                            len(fam), tuple(sorted(o.promo_id for o in fam)), "medium" if medium else "low",
                            discount_pct > 1.25 * max(o.discount_pct for o in fam))


def markdown_recovery(est: LiftEstimate, daily_demand: float, units: float) -> tuple[float, float, float]:
    """Share of `units` that the lift clears on the day of the markdown: extra units = daily demand x lift, capped at
    the units at risk. (low, mid, high) from the 80% band; lift below the noise floor is still reported, not hidden."""
    if units <= 0:
        return 0.0, 0.0, 0.0
    return tuple(max(0.0, min(1.0, daily_demand * x / 100.0 / units))  # type: ignore[return-value]
                 for x in (est.lift_low_pct, est.lift_pct, est.lift_high_pct))


def promo_effect(est: LiftEstimate, daily_demand: float, days: int, units_at_risk: float, price: float, unit_cost: float,
                 discount: float) -> dict:
    """Expected effect of discounting the SKU for `days` days. Extra units sell stock that would otherwise be wasted
    (up to units_at_risk); every baseline unit also loses the discount (cannibalisation).
    net = extra x price x (1 - d) - baseline_units x price x d  (cost cancels: it was sunk, the units expired otherwise).
    Returns low / mid / high for lift (low lift = low net) plus the units cleared and waste avoided at mid."""
    out: dict[str, float] = {}
    for tag, lift in (("low", est.lift_low_pct), ("mid", est.lift_pct), ("high", est.lift_high_pct)):
        cleared = min(max(0.0, units_at_risk), daily_demand * days * lift / 100.0)
        out[tag] = cleared * price * (1.0 - discount) - daily_demand * days * price * discount
        if tag == "mid":
            out["cleared_units"], out["waste_avoided_usd"] = cleared, cleared * unit_cost
    return out
