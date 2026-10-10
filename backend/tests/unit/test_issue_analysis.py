"""C2: deterministic Spanish analysis of an issue (public route and internal twin)."""
import pytest

from glazed_backend.application.copilot import usd
from tests.unit.copilot_support import option, stockout_issue, with_issues

IID = "S030|stockout_risk|A"


def analysis(client, cid, iid=IID):
    r = client.get(f"/api/v1/cases/{cid}/issues/{iid}/analysis")
    assert r.status_code == 200, r.text
    return r.json()


def test_shape_envelope_and_recommendation_is_best_net_with_do_nothing_compared():
    client, cid, _ = with_issues(stockout_issue("A"))
    a = analysis(client, cid)
    assert a["as_of"] == "2026-07-19" and a["store_id"] == "S030" and a["source"]
    assert a["store_display_name"] == "Bayfront Municipal Airport · Gate Area West"
    assert a["recommendation"]["option_id"] == "bestA" and a["recommendation"]["action_type"] == "place_order"
    assert a["recommendation"]["params"]["qty"] == 40 and "40" in a["recommendation"]["label"]
    assert a["tier"] == "N2" and a["requires_approval"] is True and a["deadline"] == "2026-07-19"
    assert a["impact_usd"]["mid"] == 80.0 and a["impact_usd"]["low"] <= a["impact_usd"]["mid"] <= a["impact_usd"]["high"]
    assert a["confidence"] == {"score": 0.82, "calibrated": True}
    assert "Prod A" in a["title"] and a["problem"]


def test_text_is_spanish_and_cites_computed_numbers_only():
    client, cid, _ = with_issues(stockout_issue("A"))
    a = analysis(client, cid)
    d = a["dialog"]
    assert usd(120.0) in d["if_not_act"] and usd(80.0) in d["why"] and usd(80.0) in d["if_accept"]
    assert {x["option_id"] for x in d["alternatives"]} == {"altA", "dnA"}
    alt = next(x for x in d["alternatives"] if x["option_id"] == "altA")
    assert alt["net_usd_mid"] == 30.0 and alt["label"]
    assert any("proveedor" in c.lower() for c in a["cons"])  # English risk string translated
    assert a["pros"] and a["cons"]
    blob = " ".join([a["problem"], a["title"], d["why"], d["if_accept"], d["if_not_act"], *a["pros"], *a["cons"]])
    assert "Supplier" not in blob and "Expected" not in blob


def test_n1_recommendation_does_not_require_approval():
    iss = stockout_issue("B", tier="N1")
    client, cid, _ = with_issues(iss)
    a = analysis(client, cid, "S030|stockout_risk|B")
    assert a["tier"] == "N1" and a["requires_approval"] is False


def test_do_nothing_wins_when_every_action_is_negative():
    iss = stockout_issue("C")
    for o in iss["options"]:
        if o["action_type"] != "do_nothing":
            o["net_usd_mid"] = -5.0
    client, cid, _ = with_issues(iss)
    a = analysis(client, cid, "S030|stockout_risk|C")
    assert a["recommendation"]["action_type"] == "do_nothing" and a["requires_approval"] is False
    assert a["impact_usd"] == {"low": 0.0, "mid": 0.0, "high": 0.0}


def test_uncalibrated_confidence_is_flagged_and_a_con_is_added():
    iss = stockout_issue("D")
    iss["options"][0]["confidence"] = {"score": 0.5, "n_backtest": 0, "method": "backtest_replay", "noise_capped": False}
    client, cid, _ = with_issues(iss)
    a = analysis(client, cid, "S030|stockout_risk|D")
    assert a["confidence"]["calibrated"] is False
    assert any("backtest" in c.lower() for c in a["cons"])


def test_unknown_issue_is_404_and_internal_twin_matches():
    client, cid, _ = with_issues(stockout_issue("A"))
    assert client.get(f"/api/v1/cases/{cid}/issues/S030|stockout_risk|NOPE/analysis").status_code == 404
    pub = analysis(client, cid)
    r = client.get(f"/internal/v1/issues/{IID}/analysis", headers={"X-Glazed-Case": cid})
    assert r.status_code == 200 and r.json() == pub


def test_missing_prices_do_not_break_a_kind_without_a_template():
    iss = stockout_issue("E", kind="weird_kind")
    client, cid, _ = with_issues(iss)
    a = analysis(client, cid, "S030|weird_kind|E")
    assert a["title"] and a["problem"]


def test_inflated_order_with_zero_optimum_says_no_order_is_needed():
    iss = stockout_issue("F", kind="inflated_order")
    iss["evidence"] = [{"metric": "ordered_qty", "value": 12.0}, {"metric": "optimum_qty", "value": 0.0}]
    client, cid, _ = with_issues(iss)
    a = analysis(client, cid, "S030|inflated_order|F")
    assert "no hace falta pedir" in a["problem"] and "0.0" not in a["problem"]
