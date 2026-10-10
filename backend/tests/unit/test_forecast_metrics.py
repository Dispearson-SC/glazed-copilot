"""C5: GET /cases/{id}/forecast?level=store&metric=... and the internal twin."""
from datetime import date, timedelta

import pytest

from tests.fakes import make_series
from tests.unit.manager_support import AS_OF, START, build, dates_after


def flow(footfall=True, extra=()):
    rows, d = [], START
    while d <= AS_OF:
        tx = 100 + d.isoweekday() * 10
        rows.append({"date": d, "transactions": tx, "footfall": 400 + d.isoweekday() if footfall else None, "net_sales": tx * 8.0})
        d += timedelta(days=1)
    return rows + list(extra)


def configure(footfall=True, extra=()):
    def conf(m):
        m.flow = flow(footfall, extra)
        m.series = [make_series("A", 2.0, START, AS_OF, lambda d: 10)]
        m.leak = bool(extra)
    return conf


def get(client, cid, metric, **params):
    r = client.get(f"/api/v1/cases/{cid}/forecast", params={"level": "store", "metric": metric, **params})
    assert r.status_code == 200, r.text
    return r.json()


def test_transactions_points_have_the_forecast_shape_and_no_actual_after_as_of():
    client, cid, _ = build(configure())
    out = get(client, cid, "transactions", **{"from": "2026-07-15", "to": "2026-07-22"})
    assert out["metric"] == "transactions" and out["level"] == "store" and out["as_of"] == "2026-07-19" and out["source"]
    pts = {p["date"]: p for p in out["points"]}
    assert set(pts) == {f"2026-07-{d}" for d in range(15, 23)}
    for p in pts.values():
        assert {"date", "forecast", "p10", "p90", "baseline", "actual", "censored"} <= set(p)
        assert p["p10"] <= p["forecast"] <= p["p90"]
    assert pts["2026-07-18"]["actual"] == 160.0 and pts["2026-07-19"]["actual"] == 170.0   # Sat=6, Sun=7
    assert all(pts[d]["actual"] is None and pts[d]["projected"] is True for d in ("2026-07-20", "2026-07-22"))
    assert pts["2026-07-19"]["projected"] is False
    assert pts["2026-07-20"]["forecast"] == pytest.approx(110.0)  # Monday samples are all 110


def test_avg_ticket_and_footfall():
    client, cid, _ = build(configure())
    t = get(client, cid, "avg_ticket", **{"from": "2026-07-18", "to": "2026-07-20"})
    assert {p["date"]: p["actual"] for p in t["points"]}["2026-07-19"] == pytest.approx(8.0)
    assert next(p for p in t["points"] if p["date"] == "2026-07-20")["forecast"] == pytest.approx(8.0)
    f = get(client, cid, "footfall", **{"from": "2026-07-18", "to": "2026-07-20"})
    assert next(p for p in f["points"] if p["date"] == "2026-07-20")["forecast"] == pytest.approx(401.0)


def test_conversion_is_transactions_over_footfall_and_null_when_invalid():
    client, cid, _ = build(configure())
    c = get(client, cid, "conversion", **{"from": "2026-07-18", "to": "2026-07-20"})
    pts = {p["date"]: p for p in c["points"]}
    assert pts["2026-07-19"]["actual"] == pytest.approx(170 / 407, abs=1e-3)
    assert pts["2026-07-20"]["forecast"] == pytest.approx(110 / 401, abs=1e-3) and pts["2026-07-20"]["actual"] is None
    client2, cid2, _ = build(configure(footfall=False))
    c2 = get(client2, cid2, "conversion", **{"from": "2026-07-18", "to": "2026-07-20"})
    assert all(p["actual"] is None and p["forecast"] is None for p in c2["points"])
    assert c2["conversion_valid"] is False and c["conversion_valid"] is True


def test_net_sales_is_the_existing_store_forecast():
    client, cid, _ = build(configure())
    out = get(client, cid, "net_sales", **{"from": "2026-07-18", "to": "2026-07-21"})
    legacy = client.get(f"/api/v1/cases/{cid}/forecast", params={"level": "store", "from": "2026-07-18", "to": "2026-07-21"}).json()
    assert [p["forecast"] for p in out["points"]] == [p["forecast"] for p in legacy["points"]]
    assert out["metric"] == "net_sales" and out["unit"] == "usd"


def test_bad_metric_and_sku_level_are_rejected():
    client, cid, _ = build(configure())
    assert client.get(f"/api/v1/cases/{cid}/forecast", params={"level": "store", "metric": "bogus"}).status_code == 400
    assert client.get(f"/api/v1/cases/{cid}/forecast", params={"level": "sku", "sku": "A", "metric": "transactions"}).status_code == 400


def test_no_look_ahead_even_if_the_adapter_leaks_future_rows():
    leak = [{"date": AS_OF + timedelta(days=i), "transactions": 9999, "footfall": 9999, "net_sales": 99999.0} for i in range(1, 4)]
    client, cid, _ = build(configure(extra=leak))
    for metric in ("transactions", "footfall", "avg_ticket", "conversion"):
        out = get(client, cid, metric, **{"from": "2026-07-17", "to": "2026-07-22"})
        assert all(p["actual"] is None for p in out["points"] if p["date"] > "2026-07-19")
        assert dates_after({"points": [p for p in out["points"] if not p["projected"]]}) == []
        assert all((p["forecast"] or 0) < 1000 for p in out["points"])


def test_internal_twin_matches_public():
    client, cid, _ = build(configure())
    pub = get(client, cid, "transactions", **{"from": "2026-07-18", "to": "2026-07-21"})
    r = client.get("/internal/v1/forecast", headers={"X-Glazed-Case": cid},
                   params={"level": "store", "metric": "transactions", "from": "2026-07-18", "to": "2026-07-21"})
    assert r.status_code == 200 and r.json() == pub
