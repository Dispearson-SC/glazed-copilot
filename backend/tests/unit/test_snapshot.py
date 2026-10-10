from datetime import date, timedelta  # noqa: F401

from tests.unit.snapshot_support import AS_OF, RichMetrics, env, mkcase, snap  # noqa: F401


def test_snapshot_has_the_contract_shape_and_a_seven_day_window(env):
    client, _, _ = env
    s = snap(client, mkcase(client))
    assert set(s) == {"store_id", "store_display_name", "as_of", "window", "kpis", "top_issues", "integrity",
                      "order_plan", "suppliers", "pending_proposals", "other_cases_pending_count", "recent_decisions", "generated_at", "cache_age_s",
                      "calendar", "as_of_weekday_es"}
    assert s["as_of"] == "2026-03-10" and s["window"] == {"from": "2026-03-04", "to": "2026-03-10"}
    assert set(s["kpis"]) == {"net_sales", "transactions", "waste_usd", "lost_sales_usd", "tx_per_staff_hour"}
    assert set(s["order_plan"]) >= {"due_today", "due_tomorrow", "top_lines"}
    assert s["store_display_name"].startswith("Bayfront")


def test_top_issues_are_operational_sorted_capped_and_trimmed(env):
    client, _, _ = env
    s = snap(client, mkcase(client))
    ti = s["top_issues"]
    assert [i["severity_usd"] for i in ti] == sorted((i["severity_usd"] for i in ti), reverse=True)
    assert len(ti) == 5 and all(i.get("category") != "integrity" for i in ti)
    assert all(len(i["evidence"]) <= 3 and i["options"] for i in ti)
    conf = ti[0]["options"][0]["confidence"]
    assert "effect_mean_usd" not in conf and "noise_floor_usd" not in conf and conf["score"] == 0.8


def test_snapshot_issues_can_be_proposed_without_calling_issues(env):
    client, c, _ = env
    cid = mkcase(client)
    s = snap(client, cid)
    i = s["top_issues"][0]
    r = client.post("/internal/v1/proposals", headers={"X-Glazed-Case": cid},
                    json={"issue_id": i["issue_id"], "option_id": i["options"][0]["option_id"]})
    assert r.status_code == 201, r.text


def test_integrity_is_top_three_by_exposure(env):
    client, _, _ = env
    s = snap(client, mkcase(client))
    assert [x["exposure_usd"] for x in s["integrity"]] == [5000.0, 4000.0, 3000.0]
    assert set(s["integrity"][0]) >= {"kind", "exposure_usd", "summary"}


def test_order_plan_splits_by_deadline_and_ranks_by_expected_loss(env):
    client, _, _ = env
    op = snap(client, mkcase(client))["order_plan"]
    assert [x["sku"] for x in op["due_today"]] == ["A", "B"]
    assert [x["sku"] for x in op["due_tomorrow"]] == ["C"]
    assert [x["sku"] for x in op["top_lines"]] == ["C", "E", "F", "B", "G"]
    assert "issue" not in op["top_lines"][0] and "sensitivity" not in op["top_lines"][0]


def test_suppliers_carry_next_delivery(env):
    client, _, _ = env
    s = snap(client, mkcase(client))["suppliers"]
    assert s[0] == {"supplier_id": "SUP01", "supplier_name": "Norte", "on_time_pct": 93.6, "fill_pct": 100.0,
                    "next_delivery": "2026-03-11"}


def test_pending_is_this_case_and_decisions_are_case_first_then_store(env):
    client, _, _ = env
    a, b = mkcase(client), mkcase(client)
    ia = snap(client, a)["top_issues"][0]
    ib = snap(client, b)["top_issues"][1]
    pa = client.post("/internal/v1/proposals", headers={"X-Glazed-Case": a},
                     json={"issue_id": ia["issue_id"], "option_id": ia["options"][0]["option_id"]}).json()
    pb = client.post("/internal/v1/proposals", headers={"X-Glazed-Case": b},
                     json={"issue_id": ib["issue_id"], "option_id": ib["options"][0]["option_id"]}).json()
    s = snap(client, a)
    assert [(p["proposal_id"], p["scope"]) for p in s["pending_proposals"]] == [(pa["proposal_id"], "this_case")]
    assert s["other_cases_pending_count"] == 1
    client.post(f"/api/v1/proposals/{pa['proposal_id']}/decision", json={"approved": True, "reason": "ok"})
    s = snap(client, a)
    assert s["pending_proposals"] == [] and s["other_cases_pending_count"] == 1
    assert [(d["proposal_id"], d["status"]) for d in s["recent_decisions"]] == [(pa["proposal_id"], "approved")]


def test_payload_stays_under_the_size_bound(env):
    client, _, _ = env
    cid = mkcase(client)
    assert len(client.get("/internal/v1/snapshot", headers={"X-Glazed-Case": cid}).content) < 25_000
    assert len(client.get("/internal/v1/briefing", headers={"X-Glazed-Case": cid}).content) < 26_000
