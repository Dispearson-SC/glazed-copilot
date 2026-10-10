"""GET /api/v1/cases/{id}/forecast: model forecast vs actuals with NO look-ahead enforced in the backend."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from glazed_backend.adapters.driven.forecast import BaselineForecast
from glazed_backend.adapters.driving.app import Container, create_app
from glazed_backend.ports.forecast import ForecastResult, ForecastRow
from tests.fakes import (FakeClock, FakeCore, FakeMetrics, InMemoryAlerts, InMemoryBacktests, InMemoryCases,
                         InMemoryExecutions, InMemoryProposals, InMemoryTrace, make_series)

AS_OF = date(2026, 3, 10)  # a Tuesday
START = date(2025, 12, 1)


def units_a(d):
    return 10 + d.isoweekday()


class StubForecast:
    """Fixed forecast for every requested SKU-day: p50 12, p10 10, p90 14 (+ optional p20/p80)."""

    def __init__(self, origin, quantiles=None, model="stub-model"):
        self.origin, self.model, self.q = origin, model, quantiles or {"p10": 10.0, "p90": 14.0}

    def forecast(self, store_id, as_of, skus, date_from, date_to, history):
        rows, d = [], date_from
        while d <= date_to:
            rows += [ForecastRow(s.sku, d, 12.0, dict(self.q)) for s in history if skus is None or s.sku in skus]
            d += timedelta(days=1)
        return ForecastResult(self.model, "v7", self.origin, rows)

    def quantile(self, *a, **k):
        return None


def build(series=None, leak=False, forecasters=None):
    m = FakeMetrics()
    m.series = series if series is not None else [make_series("A", 2.0, START, AS_OF, units_a),
                                                  make_series("B", 5.0, START, AS_OF, lambda d: 4)]
    m.leak = leak
    c = Container(metrics=m, core=FakeCore(), cases=InMemoryCases(), alerts=InMemoryAlerts(), proposals=InMemoryProposals(),
                  executions=InMemoryExecutions(), backtests=InMemoryBacktests(), trace=InMemoryTrace(), clock=FakeClock(),
                  forecasters=forecasters if forecasters is not None else [BaselineForecast()])
    client = TestClient(create_app(c))
    cid = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": AS_OF.isoformat()}).json()["case_id"]
    return client, cid


def get(client, cid, **params):
    r = client.get(f"/api/v1/cases/{cid}/forecast", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_sku_level_shape_baseline_and_units():
    client, cid = build()
    out = get(client, cid, sku="A", **{"from": "2026-03-08", "to": "2026-03-14"})
    assert out["store_id"] == "S030" and out["sku"] == "A" and out["level"] == "sku" and out["unit"] == "units"
    assert out["as_of"] == "2026-03-10" and out["forecast_origin"] == "2026-03-10"
    assert out["model"] == "baseline-weekday-8w" and out["model_version"] and out["horizon_days"] == 4
    assert [p["date"] for p in out["points"]] == [f"2026-03-{d:02d}" for d in range(8, 15)]
    wed = next(p for p in out["points"] if p["date"] == "2026-03-11")
    assert wed["forecast"] == pytest.approx(13) and wed["baseline"] == pytest.approx(13) and wed["actual"] is None
    assert set(wed) >= {"date", "forecast", "p10", "p90", "baseline", "actual", "censored"}
    mon = next(p for p in out["points"] if p["date"] == "2026-03-09")
    assert mon["actual"] == 11 and mon["forecast"] == pytest.approx(11) and mon["censored"] is False
    assert set(out["metrics_to_date"]) >= {"wape", "bias", "coverage_p10_p90", "wape_baseline", "n_days",
                                           "pinball_074", "censored_coverage"}


def test_actual_is_null_after_as_of_even_if_the_adapter_leaks_future_rows():
    leaky = [make_series("A", 2.0, START, date(2026, 4, 30), lambda d: units_a(d) if d <= AS_OF else 5000)]
    client, cid = build(series=leaky, leak=True)
    out = get(client, cid, sku="A", **{"from": "2026-03-05", "to": "2026-03-20"})
    assert all(p["actual"] is None for p in out["points"] if p["date"] > "2026-03-10")
    assert any(p["actual"] is not None for p in out["points"] if p["date"] <= "2026-03-10")
    assert max(p["forecast"] for p in out["points"]) < 100  # the baseline never saw the future rows
    assert out["forecast_origin"] <= out["as_of"] and out["metrics_to_date"]["n_days"] == 6  # Mar 5..10 only


def test_metrics_only_cover_dates_up_to_as_of_and_exclude_censored_days():
    series = [make_series("A", 2.0, START, AS_OF, lambda d: {8: 10, 9: 12, 10: 16}.get(d.day, 12),
                          stockout=lambda d: 3.0 if d == date(2026, 3, 9) else 0.0)]
    client, cid = build(series=series, forecasters=[StubForecast(AS_OF)])
    out = get(client, cid, sku="A", **{"from": "2026-03-08", "to": "2026-03-12"})
    by = {p["date"]: p for p in out["points"]}
    assert by["2026-03-09"]["censored"] is True and by["2026-03-08"]["censored"] is False
    m = out["metrics_to_date"]
    assert m["n_days"] == 2  # Mar 8 (10) and Mar 10 (16); Mar 9 is censored; Mar 11-12 are in the future
    assert m["wape"] == pytest.approx((2 + 4) / 26, abs=1e-3) and m["bias"] == pytest.approx((2 - 4) / 26, abs=1e-3)
    assert m["coverage_p10_p90"] == pytest.approx(0.5) and m["censored_coverage"] == 1.0  # forecast 12 >= actual 12


def test_store_level_sums_skus_in_usd_with_unit_prices():
    client, cid = build()
    out = get(client, cid, level="store", **{"from": "2026-03-09", "to": "2026-03-11"})
    assert out["sku"] is None and out["level"] == "store" and out["unit"] == "usd"
    mon = next(p for p in out["points"] if p["date"] == "2026-03-09")
    assert mon["actual"] == pytest.approx(11 * 2.0 + 4 * 5.0)
    wed = next(p for p in out["points"] if p["date"] == "2026-03-11")
    assert wed["forecast"] == pytest.approx(13 * 2.0 + 4 * 5.0) and wed["actual"] is None


def test_store_level_day_is_censored_when_stockouts_hit_a_large_share_of_the_sales():
    series = [make_series("A", 2.0, START, AS_OF, lambda d: 10, stockout=lambda d: 2.0 if d == date(2026, 3, 9) else 0.0),
              make_series("B", 5.0, START, AS_OF, lambda d: 1, stockout=lambda d: 2.0 if d == date(2026, 3, 8) else 0.0)]
    client, cid = build(series=series)
    by = {p["date"]: p for p in get(client, cid, level="store", **{"from": "2026-03-07", "to": "2026-03-10"})["points"]}
    assert by["2026-03-09"]["censored"] is True  # SKU A is 20 of 25 USD of the day
    assert by["2026-03-08"]["censored"] is False  # SKU B is 5 of 25 USD: under the share threshold
    assert by["2026-03-07"]["censored"] is False


def test_composition_prefers_the_file_forecast_when_its_origin_is_not_in_the_future():
    client, cid = build(forecasters=[StubForecast(date(2026, 3, 1)), BaselineForecast()])
    out = get(client, cid, sku="A", **{"from": "2026-03-09", "to": "2026-03-11"})
    assert out["model"] == "stub-model" and out["model_version"] == "v7" and out["forecast_origin"] == "2026-03-01"
    assert all(p["forecast"] == 12.0 for p in out["points"])


def test_a_file_forecast_issued_after_as_of_is_never_shown():
    client, cid = build(forecasters=[StubForecast(date(2026, 7, 19)), BaselineForecast()])
    out = get(client, cid, sku="A", **{"from": "2026-03-09", "to": "2026-03-11"})
    assert out["model"] == "baseline-weekday-8w" and out["forecast_origin"] <= out["as_of"]


def test_extra_quantiles_are_exposed_per_point_when_the_model_has_them():
    q = {"p10": 10.0, "p20": 11.0, "p80": 13.0, "p90": 14.0}
    client, cid = build(forecasters=[StubForecast(AS_OF, q)])
    p = get(client, cid, sku="A", **{"from": "2026-03-11", "to": "2026-03-11"})["points"][0]
    assert p["p10"] == 10.0 and p["p90"] == 14.0 and p["quantiles"] == {"p10": 10.0, "p20": 11.0, "p50": 12.0, "p80": 13.0, "p90": 14.0}


def test_defaults_and_errors():
    client, cid = build()
    out = get(client, cid, sku="A")
    assert out["points"][0]["date"] == "2026-03-03" and out["points"][-1]["date"] == "2026-03-17"
    assert get(client, cid)["level"] == "store"
    base = f"/api/v1/cases/{cid}/forecast"
    assert client.get(base, params={"level": "sku"}).status_code == 400
    assert client.get(base, params={"level": "store", "sku": "A"}).status_code == 400
    assert client.get(base, params={"level": "galaxy"}).status_code == 400
    assert client.get(base, params={"sku": "A", "from": "2026-03-10", "to": "2026-03-01"}).status_code == 400
    assert client.get(base, params={"sku": "ZZZ"}).status_code == 404
    assert client.get("/api/v1/cases/nope/forecast", params={"sku": "A"}).status_code == 404


# --- GET /cases/{id}/forecast/accuracy -------------------------------------------------------------------------

def accuracy(client, cid, **params):
    r = client.get(f"/api/v1/cases/{cid}/forecast/accuracy", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def acc_env(leak=False):
    series = [make_series("A", 2.0, START, AS_OF, lambda d: 10 if d <= AS_OF else 9000, shelf_life=1),
              make_series("B", 5.0, START, AS_OF, lambda d: 12, shelf_life=3),
              make_series("C", 1.0, START, AS_OF, lambda d: 20, shelf_life=None)]
    return build(series=series, leak=leak, forecasters=[StubForecast(AS_OF)])


def test_accuracy_by_shelf_life_segments_the_skus_and_only_scores_dates_up_to_as_of():
    client, cid = acc_env(leak=True)
    out = accuracy(client, cid, by="shelf_life", **{"from": "2026-03-01", "to": "2026-03-20"})
    assert out["by"] == "shelf_life" and out["as_of"] == "2026-03-10" and set(out["groups"]) == {"1", "2-3", "non_perishable"}
    one = out["groups"]["1"]
    assert one["n_days"] == 10 and one["wape"] == pytest.approx(2 / 10, abs=1e-3)  # forecast 12 vs actual 10, Mar 1..10
    assert out["groups"]["2-3"]["wape"] == 0.0 and out["groups"]["non_perishable"]["bias"] == pytest.approx(-8 / 20, abs=1e-3)
    assert out["overall"]["n_days"] == 30 and out["window"] == {"from": "2026-03-01", "to": "2026-03-10"}


def test_accuracy_by_sku_and_by_format():
    client, cid = acc_env()
    by_sku = accuracy(client, cid, by="sku")
    assert set(by_sku["groups"]) == {"A", "B", "C"}
    fmt = accuracy(client, cid, by="format")
    assert set(fmt["groups"]) == {"Shop-in-Shop"} and fmt["groups"]["Shop-in-Shop"]["n_days"] == by_sku["overall"]["n_days"]


def test_accuracy_rejects_an_unknown_grouping_and_unknown_cases():
    client, cid = acc_env()
    assert client.get(f"/api/v1/cases/{cid}/forecast/accuracy", params={"by": "color"}).status_code == 400
    assert client.get(f"/api/v1/cases/{cid}/forecast/accuracy").status_code == 400
    assert client.get("/api/v1/cases/nope/forecast/accuracy", params={"by": "sku"}).status_code == 404
