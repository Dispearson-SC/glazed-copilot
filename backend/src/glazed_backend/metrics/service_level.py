"""Newsvendor critical ratio per SKU: CR = Cu / (Cu + Co)."""
from __future__ import annotations

SENSITIVITY = (0.60, 0.74, 0.85)
CR_MIN, CR_MAX = 0.05, 0.99


def critical_ratio(price: float, unit_cost: float, salvage: float = 0.0) -> float:
    """Cu = price - cost (margin lost per unit short); Co = cost - salvage (loss per unit left over).

    Glazed has no markdown history, so salvage defaults to 0. The result is clamped to [0.05, 0.99]."""
    cu = price - unit_cost
    co = unit_cost - salvage
    if cu <= 0:
        return CR_MIN
    if co <= 0:
        return CR_MAX
    return min(CR_MAX, max(CR_MIN, cu / (cu + co)))


def sensitivity_levels() -> dict[str, float]:
    return {f"{s:.2f}": s for s in SENSITIVITY}
