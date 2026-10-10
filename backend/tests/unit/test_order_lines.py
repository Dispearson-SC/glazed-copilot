"""R3: every order-plan line carries confidence, the do-nothing comparison, the minimum-order warning, lead time and delivery."""
from glazed_backend.application.briefing import trim_line
from tests.unit.copilot_support import plan_line, stockout_issue, with_issues

DN = {"net_usd_mid": -14.0, "expected_lost_sales_usd": {"low": 6.0, "mid": 11.0, "high": 20.0},
      "expected_waste_usd": {"low": 0.0, "mid": 3.0, "high": 5.0}}
WARN = {"min_order_value": 300.0, "order_value_usd": 106.1, "suggestion": "Below the supplier minimum"}


def rich(sku, issue, **kw):
    return {**plan_line(sku, issue, **kw), "confidence": {"score": 0.61, "calibrated": True, "n_backtest": 30, "noise_capped": False},
            "do_nothing": DN, "net_usd_mid": 22.5, "lead_time_days": 2, "next_delivery_date": "2026-07-21"}


def test_briefing_line_keeps_the_new_fields_and_the_warning_object():
    a = stockout_issue("A")
    t = trim_line(rich("A", a, warn=WARN))
    assert t["confidence"] == {"score": 0.61, "calibrated": True} and t["do_nothing"] == DN
    assert t["lead_time_days"] == 2 and t["next_delivery_date"] == "2026-07-21"
    assert t["min_order_warning"] == WARN and t["below_min_order"] is True
    ok = trim_line(rich("B", stockout_issue("B")))
    assert ok["min_order_warning"] is None and ok["below_min_order"] is False


def test_pending_technical_items_carry_the_same_fields():
    a = stockout_issue("A")
    def conf(m):
        m.plan = {"suppliers": [], "lines": [rich("A", a, warn=WARN)]}
    client, cid, _ = with_issues(a, configure=conf)
    (t,) = client.get(f"/api/v1/cases/{cid}/decisions/pending").json()["technical"]
    assert t["confidence"] == {"score": 0.61, "calibrated": True} and t["do_nothing"] == DN
    assert t["lead_time_days"] == 2 and t["next_delivery_date"] == "2026-07-21"
    assert t["min_order_warning"] == WARN and "mínimo" in t["warning"]


def test_pending_technical_falls_back_to_the_issue_options_when_the_line_has_no_figures():
    a = stockout_issue("A")
    def conf(m):
        m.plan = {"suppliers": [], "lines": [plan_line("A", a)]}
    client, cid, _ = with_issues(a, configure=conf)
    (t,) = client.get(f"/api/v1/cases/{cid}/decisions/pending").json()["technical"]
    assert t["confidence"] == {"score": 0.82, "calibrated": True}
    assert t["do_nothing"]["net_usd_mid"] == -120.0  # cost of inaction of the issue's do_nothing option
