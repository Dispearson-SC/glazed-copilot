"""P2: transfer options routes, the proposal of an option, and the transfer issue."""
from tests.unit.copilot_support import SID, option, stockout_issue, with_issues
from glazed_backend.metrics.transfers import transfer_issue_options
from datetime import date

RANGE = {"low": 1.0, "mid": 2.0, "high": 3.0}
OPT = {"option_id": "tr1", "sku": "A", "product_name": "Prod A", "from_store": SID, "to_store": "S031", "to_store_name": "Near",
       "qty": 8, "surplus_units": 9.0, "deficit_units": 12.0, "transfer_cost_usd": 15.8, "waste_avoided_usd": RANGE,
       "lost_sales_avoided_usd": RANGE, "net_usd": RANGE, "confidence": {"score": 0.3, "calibrated": False},
       "expires_on": "2026-07-20", "rationale_es": "x"}


def transfer_issue():
    iid = f"{SID}|transfer_opportunity|A"
    opts = transfer_issue_options(iid, [OPT], date(2026, 7, 19), 5.0)
    for o in opts:
        o["confidence"], o["tier"] = {"score": 0.3, "n_backtest": 0, "method": "uncalibrated"}, "N3"
    return {"issue_id": iid, "kind": "transfer_opportunity", "category": "operational", "sku": "A", "product_name": "Prod A",
            "store_id": SID, "as_of": "2026-07-19", "as_of_date": "2026-07-19", "severity_usd": 5.0, "evidence": [],
            "data_caveats": [], "options": opts, "recommended_option_id": "tr1", "engine_version": "glazed_metrics_v1"}


def env(with_option=True):
    client, cid, m = with_issues(transfer_issue(), configure=lambda m: setattr(m, "transfers", {
        "options": [OPT] if with_option else [], "do_nothing": {"expected_waste_usd": RANGE}, "assumptions": {"x": 1}, "reason": "no_surplus", "reason_es": "sin sobrante"}))
    return client, cid, {"X-Glazed-Case": cid}


def test_options_internal_and_public_twin():
    client, cid, h = env()
    a = client.get("/internal/v1/transfers/options", params={"sku": "A", "limit": 3}, headers=h).json()
    b = client.get(f"/api/v1/cases/{cid}/transfers/options").json()
    assert a["options"][0]["option_id"] == "tr1" and a["do_nothing"]["expected_waste_usd"] == RANGE and a["store_id"] == SID
    assert b["options"] == a["options"]
    assert client.get("/internal/v1/transfers/options", params={"sku": "ZZ"}, headers=h).json()["options"] == []
    assert client.get("/internal/v1/transfers/options", params={"limit": 0}, headers=h).status_code == 400


def test_empty_options_carry_a_reason():
    client, cid, h = env(with_option=False)
    out = client.get("/internal/v1/transfers/options", headers=h).json()
    assert out["options"] == [] and out["reason"] == "no_surplus"


def test_proposal_is_pending_transfer_stock_and_idempotent():
    client, cid, h = env()
    r = client.post("/internal/v1/transfers/proposals", json={"option_id": "tr1", "rationale": "sobra aquí"},
                    headers={**h, "Idempotency-Key": "k1"})
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["status"] == "pending" and p["action_type"] == "transfer_stock" and p["params"]["to_store"] == "S031"
    assert p["issue_id"] == f"{SID}|transfer_opportunity|A" and p["rationale"] == "sobra aquí"
    again = client.post("/internal/v1/transfers/proposals", json={"option_id": "tr1"}, headers={**h, "Idempotency-Key": "k1"})
    assert again.status_code == 200 and again.json()["proposal_id"] == p["proposal_id"]
    assert client.post("/internal/v1/transfers/proposals", json={"option_id": "nope"}, headers=h).status_code == 404


def test_transfer_issue_is_pending_and_labelled_in_spanish():
    client, cid, h = env()
    pend = client.get(f"/api/v1/cases/{cid}/decisions/pending").json()
    item = next(a for a in pend["approvals"] if a["kind"] == "transfer_opportunity")
    assert item["recommendation"]["action_type"] == "transfer_stock" and "Trasladar 8 unidades de Prod A a Near" in item["recommendation"]["label"]
    an = client.get(f"/api/v1/cases/{cid}/issues/{item['issue_id']}/analysis").json()
    assert an["title"].startswith("Oportunidad de traslado")


def test_transfer_issue_becomes_a_spanish_labelled_liaison_alert():
    from glazed_backend import application as uc
    client, cid, h = env()
    c = client.container
    uc.AdvanceSimClock(c.cases, c.alerts, c.metrics).detect(cid)
    (a,) = [x for x in client.get("/api/v1/alerts", params={"store_id": SID}).json() if x["issue"]["kind"] == "transfer_opportunity"]
    assert a["kind_label_es"] == "Oportunidad de traslado" and a["title_es"] == "Oportunidad de traslado: Prod A" and a["agent_id"] == "liaison"
