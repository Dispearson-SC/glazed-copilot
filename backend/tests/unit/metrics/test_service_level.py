import pytest

from glazed_backend.metrics.service_level import SENSITIVITY, critical_ratio, sensitivity_levels


def test_critical_ratio_is_cu_over_cu_plus_co():
    # Cu = 10 - 2.6 = 7.4, Co = 2.6 (salvage 0) -> 0.74
    assert critical_ratio(price=10.0, unit_cost=2.6) == pytest.approx(0.74)


def test_critical_ratio_uses_salvage_when_given():
    # Co = 2.6 - 1.0 = 1.6 -> 7.4 / 9.0
    assert critical_ratio(10.0, 2.6, salvage=1.0) == pytest.approx(7.4 / 9.0)


def test_critical_ratio_is_bounded_for_degenerate_prices():
    assert critical_ratio(price=1.0, unit_cost=1.5) == 0.05  # negative margin: never order for service
    assert critical_ratio(price=100.0, unit_cost=0.0) == 0.99  # free product: capped below 1


def test_sensitivity_levels_are_the_three_reference_values():
    assert SENSITIVITY == (0.60, 0.74, 0.85)
    assert sensitivity_levels() == {"0.60": 0.60, "0.74": 0.74, "0.85": 0.85}
