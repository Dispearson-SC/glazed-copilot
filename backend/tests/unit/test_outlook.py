"""C6: GET /cases/{id}/outlook?days=2 and the internal twin."""
from datetime import date, timedelta

import pytest

from tests.fakes import make_series
from tests.unit.manager_support import AS_OF, START, build, dates_after, prod

D1, D2 = (AS_OF + timedelta(days=i) for i in (1, 2))


def flow_rows(extra=()):
    rows, d = [], START
    while d <= AS_OF:
        tx = 100 + d.isoweekday() * 10
        rows.append({"date": d, "transactions": tx, "footfall": 400, "net_sales": tx * 8.0})
        d += timedelta(days=1)
    return rows + list(extra)


def configure(on_hand=3, pos=(), extra_flow=()):
    def conf(m):
        m.flow = flow_rows(extra_flow)
        m.series = [make_series("A", 2.0, START, AS_OF, lambda d: 10, closing=lambda d: on_hand),
                    make_series("DEAD", 9.0, START, AS_OF - timedelta(days=60), lambda d: 10)]
        m.catalog = {"A": prod("Alpha", price=2.0), "DEAD": prod("Dead", price=9.0)}
        m.pos = list(pos)
        m.leak = bool(extra_flow)
    return conf


def outlook(client, cid, **params):
    r = client.get(f"/api/v1/cases/{cid}/outlook", params=params)
    assert r.status_code == 200, r.text
    out = r.json()
    out["days"] = [d for d in out["days"] if d["projected"]]  # today / past days are covered by their own test
    return out


def test_shape_envelope_and_days_start_tomorrow():
    client, cid, _ = build(configure())
    out = outlook(client, cid)
    assert out["as_of"] == "2026-07-19" and out["store_id"] == "S030" and out["source"] and out["store_display_name"]
    assert [d["date"] for d in out["days"]] == [D1.isoformat(), D2.isoformat()]
    day = out["days"][0]
    assert day["projected"] is True and day["weather"] is None and day["weather_note"] == "Sin pronóstico"
    for k in ("net_sales", "transactions", "avg_ticket", "expected_waste_usd", "expected_lost_sales_usd"):
        assert set(day[k]) == {"low", "mid", "high"}, k
    assert day["transactions"]["mid"] == pytest.approx(110.0)  # Monday
    assert day["avg_ticket"]["mid"] == pytest.approx(8.0)
    assert day["net_sales"]["low"] <= day["net_sales"]["mid"] <= day["net_sales"]["high"]


def test_lost_sales_come_from_stock_vs_forecast_and_skip_inactive_skus():
    client, cid, _ = build(configure(on_hand=3))
    d1, d2 = outlook(client, cid)["days"]
    assert d1["expected_lost_sales_usd"]["mid"] == pytest.approx((10 - 3) * 2.0)   # 7 units short on day 1
    assert d2["expected_lost_sales_usd"]["mid"] == pytest.approx(10 * 2.0)         # nothing left on day 2


def test_a_scheduled_delivery_removes_the_loss_it_covers():
    po = {"po_id": "PO1", "supplier_id": "SUP01", "supplier_name": "S", "sku": "A", "product_name": "Alpha", "qty": 100,
          "unit_cost": 1.0, "order_date": AS_OF - timedelta(days=1), "expected_date": D2, "received_date": None}
    client, cid, _ = build(configure(on_hand=3, pos=[po]))
    d1, d2 = outlook(client, cid)["days"]
    assert d1["expected_lost_sales_usd"]["mid"] == pytest.approx(14.0) and d2["expected_lost_sales_usd"]["mid"] == 0.0


def test_waste_matches_the_expiring_view_by_day():
    def conf(m):
        configure()(m)
        m.series = [make_series("F", 5.0, START, AS_OF, lambda d: 10, shelf_life=2, closing=lambda d: 30 if d == AS_OF else 50,
                                received=lambda d: 20 if AS_OF - timedelta(days=1) <= d <= AS_OF else 0)]
        m.catalog = {"F": prod("Fresh", cost=2.0, life=2)}
    client, cid, _ = build(conf)
    exp = client.get(f"/api/v1/cases/{cid}/expiring", params={"days": 2}).json()["by_day"]
    days = outlook(client, cid)["days"]
    for d in days:
        want = next((x["waste_usd"] for x in exp if x["date"] == d["date"]), {"low": 0.0, "mid": 0.0, "high": 0.0})
        assert d["expected_waste_usd"] == want
    assert sum(d["expected_waste_usd"]["high"] for d in days) > 0


def test_days_validation_and_no_look_ahead():
    leak = [{"date": AS_OF + timedelta(days=i), "transactions": 9999, "footfall": 1, "net_sales": 999999.0} for i in range(1, 4)]
    client, cid, _ = build(configure(extra_flow=leak))
    for bad in (0, 8):
        assert client.get(f"/api/v1/cases/{cid}/outlook", params={"days": bad}).status_code == 400
    out = outlook(client, cid, days=3)
    assert len(out["days"]) == 3 and all(d["transactions"]["mid"] < 1000 for d in out["days"])
    assert dates_after({k: v for k, v in out.items() if k != "days"}) == []
    assert all(d["projected"] for d in out["days"])


def test_internal_twin_matches_public():
    client, cid, _ = build(configure())
    r = client.get("/internal/v1/outlook", headers={"X-Glazed-Case": cid}, params={"days": 2})
    pub = client.get(f"/api/v1/cases/{cid}/outlook", params={"days": 2}).json()
    assert r.status_code == 200 and r.json() == pub


def test_today_and_yesterday_are_backtests_with_actual():
    client, cid, _ = build(configure())
    r = client.get(f"/api/v1/cases/{cid}/outlook")
    assert r.status_code == 200
    days = r.json()["days"]
    assert [d["date"] for d in days][:3] == ["2026-07-18", "2026-07-19", D1.isoformat()]
    today = days[1]
    assert today["is_today"] is True and today["forecast_kind"] == "backtest" and today["projected"] is False
    assert "net_sales" in today["actual"] and "vs_forecast_pct" in today
    assert days[2]["forecast_kind"] == "forward"
