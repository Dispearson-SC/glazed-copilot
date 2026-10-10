"""Shared fixtures for the Wave 14 (decision copilot) tests: hand-made issues shaped like the glazed_metrics_v1 contract."""
from tests.unit.manager_support import AS_OF, build

SID = "S030"


def option(oid, action, net, tier, cost=0.0, score=0.8, low=None, high=None, params=None, deadline=None, reason="", risk=None):
    return {"option_id": oid, "action_type": action, "params": params if params is not None else {"sku": "A", "qty": 10},
            "expected_benefit_usd": {"low": low if low is not None else net * 0.5, "mid": net + cost,
                                     "high": high if high is not None else net * 1.5 + cost},
            "cost_usd": cost, "net_usd_mid": net, "loss_impact": {"waste_usd_delta": 0.0, "lost_sales_usd_delta": -net},
            "confidence": {"score": score, "n_backtest": 12 if action != "do_nothing" else 0,
                           "method": "backtest_replay" if action != "do_nothing" else "baseline", "noise_capped": False},
            "tier": tier, "tier_reasons": [], "urgency": {"deadline_date": deadline, "reason": reason},
            "risk": risk or [], "if_act": None, "if_not": None}


def stockout_issue(sku="A", kind="stockout_risk", severity=120.0, tier="N2"):
    iid = f"{SID}|{kind}|{sku}"
    best = option(f"best{sku}", "place_order", 80.0, tier, cost=40.0, score=0.82, deadline="2026-07-19",
                  reason="Order by 2026-07-19", risk=["Supplier late on 15% of orders."],
                  params={"sku": sku, "supplier_id": "SUP01", "qty": 40, "cases": 4, "case_size": 10})
    alt = option(f"alt{sku}", "adjust_order_qty", 30.0, "N1", cost=10.0, score=0.9, deadline="2026-07-19",
                 params={"sku": sku, "supplier_id": "SUP01", "qty": 20, "cases": 2, "case_size": 10})
    dn = option(f"dn{sku}", "do_nothing", 0.0, "N0", cost=severity, score=1.0, params={}, reason="Expected lost sales.")
    dn["cost_of_inaction_usd"] = {"mid": severity}
    return {"issue_id": iid, "kind": kind, "category": "operational", "sku": sku, "product_name": f"Prod {sku}",
            "supplier_id": "SUP01", "store_id": SID, "as_of": AS_OF.isoformat(), "as_of_date": AS_OF.isoformat(),
            "severity_usd": severity, "evidence": [], "data_caveats": [], "options": [best, alt, dn],
            "recommended_option_id": best["option_id"], "engine_version": "glazed_metrics_v1"}


def with_issues(*issues, configure=None):
    def conf(m):
        m.issues_by_date = {AS_OF: list(issues)}
        if configure:
            configure(m)
    return build(conf)
