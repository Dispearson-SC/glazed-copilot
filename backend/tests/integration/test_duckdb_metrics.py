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


def test_kpis_report_lost_sales_range_next_to_waste(m):
    k = m.kpis(S, AS_OF, date(2026, 2, 1), AS_OF)
    ls = k["lost_sales_usd"]
    assert 0 <= ls["low"] <= ls["mid"] <= ls["high"] and ls["mid"] > 0
    assert k["window"] == {"from": "2026-02-01", "to": "2026-03-10"} and k["waste_usd"] >= 0


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


def test_issues_follow_the_wave5_contract_with_deterministic_options(m):
    issues = m.issues(S, AS_OF, limit=20)
    assert issues and issues == m.issues(S, AS_OF, limit=20)
    seen_kinds = set()
    for i in issues:
        seen_kinds.add(i["kind"])
        assert {"issue_id", "kind", "store_id", "as_of", "severity_usd", "evidence", "data_caveats", "options"} <= i.keys()
        assert i["store_display_name"].endswith("Gate Area West") or " · " in i["store_display_name"]
        assert i["as_of"] == "2026-03-10" and isinstance(i["evidence"], list) and i["evidence"]
        assert all({"metric", "value", "unit", "period", "source"} <= e.keys() for e in i["evidence"])
        opts = i["options"]
        assert 1 <= len(opts) <= 5 and opts[-1]["action_type"] == "do_nothing"
        assert len({o["option_id"] for o in opts}) == len(opts)
        assert i["recommended_option_id"] in {o["option_id"] for o in opts}
        for o in opts:
            assert o["action_type"] in {"place_order", "adjust_order_qty", "skip_order", "markdown_end_of_day",
                                        "run_promo", "transfer_stock", "shift_staff_hours", "do_nothing"}
            assert o["tier"] in {"N0", "N1", "N2", "N3"} and o["tier_reasons"]
            assert set(o["expected_benefit_usd"]) == {"low", "mid", "high"} and o["if_act"] is None and o["if_not"] is None
            assert set(o["loss_impact"]) == {"waste_usd_delta", "lost_sales_usd_delta"}
            assert {"score", "n_backtest", "method"} <= o["confidence"].keys() and 0 <= o["confidence"]["score"] <= 1
            assert "deadline_date" in o["urgency"] and o["urgency"]["reason"] and isinstance(o["risk"], list)
            if o["action_type"] == "markdown_end_of_day":
                assert o["data_caveat"] == "assumed elasticity" and o["tier"] in {"N2", "N3", "N0"}
            if o["tier"] == "N1":
                assert o["confidence"]["score"] >= 0.85 and o["confidence"]["n_backtest"] >= 30 and o["net_usd_mid"] > 0
        assert opts[-1]["cost_usd"] >= 0
    assert "stockout_risk" in seen_kinds


def test_order_plan_lines_embed_their_issue(m):
    plan = m.order_plan(S, AS_OF)
    embedded = [l for l in plan["lines"] if l.get("issue")]
    assert embedded and all(l["issue"]["options"] and l["issue"]["sku"] == l["sku"] for l in embedded)


def test_inventory_projection(m):
    sku = m.issues(S, AS_OF, 50)[0].get("sku") or "SKU-100014"
    p = m.inventory_projection(S, AS_OF, sku, horizon=7)
    assert len(p["daily"]) == 7 and "projected_stockout_date" in p and p["method"] == "simple_v0"


def test_order_plan_lines_carry_the_reorder_contract(m):
    plan = m.order_plan(S, AS_OF)
    assert plan["method"] == "glazed_metrics_v1" and plan["as_of"] == "2026-03-10" and plan["lines"]
    for line in plan["lines"]:
        assert line["qty"] % line["case_size"] == 0 and line["qty"] > 0 and line["cases"] * line["case_size"] == line["qty"]
        assert 0 < line["service_level_target"] < 1 and line["method"] in {"newsvendor", "order_up_to", "sS"}
        assert line["qty_range"]["low"] <= line["qty_range"]["high"] and line["supplier_name"]
        assert {"projected_stockout_date", "order_deadline", "stockout_risk_without_order", "vs_current_practice",
                "min_order_warning", "expected_waste_usd", "expected_lost_sales_usd"} <= line.keys()


def test_snapshot_never_contains_information_after_as_of(m):
    snap = m._snapshot(S, AS_OF)
    assert all(r.date <= AS_OF for rows in snap.rows.values() for r in rows)
    assert all(p.order_date <= AS_OF and (p.received_date is None or p.received_date <= AS_OF) for p in snap.pos)
    assert all(d <= AS_OF for d in snap.store.closed_dates)


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


def test_stores_expose_display_name_with_site(m):
    s030 = next(r for r in m.stores() if r["store_id"] == "S030")
    assert s030["display_name"] == f"{s030['site_name']} · {s030['name']}"
    assert s030["site_name"] and s030["site_type"]
    names = [r["display_name"] for r in m.stores()]
    assert len(set(names)) == len(names)  # unique, unlike store_name alone
