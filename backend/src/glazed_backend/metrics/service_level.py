"""Newsvendor critical ratio per SKU: CR = Cu / (Cu + Co)."""
from __future__ import annotations

from .types import Config

SENSITIVITY = (0.60, 0.74, 0.85)
CR_MIN, CR_MAX = 0.05, 0.99


def critical_ratio(price: float, unit_cost: float, salvage: float = 0.0, waste_penalty: float = 0.0) -> float:
    """Cu = price - cost (margin lost per unit short); Co = cost - salvage (loss per unit left over).

    Glazed has no markdown history, so salvage defaults to 0. `waste_penalty` (multiple of unit cost) adds a
    shadow cost per wasted unit to Co; 0 is the plain margin ratio. The result is clamped to [0.05, 0.99]."""
    cu = price - unit_cost
    co = unit_cost - salvage + waste_penalty * unit_cost
    if cu <= 0:
        return CR_MIN
    if co <= 0:
        return CR_MAX
    return min(CR_MAX, max(CR_MIN, cu / (cu + co)))


def sensitivity_levels() -> dict[str, float]:
    return {f"{s:.2f}": s for s in SENSITIVITY}


def overage_cost(unit_cost: float, cfg: Config | None) -> float:
    """Co used to round to cases: the cost of a leftover perishable unit, plus the waste penalty when waste_aware."""
    pen = cfg.waste_penalty if cfg is not None and cfg.waste_aware else 0.0
    return max(unit_cost * (1.0 + pen), 1e-6)


def service_target(price: float, unit_cost: float, perishable: bool, cfg: Config) -> float:
    """Service level of the order: critical ratio for perishables, at least cfg.non_perishable_service otherwise.
    waste_aware: the penalty enters the ratio of perishables and perishable_service_cap bounds it."""
    if not cfg.waste_aware:
        cr = critical_ratio(price, unit_cost)
        return cr if perishable else max(cr, cfg.non_perishable_service)
    if not perishable:
        return max(critical_ratio(price, unit_cost), cfg.non_perishable_service)  # waste does not apply to shelf-stable stock
    cr = critical_ratio(price, unit_cost, waste_penalty=cfg.waste_penalty)
    return min(cr, cfg.perishable_service_cap) if cfg.perishable_service_cap is not None else cr
