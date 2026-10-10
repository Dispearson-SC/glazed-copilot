from glazed_backend.application.copilot import _dedupe_by_sku_action
from glazed_backend.metrics.issues import merge_same_action


def _issue(kind, score, n, sev=10.0):
    iid = f"S001|{kind}|SKU-1"
    return {"issue_id": iid, "kind": kind, "sku": "SKU-1", "store_id": "S001", "severity_usd": sev,
            "evidence": [{"metric": kind, "period": "p"}, {"metric": "shared", "period": "p"}], "data_caveats": [kind],
            "recommended_option_id": iid + "|o",
            "options": [{"option_id": iid + "|o", "action_type": "skip_order", "params": {"sku": "SKU-1", "typical_qty": 12},
                         "confidence": {"score": score, "n_backtest": n}}]}


def test_same_action_merges_into_calibrated_primary():
    out = merge_same_action([_issue("inflated_order", 0.3, 0), _issue("overstock_waste", 0.83, 12)])
    assert len(out) == 1
    p = out[0]
    assert p["issue_id"] == "S001|overstock_waste|SKU-1"
    assert p["kinds"] == ["overstock_waste", "inflated_order"]
    assert p["merged_issue_ids"] == ["S001|inflated_order|SKU-1"]
    assert [e["metric"] for e in p["evidence"]] == ["overstock_waste", "shared", "inflated_order"]


def test_different_action_is_not_merged():
    b = _issue("expiring", 0.5, 3)
    b["options"][0]["action_type"] = "markdown_end_of_day"
    assert len(merge_same_action([_issue("inflated_order", 0.3, 0), b])) == 2


def test_approval_duplicate_of_technical_is_linked():
    tech = [{"issue_id": "i1", "sku": "SKU-1", "action_type": "skip_order"}]
    appr = [{"issue_id": "i2", "sku": "SKU-1", "recommendation": {"action_type": "skip_order"}}]
    a, t = _dedupe_by_sku_action(appr, tech)
    assert a == [] and t[0]["linked_issue_ids"] == ["i2"]


def test_skip_order_and_a_downward_adjust_of_the_same_sku_merge():
    from glazed_backend.metrics.issues import merge_same_action

    def issue(kind, action, params, score, n):
        return {"issue_id": f"S004|{kind}|SKU-1", "kind": kind, "store_id": "S004", "sku": "SKU-1", "evidence": [],
                "data_caveats": [], "severity_usd": 10.0, "recommended_option_id": "o",
                "options": [{"option_id": "o", "action_type": action, "params": params,
                             "confidence": {"score": score, "n_backtest": n}}]}
    a = issue("inflated_order", "adjust_order_qty", {"supplier_id": "SUP03", "qty": 1, "typical_qty": 10.0}, 0.3, 0)
    b = issue("overstock_waste", "skip_order", {"supplier_id": "SUP03", "typical_qty": 10.0}, 0.84, 120)
    (only,) = merge_same_action([a, b])
    assert only["issue_id"] == "S004|overstock_waste|SKU-1" and only["merged_issue_ids"] == ["S004|inflated_order|SKU-1"]
