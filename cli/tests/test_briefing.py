import json

from glazed_cli.state import State

SNAP = {
    "store_id": "S030", "store_display_name": "Bayfront · Gate Area West", "as_of": "2026-03-10",
    "window": {"from": "2026-03-04", "to": "2026-03-10"},
    "kpis": {"net_sales": 4500.5, "transactions": 477, "waste_usd": 1429.6,
             "lost_sales_usd": {"low": 37.0, "mid": 383.9, "high": 503.2}, "tx_per_staff_hour": 1.83},
    "top_issues": [{"issue_id": "i1", "kind": "overstock_waste", "product_name": "Burrito", "severity_usd": 687.4,
                    "options": [{"option_id": "o1"}, {"option_id": "o2"}]}],
    "integrity": [{"issue_id": "x1", "kind": "sku_key_mismatch", "exposure_usd": 138690.36, "summary": "SKU format"}],
    "order_plan": {"due_today": [{"sku": "SKU-1", "name": "Burrito", "supplier_name": "Norte", "qty": 10,
                                  "order_deadline": "2026-03-10", "expected_loss_usd": 5.0}],
                   "due_tomorrow": [], "top_lines": [{"sku": "SKU-2", "name": "Wrap", "supplier_name": "Costa", "qty": 4,
                                                      "order_deadline": "2026-03-13", "expected_loss_usd": 18.0}]},
    "suppliers": [{"supplier_id": "SUP01", "supplier_name": "Norte", "on_time_pct": 93.6, "fill_pct": 100.0,
                   "next_delivery": "2026-03-11"}],
    "pending_proposals": [], "recent_decisions": [], "generated_at": "2026-10-10T10:00:00+00:00", "cache_age_s": 12}
BRIEF = {"snapshot": SNAP, "suggested_focus": ["i1"], "headline": [
    {"key": "waste_7d", "text": "Merma 7 días $1,430", "value": 1429.6, "unit": "USD", "source": "kpis"},
    {"key": "orders_due_today", "text": "1 pedidos vencen hoy", "value": 1, "unit": "pedidos", "source": "order_plan"}]}


def test_briefing_renders_headline_and_snapshot_tables(api, run):
    State(current_case="c1").save()
    api.on("GET", "/api/v1/cases/c1/briefing", BRIEF)
    r = run("briefing")
    assert r.exit_code == 0, r.output
    for text in ("Merma 7 días $1,430", "kpis", "overstock_waste", "687.40", "sku_key_mismatch", "SKU-1", "SKU-2",
                 "Norte", "2026-03-11", "Bayfront"):
        assert text in r.output
    assert "cache 12s" in r.output


def test_briefing_json_is_the_raw_payload(api, run):
    State(current_case="c1").save()
    api.on("GET", "/api/v1/cases/c1/briefing", BRIEF)
    r = run("--json", "briefing")
    assert r.exit_code == 0 and json.loads(r.output) == BRIEF


def test_briefing_accepts_an_explicit_case(api, run):
    api.on("GET", "/api/v1/cases/c9/briefing", BRIEF)
    assert run("briefing", "--case", "c9").exit_code == 0
