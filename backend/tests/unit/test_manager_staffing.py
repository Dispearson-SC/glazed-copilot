"""GET /api/v1/cases/{id}/staffing and /internal/v1/staffing: staff-hour recommendation from the flow forecast."""
from datetime import timedelta

import pytest

from tests.unit.manager_support import AS_OF, build, dates_after


def flow_rows(end=AS_OF, days=100):
    out, d = [], end - timedelta(days=days)
    while d <= end:
        out.append({"date": d, "transactions": 100 + d.isoweekday() * 10, "footfall": 400, "net_sales": (100 + d.isoweekday() * 10) * 8.0})
        d += timedelta(days=1)
    return out


def staff_rows(end=AS_OF, days=40):
    """Three stores of the format: ratios 2, 4 and 8 transactions per staff hour -> p50 = 4."""
    out, d = [], end - timedelta(days=days)
    while d <= end:
        out += [{"store_id": f"S{i}", "date": d, "transactions": 100, "staff_hours": h} for i, h in ((1, 50.0), (2, 25.0), (3, 12.5))]
        d += timedelta(days=1)
    return out


def configure(m):
    m.flow = flow_rows()
    m.staff = staff_rows()


def get(client, cid, **params):
    r = client.get(f"/api/v1/cases/{cid}/staffing", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_envelope_benchmark_and_daily_rows():
    client, cid, _ = build(configure)
    out = get(client, cid)
    assert out["as_of"] == "2026-07-19" and out["store_id"] == "S030" and out["source"] and out["store_display_name"]
    assert out["benchmark"]["format"] == "Shop-in-Shop" and out["benchmark"]["tx_per_staff_hour_p50"] == pytest.approx(4.0)
    assert out["note"] == "sin datos por hora"
    assert [d["date"] for d in out["days"]] == [f"2026-07-{n}" for n in range(20, 27)]
    mon = out["days"][0]  # Monday: 110 transactions every week
    assert mon["forecast_transactions"] == {"low": 110.0, "mid": 110.0, "high": 110.0}
    assert mon["recommended_staff_hours"] == {"low": 27.5, "mid": 27.5, "high": 27.5}
    assert mon["planned_staff_hours"] is None and mon["gap_hours"] is None and mon["basis"] == "daily"
    assert all(d["projected"] is True for d in out["days"])


def test_days_validation():
    client, cid, _ = build(configure)
    assert len(get(client, cid, days=3)["days"]) == 3
    for bad in (0, 15):
        assert client.get(f"/api/v1/cases/{cid}/staffing", params={"days": bad}).status_code == 400


def test_forecast_transactions_come_from_the_flow_forecast():
    def varied(m):
        configure(m)
        m.flow = [{**r, "transactions": r["transactions"] + (20 if (AS_OF - r["date"]).days // 7 % 2 else 0)} for r in flow_rows()]
    client, cid, _ = build(varied)
    mon = get(client, cid, days=1)["days"][0]["forecast_transactions"]
    assert mon["low"] < mon["mid"] < mon["high"]
    rec = get(client, cid, days=1)["days"][0]["recommended_staff_hours"]
    assert rec["low"] < rec["mid"] < rec["high"]


def test_no_look_ahead_even_if_the_adapter_leaks():
    def leaky(m):
        configure(m)
        m.leak = True
        m.flow = flow_rows(end=AS_OF + timedelta(days=30))
        m.staff = staff_rows() + [{"store_id": "S9", "date": AS_OF + timedelta(days=1), "transactions": 10000, "staff_hours": 1.0}] * 200
    client, cid, _ = build(leaky)
    clean_client, clean_cid, _ = build(configure)
    out = get(client, cid)
    assert out["benchmark"]["tx_per_staff_hour_p50"] == pytest.approx(4.0)
    assert out["days"] == get(clean_client, clean_cid)["days"]
    assert dates_after(out) == []


def test_missing_history_is_a_404():
    client, cid, _ = build(lambda m: setattr(m, "flow", flow_rows()))  # no staffing history
    assert client.get(f"/api/v1/cases/{cid}/staffing").status_code == 404
    client2, cid2, _ = build(lambda m: setattr(m, "staff", staff_rows()))  # no flow history
    assert client2.get(f"/api/v1/cases/{cid2}/staffing").status_code == 404


def test_internal_route_matches_public_and_asserts_store_and_as_of():
    client, cid, _ = build(configure)
    h = {"X-Glazed-Case": cid}
    r = client.get("/internal/v1/staffing", headers=h, params={"days": 2})
    assert r.status_code == 200 and r.json() == get(client, cid, days=2)
    assert client.get("/internal/v1/staffing", headers=h, params={"store_id": "S001"}).status_code == 400
    assert client.get("/internal/v1/staffing", headers=h, params={"as_of": "2026-07-18"}).status_code == 400
