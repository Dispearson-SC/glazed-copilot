"""R2 (pure part): the realized outcome of a decision, its verdict against the expected range and its Spanish summary."""
from datetime import date

import pytest

from glazed_backend.metrics.outcomes import build_outcome, outcome_text, verdict

SIM = {"net_usd_low": 4.0, "net_usd_mid": 20.0, "net_usd_high": 30.0, "label": "simulated"}
OBS = {"net_usd": 18.0, "waste_usd": 2.5, "lost_sales_usd": 1.25, "censored": True, "units_sold": 27, "units_forecast": 30.0,
       "window": ["2026-07-20", "2026-07-22"]}
DEC = {"decision_id": "d1", "case_id": "c1", "issue_id": "S030|stockout_risk|A", "action_type": "place_order",
       "params": {"sku": "A", "qty": 12, "decision_as_of": "2026-07-19"}}
HORIZON = {"decision_date": "2026-07-19", "days": 3, "ends": "2026-07-22", "passed": True}


@pytest.mark.parametrize("net,expected", [(40.0, "better"), (31.0, "within"), (20.0, "within"), (4.0, "within"),
                                           (2.0, "within"), (-5.0, "worse")])
def test_verdict_compares_the_net_with_the_expected_range_and_a_tolerance(net, expected):
    code, es = verdict(net, SIM)
    assert code == expected
    assert es == {"better": "mejor de lo esperado", "within": "dentro de lo esperado", "worse": "peor de lo esperado"}[code]


def test_a_zero_width_range_still_has_a_tolerance():
    flat = {"net_usd_low": None, "net_usd_mid": 0.0, "net_usd_high": None}
    assert verdict(0.5, flat)[0] == "within" and verdict(5.0, flat)[0] == "better" and verdict(-5.0, flat)[0] == "worse"


def test_complete_outcome_has_realized_figures_sold_vs_forecast_and_a_verdict():
    o = build_outcome(DEC, HORIZON, SIM, OBS, date(2026, 7, 23), True, "within_range")
    assert o["complete"] is True and o["measured_as_of"] == "2026-07-23" and o["decided_as_of"] == "2026-07-19"
    assert o["observed"] == {"net_usd": 18.0, "waste_usd": 2.5, "lost_sales_usd": 1.25, "censored": True, "units_sold": 27,
                             "units_forecast": 30.0, "window": ["2026-07-20", "2026-07-22"]}
    assert o["sold_vs_forecast"] == {"units_sold": 27, "units_forecast": 30.0, "delta_units": -3.0, "delta_pct": -10.0}
    assert o["verdict"] == "dentro de lo esperado" and o["verdict_code"] == "within" and o["label"] == "backtest"
    assert o["simulated"] == SIM and o["horizon_ends"] == "2026-07-22" and o["sku"] == "A"
    assert o["score"] == {"within_expected_range": True, "error_vs_mid_usd": -2.0, "diagnosis": "within_range"}
    assert "censur" in o["summary"] and "$2.50" in o["summary"] and "27" in o["summary"] and o["summary"].startswith("Resultado medido")


def test_partial_outcome_has_no_verdict_yet():
    o = build_outcome(DEC, {**HORIZON, "passed": False}, SIM, {**OBS, "window": ["2026-07-20", "2026-07-20"]},
                      date(2026, 7, 21), False, None)
    assert o["complete"] is False and o["verdict"] is None and o["verdict_code"] is None and o["score"] is None
    assert o["window_days"] == 1 and "en curso" in o["summary"]


def test_missing_forecast_is_reported_as_unknown_not_invented():
    o = build_outcome(DEC, HORIZON, SIM, {**OBS, "units_forecast": None}, date(2026, 7, 23), True, "within_range")
    assert o["sold_vs_forecast"] == {"units_sold": 27, "units_forecast": None, "delta_units": None, "delta_pct": None}


def test_text_names_the_product():
    o = build_outcome(DEC, HORIZON, SIM, OBS, date(2026, 7, 23), True, "within_range")
    assert "Pan" in outcome_text(o, "Pan")
