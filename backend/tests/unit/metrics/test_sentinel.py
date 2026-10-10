from datetime import date, datetime, timezone

from glazed_backend.metrics.sentinel import HORIZON_DAYS, evaluate_decision, latest_execution

T0 = datetime(2026, 10, 10, 9, tzinfo=timezone.utc)


def ex(status, source="simulated", minute=0, detail=""):
    return {"status": status, "source": source, "executed_at": T0.replace(minute=minute), "detail": detail}


def decision(status="approved", expected=None, as_of="2026-03-10"):
    return {"decision_id": "p1", "status": status, "action_type": "adjust_order_qty", "issue_id": "S030|overstock_waste|SKU",
            "params": {"decision_as_of": as_of, "expected": expected if expected is not None else
                       {"net_usd_mid": 10.0, "net_usd_low": 4.0, "net_usd_high": 16.0}}}


def test_the_latest_execution_wins_and_an_operational_record_beats_a_simulated_one():
    assert latest_execution([ex("executed", minute=1), ex("not_executed", "demo_injected", minute=2)])["status"] == "not_executed"
    assert latest_execution([ex("executed", "operational", minute=1), ex("not_executed", "simulated", minute=2)])["status"] == "executed"
    assert latest_execution([]) is None


def test_a_rejected_or_pending_decision_is_not_applicable():
    for st in ("rejected", "pending"):
        r = evaluate_decision(decision(st), [], date(2026, 3, 20), None, [])
        assert r["applicable"] is False and r["diagnosis"] is None


def test_approved_without_any_execution_record_is_not_executed():
    r = evaluate_decision(decision(), [], date(2026, 3, 20), None, [])
    assert r["execution_status"] == "not_executed" and r["diagnosis"] == "not_executed"


def test_partial_and_not_executed_are_diagnosed_as_non_compliance():
    for st in ("not_executed", "partial"):
        r = evaluate_decision(decision(), [ex(st, "demo_injected")], date(2026, 3, 20), None, [])
        assert r["execution_status"] == st and r["diagnosis"] == "not_executed" and "manager" in r["explanation"]


def test_executed_before_the_horizon_has_no_observed_outcome_and_no_diagnosis():
    d0 = date(2026, 3, 10)
    r = evaluate_decision(decision(), [ex("executed")], date(2026, 3, 10 + HORIZON_DAYS - 1), {"net_usd": 9.0}, [])
    assert r["horizon"]["passed"] is False and r["observed"] is None and r["diagnosis"] is None
    assert r["horizon"]["ends"] == (d0.replace(day=10 + HORIZON_DAYS)).isoformat()


def test_outcome_inside_the_simulated_range_is_within_range_and_labelled_backtest():
    r = evaluate_decision(decision(), [ex("executed")], date(2026, 3, 14), {"net_usd": 8.0}, [])
    assert r["diagnosis"] == "within_range" and r["observed"]["label"] == "backtest" and r["simulated"]["net_usd_mid"] == 10.0


def test_outside_the_range_with_an_overlapping_event_is_attributed_to_the_event():
    ev = [{"type": "bloqueo", "date_from": "2026-03-11", "date_to": "2026-03-12", "note": "road closed"}]
    r = evaluate_decision(decision(), [ex("executed")], date(2026, 3, 14), {"net_usd": -20.0}, ev)
    assert r["diagnosis"] == "external_event" and r["events"][0]["type"] == "bloqueo"


def test_outside_the_range_without_events_is_a_forecast_error():
    ev = [{"type": "bloqueo", "date_from": "2026-04-01", "date_to": "2026-04-02"}]  # does not overlap the horizon
    r = evaluate_decision(decision(), [ex("executed")], date(2026, 3, 14), {"net_usd": -20.0}, ev)
    assert r["diagnosis"] == "forecast_error" and r["events"] == []


def test_without_a_measurable_outcome_the_diagnosis_stays_open():
    r = evaluate_decision(decision(), [ex("executed")], date(2026, 3, 14), None, [])
    assert r["diagnosis"] is None and "no measurable outcome" in r["explanation"]
