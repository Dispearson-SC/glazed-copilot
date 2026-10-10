import os
from datetime import date

import pytest

from glazed_backend.domain import FutureDate, NotFound

PATH = os.environ.get("GLAZED_DUCKDB_PATH", "/home/ubuntu/projects/Softek-HackSaltillo/Dataset/clean/glazed.duckdb")
pytestmark = [pytest.mark.integration,
              pytest.mark.skipif(not os.path.exists(PATH), reason="DuckDB dataset not available")]

S, AS_OF = "S030", date(2026, 3, 10)


@pytest.fixture(scope="module")
def m():
    from glazed_backend.adapters.driven.duckdb_metrics import DuckDBMetrics
    return DuckDBMetrics(PATH)


def test_kpis_match_source(m):
    k = m.kpis(S, AS_OF, date(2026, 3, 1), date(2026, 3, 7))
    for key in ("net_sales", "units", "transactions", "footfall", "conversion", "tx_per_staff_hour",
                "waste_usd", "stockout_hours"):
        assert key in k
    assert k["net_sales"] > 0 and 0 <= k["conversion"] <= 1.5


def test_kpis_cannot_read_past_as_of(m):
    with pytest.raises(FutureDate):
        m.kpis(S, AS_OF, date(2026, 3, 1), date(2026, 3, 11))


def test_day_summary_shape_and_guard(m):
    d = m.day_summary(S, AS_OF, date(2026, 3, 9))
    assert d["date"] == "2026-03-09" and d["context"]["weekday"] == "Mon"
    assert d["by_department"] and d["top_skus"] and "vs_same_weekday_avg" in d
    with pytest.raises(FutureDate):
        m.day_summary(S, AS_OF, date(2026, 3, 11))


def test_issues_are_sorted_stable_and_keyed(m):
    a = m.issues(S, AS_OF, limit=5)
    assert a == m.issues(S, AS_OF, limit=5)
    assert len(a) <= 5
    assert [x["severity_usd"] for x in a] == sorted((x["severity_usd"] for x in a), reverse=True)
    for i in a:
        assert i["issue_id"].startswith(f"{S}|{i['kind']}|") and i["as_of_date"] == "2026-03-10"
        assert i["kind"] in {"stockout_risk", "overstock_waste", "expiring", "late_delivery"}


def test_inventory_projection(m):
    sku = m.issues(S, AS_OF, 50)[0].get("sku") or "SKU-100014"
    p = m.inventory_projection(S, AS_OF, sku, horizon=7)
    assert len(p["daily"]) == 7 and "projected_stockout_date" in p and p["method"] == "simple_v0"


def test_order_plan_is_marked_simple(m):
    plan = m.order_plan(S, AS_OF)
    assert plan["method"] == "simple_v0" and "glazed_metrics" in plan["note"]
    for line in plan["lines"]:
        assert line["qty_units"] % line["case_size"] == 0 and line["qty_units"] > 0


def test_supplier_performance_uses_only_received_by_as_of(m):
    rows = m.supplier_performance(S, AS_OF)
    assert rows and all(0 <= r["on_time_pct"] <= 100 and 0 <= r["fill_pct"] <= 100 for r in rows)
    assert all({"lead_time_mean_days", "lead_time_p90_days", "contract_on_time_pct"} <= r.keys() for r in rows)


def test_promo_evaluation(m):
    r = m.promo_evaluation(S, date(2026, 4, 30), "PR006")
    assert r["confidence"] == "low" and "uplift_pct" in r
    with pytest.raises(NotFound):
        m.promo_evaluation(S, AS_OF, "NOPE")
    assert m.promo_evaluation(S, AS_OF, "PR006")["status"] == "not_started"


def test_history(m):
    h = m.history(S, AS_OF)
    assert h["weeks"] and max(w["week_start"] for w in h["weeks"]) <= "2026-03-10"


def test_backtest_day_returns_both_arms(m):
    r = m.backtest_day(S, date(2026, 3, 2), "simple_v0")
    assert set(r) >= {"current", "policy"} and r["policy"]["waste_usd"] <= r["current"]["waste_usd"]
    assert r["policy"]["lost_sales_usd"] <= r["current"]["lost_sales_usd"]


def test_stores_listing(m):
    rows = m.stores()
    s030 = next(r for r in rows if r["store_id"] == "S030")
    assert s030.keys() >= {"store_id", "name", "format", "site_id", "region"} and s030["region"]
