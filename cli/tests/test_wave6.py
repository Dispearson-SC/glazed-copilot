from glazed_cli.state import State

COMPLIANCE = [
    {"decision_id": "d1", "action_type": "place_order", "status": "approved", "applicable": True,
     "execution_status": "executed", "diagnosis": "forecast_error", "explanation": "outside range",
     "simulated": {"net_usd_mid": 100.0, "net_usd_low": 80.0, "net_usd_high": 120.0},
     "observed": {"net_usd": 40.0, "label": "backtest"}},
    {"decision_id": "d2", "action_type": "skip_order", "status": "approved", "applicable": True,
     "execution_status": "not_executed", "diagnosis": "not_executed", "explanation": "not done",
     "simulated": None, "observed": None},
]


def test_compliance_lists_decisions(api, run):
    State(current_case="c1").save()
    api.on("GET", "/api/v1/cases/c1/compliance", COMPLIANCE)
    r = run("compliance")
    assert r.exit_code == 0
    for text in ("d1", "executed", "forecast_error", "100.00", "40.00", "backtest", "d2", "not_executed"):
        assert text in r.output


def test_compliance_filters_by_decision(api, run):
    State(current_case="c1").save()
    api.on("GET", "/api/v1/cases/c1/compliance", COMPLIANCE)
    r = run("compliance", "--decision", "d2")
    assert "d2" in r.output and "d1" not in r.output


def test_compliance_unknown_decision_is_friendly(api, run):
    State(current_case="c1").save()
    api.on("GET", "/api/v1/cases/c1/compliance", COMPLIANCE)
    r = run("compliance", "--decision", "zzz")
    assert r.exit_code == 1 and "zzz" in r.output


def test_inject_not_executed(api, run):
    State(current_case="c1").save()
    api.on("POST", "/api/v1/cases/c1/inject", {"execution": {"status": "not_executed"}}, 201)
    r = run("inject", "not-executed", "p1", "--detail", "no truck")
    assert r.exit_code == 0
    assert api.last_json() == {"execution": {"proposal_id": "p1", "status": "not_executed", "detail": "no truck"}}


def test_inject_event(api, run):
    State(current_case="c1").save()
    api.on("POST", "/api/v1/cases/c1/inject", {"event": {"type": "bloqueo"}}, 201)
    r = run("inject", "event", "--type", "bloqueo", "--from", "2026-03-02", "--to", "2026-03-03", "--note", "road")
    assert r.exit_code == 0
    assert api.last_json() == {"event": {"type": "bloqueo", "date_from": "2026-03-02", "date_to": "2026-03-03", "note": "road"}}


def test_promo_audit_posts_to_the_public_route_and_renders_the_verdict(api, run):
    State(current_case="c1").save()
    api.on("POST", "/api/v1/promos/audit",
           {"verdict": "block", "recommendation": "do_nothing", "reasons": ["uplift below the noise floor"],
            "similar": [{"promo_id": "PR002"}, {"promo_id": "PR005"}], "alternative": {"promo_id": "PR009"}})
    r = run("promo-audit", "--department", "Bakery", "--discount", "15")
    assert api.last_json() == {"case_id": "c1", "department": "Bakery", "discount_pct": 15.0}
    for text in ("block", "PR002", "PR005", "PR009", "noise floor"):
        assert text in r.output


def test_alerts_table_names_new_kinds_and_shows_exposure_for_integrity(api, run):
    api.on("GET", "/api/v1/alerts", [
        {"alert_id": "a1", "alert_type": 9, "store_id": "S030", "severity_usd": 1.0, "state": "nueva", "as_of": "2026-03-01",
         "issue_key": "k", "issue": {"kind": "orphan_sku", "category": "integrity", "exposure_usd": 777.0}},
        {"alert_id": "a2", "alert_type": 21, "store_id": "S030", "severity_usd": 58.92, "state": "nueva", "as_of": "2026-03-01",
         "issue_key": "k2", "issue": {"kind": "compliance_deviation"}},
    ])
    r = run("alerts")
    assert "orphan_sku" in r.output and "exposure 777.00" in r.output and "compliance_deviation" in r.output


def test_decide_reject_shows_jev_category(api, run):
    api.on("POST", "/api/v1/proposals/p1/decision",
           {"execution_id": "e1", "proposal_id": "p1", "case_id": "c1", "source": "simulated", "status": "not_executed", "detail": ""})
    api.on("GET", "/api/v1/proposals", [{"proposal_id": "p1", "status": "rejected", "reason_category": "precio", "reason_confidence": 0.81}])
    r = run("decide", "p1", "--reject", "--reason", "muy caro")
    assert "precio" in r.output and "0.81" in r.output
