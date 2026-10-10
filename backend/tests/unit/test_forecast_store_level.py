"""Q5: the store-level USD forecast must reconcile with store net sales (no double scale), share the day-summary
baseline, aggregate bands with diversification and never look ahead."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from glazed_backend.adapters.driven.forecast import FileForecast
from glazed_backend.adapters.driving.app import Container, create_app
from glazed_backend.ports.forecast import ForecastResult, ForecastRow
from tests.fakes import (FakeClock, FakeCore, FakeMetrics, InMemoryAlerts, InMemoryBacktests, InMemoryCases,
                         InMemoryExecutions, InMemoryProposals, InMemoryTrace, make_series)
from tests.unit.test_forecast_adapters import BASE_COLS, write_parquet
from tests.unit.test_forecast_api import AS_OF, START, StubForecast

Z90 = 1.2815515655446004


def build(net=lambda d: 20.0, flow_after=None, forecaster=None, with_flow=True):
    """A: 10 units x $2 and B: 4 units x $5 a day = $40 of unit value; store net sales come from `net`."""
    m = FakeMetrics()
    m.series = [make_series("A", 2.0, START, AS_OF, lambda d: 10), make_series("B", 5.0, START, AS_OF, lambda d: 4)]
    m.flow, d = [], START
    while with_flow and d <= AS_OF:
        m.flow.append({"date": d, "transactions": 10, "footfall": None, "net_sales": net(d)})
        d += timedelta(days=1)
    for extra in flow_after or []:
        m.flow.append(extra)
    m.leak = bool(flow_after)
    c = Container(metrics=m, core=FakeCore(), cases=InMemoryCases(), alerts=InMemoryAlerts(), proposals=InMemoryProposals(),
                  executions=InMemoryExecutions(), backtests=InMemoryBacktests(), trace=InMemoryTrace(), clock=FakeClock(),
                  forecasters=[forecaster or StubForecast(AS_OF)])
    client = TestClient(create_app(c))
    cid = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": AS_OF.isoformat()}).json()["case_id"]
    return client, cid


def store(client, cid, frm="2026-03-09", to="2026-03-14"):
    r = client.get(f"/api/v1/cases/{cid}/forecast", params={"level": "store", "from": frm, "to": to})
    assert r.status_code == 200, r.text
    return r.json()


def test_store_forecast_is_scaled_to_net_sales_by_the_28_day_calibration_factor():
    client, cid = build(net=lambda d: 20.0)  # net sales are half of units x list price
    out = store(client, cid)
    assert out["calibration"]["factor"] == pytest.approx(0.5) and out["calibration"]["days"] == 28
    wed = next(p for p in out["points"] if p["date"] == "2026-03-11")
    assert wed["forecast"] == pytest.approx((12 * 2 + 12 * 5) * 0.5)  # 42, not the raw 84
    mon = next(p for p in out["points"] if p["date"] == "2026-03-09")
    assert mon["actual"] == pytest.approx(20.0)  # actual is the store's net sales


def test_without_store_net_sales_the_factor_is_one_and_actual_falls_back_to_units_x_price():
    client, cid = build(with_flow=False)
    out = store(client, cid)
    assert out["calibration"] is None
    mon = next(p for p in out["points"] if p["date"] == "2026-03-09")
    assert mon["actual"] == pytest.approx(10 * 2 + 4 * 5)
    assert next(p for p in out["points"] if p["date"] == "2026-03-11")["forecast"] == pytest.approx(84.0)


def test_store_baseline_is_the_day_summary_same_weekday_average_of_net_sales():
    client, cid = build(net=lambda d: 100.0 * d.isoweekday())
    out = store(client, cid)
    wed = next(p for p in out["points"] if p["date"] == "2026-03-11")
    assert wed["baseline"] == pytest.approx(300.0)  # mean of the previous eight Wednesdays' net_sales
    sat = next(p for p in out["points"] if p["date"] == "2026-03-14")
    assert sat["baseline"] == pytest.approx(600.0)


def test_store_band_respects_diversification_instead_of_summing_sku_quantiles():
    client, cid = build(net=lambda d: 20.0)
    wed = next(p for p in store(client, cid)["points"] if p["date"] == "2026-03-11")
    sigma = ((Z90 ** -1 * 2.0 * 2) ** 2 + (Z90 ** -1 * 2.0 * 5) ** 2) ** 0.5 * 0.5  # sqrt of summed variances, calibrated
    assert wed["p10"] == pytest.approx(42 - Z90 * sigma, rel=1e-3) and wed["p90"] == pytest.approx(42 + Z90 * sigma, rel=1e-3)
    assert wed["p90"] < (14 * 2 + 14 * 5) * 0.5 and wed["p10"] > (10 * 2 + 10 * 5) * 0.5  # tighter than the plain sums
    assert wed["p10"] < wed["forecast"] < wed["p90"]


def test_rows_for_the_same_sku_and_day_are_counted_once():
    class Doubled(StubForecast):
        def forecast(self, *a):
            res = super().forecast(*a)
            return ForecastResult(res.model, res.model_version, res.origin, res.rows + res.rows)
    client, cid = build(net=lambda d: 20.0, forecaster=Doubled(AS_OF))
    wed = next(p for p in store(client, cid)["points"] if p["date"] == "2026-03-11")
    assert wed["forecast"] == pytest.approx(42.0)


def test_net_sales_after_as_of_never_reach_the_baseline_or_the_calibration():
    leak = [{"date": AS_OF + timedelta(days=k), "transactions": 1, "footfall": None, "net_sales": 99999.0} for k in range(1, 30)]
    client, cid = build(net=lambda d: 20.0, flow_after=leak)
    out = store(client, cid, "2026-03-09", "2026-03-20")
    assert out["calibration"]["factor"] == pytest.approx(0.5)
    assert all(p["actual"] is None for p in out["points"] if p["date"] > "2026-03-10")
    assert next(p for p in out["points"] if p["date"] == "2026-03-17")["baseline"] == pytest.approx(20.0)


def test_file_forecast_uses_a_single_model_when_the_file_holds_several(tmp_path):
    cols = BASE_COLS
    rows = [("S030", "A", "2026-07-20", v, 1.0, 9.0, 0.0, False, m)
            for m, v in (("glm_poisson", 5.0), ("seasonal_naive", 50.0), ("ma28_weekday", 500.0))]
    f = tmp_path / "f.parquet"
    write_parquet(f, rows, cols)
    res = FileForecast(str(f)).forecast("S030", date(2026, 7, 25), None, date(2026, 7, 20), date(2026, 7, 20), [])
    assert res.model == "glm_poisson" and [r.forecast for r in res.rows] == [5.0]
