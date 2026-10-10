"""Internal forecast routes for the Agent-Core tools: store and as_of come from the case, never from the caller."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from glazed_backend.adapters.driven.forecast import BaselineForecast
from glazed_backend.adapters.driving.app import Container, create_app
from tests.fakes import (FakeClock, FakeCore, FakeMetrics, InMemoryAlerts, InMemoryBacktests, InMemoryCases,
                         InMemoryExecutions, InMemoryProposals, InMemoryTrace, make_series)
from tests.unit.test_forecast_api import AS_OF, START, StubForecast, units_a


def build(series=None, flow=None, leak=False, forecasters=None):
    m = FakeMetrics()
    m.series = series if series is not None else [make_series("A", 2.0, START, AS_OF, units_a)]
    m.flow = flow if flow is not None else []
    m.leak = leak
    c = Container(metrics=m, core=FakeCore(), cases=InMemoryCases(), alerts=InMemoryAlerts(), proposals=InMemoryProposals(),
                  executions=InMemoryExecutions(), backtests=InMemoryBacktests(), trace=InMemoryTrace(), clock=FakeClock(),
                  forecasters=forecasters if forecasters is not None else [BaselineForecast()])
    client = TestClient(create_app(c))
    cid = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": AS_OF.isoformat()}).json()["case_id"]
    return client, {"X-Glazed-Case": cid}


def flow_rows(end=AS_OF, days=100, footfall=True):
    out, d = [], end - timedelta(days=days)
    while d <= end:
        out.append({"date": d, "transactions": 100 + d.isoweekday() * 10, "footfall": 400 + d.isoweekday() if footfall else None,
                    "net_sales": (100 + d.isoweekday() * 10) * 8.0})
        d += timedelta(days=1)
    return out


DEMAND = "/internal/v1/forecast/demand"
FLOW = "/internal/v1/forecast/flow"


def test_demand_forecast_shape_and_values():
    client, h = build()
    r = client.get(DEMAND, headers=h, params={"sku": "A", "target_date": "2026-03-11"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["sku"] == "A" and out["target_date"] == "2026-03-11" and out["qty"] == pytest.approx(13)
    assert set(out["quantiles"]) == {"p10", "p20", "p50", "p80", "p90"}
    assert out["qty_range"] == {"p10": out["quantiles"]["p10"], "p50": out["quantiles"]["p50"], "p90": out["quantiles"]["p90"]}
    assert out["weather_kind"] == "observed" and out["model"] == "baseline-weekday-8w" and out["model_version"]
    assert out["forecast_origin"] == "2026-03-10" and out["censored_share"] == 0.0


def test_demand_target_date_must_be_after_as_of():
    client, h = build()
    for d in ("2026-03-10", "2026-03-01"):
        assert client.get(DEMAND, headers=h, params={"sku": "A", "target_date": d}).status_code == 422
    assert client.get(DEMAND, headers=h, params={"sku": "A"}).status_code == 422


def test_store_and_as_of_params_cannot_override_the_case():
    client, h = build()
    ok = {"sku": "A", "target_date": "2026-03-11"}
    assert client.get(DEMAND, headers=h, params={**ok, "store_id": "S030", "as_of": "2026-03-10"}).status_code == 200
    assert client.get(DEMAND, headers=h, params={**ok, "store_id": "S001"}).status_code == 400
    assert client.get(DEMAND, headers=h, params={**ok, "as_of": "2026-12-31"}).status_code == 400
    assert client.get(DEMAND, params=ok).status_code == 400  # no case header


def test_demand_censored_share_counts_stockout_days_in_the_training_window():
    s = [make_series("A", 2.0, START, AS_OF, units_a, stockout=lambda d: 2.0 if d.day % 2 == 0 and d.month == 3 else 0.0)]
    client, h = build(series=s)
    out = client.get(DEMAND, headers=h, params={"sku": "A", "target_date": "2026-03-11"}).json()
    assert out["censored_share"] == pytest.approx(5 / 56, abs=1e-3)  # Mar 2,4,6,8,10 in the last 56 days


def test_demand_interpolates_missing_levels_and_says_so():
    client, h = build(forecasters=[StubForecast(AS_OF)])
    out = client.get(DEMAND, headers=h, params={"sku": "A", "target_date": "2026-03-11"}).json()
    assert out["quantiles"]["p20"] == pytest.approx(10 + 0.1 / 0.4 * 2) and out["interpolated_quantiles"] == ["p20", "p80"]
    assert out["model"] == "stub-model"


def test_demand_no_forecast_is_a_404_with_a_clear_detail():
    client, h = build()
    r = client.get(DEMAND, headers=h, params={"sku": "ZZZ", "target_date": "2026-03-11"})
    assert r.status_code == 404 and "ZZZ" in r.json()["detail"]
    short = [make_series("A", 2.0, date(2026, 3, 9), AS_OF, units_a)]
    client2, h2 = build(series=short)
    assert client2.get(DEMAND, headers=h2, params={"sku": "A", "target_date": "2026-03-11"}).status_code == 404


def test_a_forecast_issued_after_as_of_is_not_served_to_agents_either():
    client, h = build(forecasters=[StubForecast(date(2026, 7, 19)), BaselineForecast()])
    out = client.get(DEMAND, headers=h, params={"sku": "A", "target_date": "2026-03-11"}).json()
    assert out["model"] == "baseline-weekday-8w" and out["forecast_origin"] <= "2026-03-10"


def test_flow_forecast_is_a_weekday_baseline_with_empirical_quantiles():
    client, h = build(flow=flow_rows())
    r = client.get(FLOW, headers=h, params={"target_date": "2026-03-13"})  # Friday
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["granularity"] == "daily" and out["target_date"] == "2026-03-13" and out["forecast_origin"] == "2026-03-10"
    assert out["transactions"] == {"p10": 150.0, "p50": 150.0, "p90": 150.0}
    assert out["footfall"]["p50"] == 405.0 and out["avg_ticket"] == {"p10": 8.0, "p50": 8.0, "p90": 8.0}
    assert out["model"] == "flow-weekday-8w"


def test_flow_uses_nothing_after_as_of_and_nulls_what_does_not_exist():
    rows = flow_rows(end=AS_OF + timedelta(days=30))  # a leaky adapter returns the future too
    client, h = build(flow=rows, leak=True)
    out = client.get(FLOW, headers=h, params={"target_date": "2026-03-13"}).json()
    assert out["forecast_origin"] == "2026-03-10" and out["transactions"]["p50"] == 150.0
    nofoot, h2 = build(flow=flow_rows(footfall=False))
    assert nofoot.get(FLOW, headers=h2, params={"target_date": "2026-03-13"}).json()["footfall"] is None


def test_flow_validation_and_missing_data():
    client, h = build(flow=flow_rows())
    assert client.get(FLOW, headers=h, params={"target_date": "2026-03-10"}).status_code == 422
    empty, h2 = build(flow=[])
    r = empty.get(FLOW, headers=h2, params={"target_date": "2026-03-13"})
    assert r.status_code == 404 and "flow" in r.json()["detail"].lower()
