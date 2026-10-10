from datetime import date

from glazed_backend.metrics.integrity import integrity_issues, normalize_sku, scan_sales
from glazed_backend.metrics.types import Config

MASTER = {"SKU100040": "Better For You Breakfast Sandwich", "SKU-100041": "Muffin"}
SALES = [  # (store_id, sku, rows, net_sales, days)
    ("S030", "SKU-100040", 30, 1200.0, 28), ("S001", "SKU-100040", 20, 800.0, 19),
    ("S030", "SKU-100041", 50, 99.0, 40), ("S030", "SKU-712345", 2, 19.5, 2), ("S001", "SKU-799999", 1, 5.0, 1)]


def test_normalize_sku_ignores_case_dashes_spaces_and_padding():
    assert normalize_sku(" sku-100040 ") == normalize_sku("SKU100040") == "SKU100040"


def test_scan_separates_key_mismatches_from_real_orphans():
    mm, orphans = scan_sales(SALES, MASTER)
    assert [(m["sku"], m["master_sku"]) for m in mm] == [("SKU-100040", "SKU100040")]
    assert mm[0]["net_sales"] == 2000.0 and mm[0]["by_store"] == {"S030": 1200.0, "S001": 800.0}
    assert sorted(o["sku"] for o in orphans) == ["SKU-712345", "SKU-799999"] and sum(o["net_sales"] for o in orphans) == 24.5


def test_issues_are_integrity_tasks_at_tier_n2_with_store_and_chain_amounts():
    mm, orphans = scan_sales(SALES, MASTER)
    issues = integrity_issues("S030", date(2026, 9, 1), date(2026, 9, 1), mm, orphans, Config(), min_usd=0)
    kinds = {i["kind"]: i for i in issues}
    assert set(kinds) == {"sku_key_mismatch", "orphan_sku"}
    k = kinds["sku_key_mismatch"]
    assert k["category"] == "integrity" and k["integrity"] is True and k["issue_id"] == "S030|sku_key_mismatch|SKU-100040"
    ev = {e["metric"]: e["value"] for e in k["evidence"]}
    assert ev["recoverable_sales_chain_usd"] == 2000.0 and ev["recoverable_sales_store_usd"] == 1200.0
    assert [o["action_type"] for o in k["options"]] == ["data_fix_task", "do_nothing"]
    assert k["options"][0]["tier"] == "N2" and k["options"][0]["params"]["master_sku"] == "SKU100040"
    o = kinds["orphan_sku"]
    assert o["options"][0]["tier"] == "N2" and {e["metric"]: e["value"] for e in o["evidence"]}["orphan_sales_chain_usd"] == 24.5


def test_a_store_with_no_affected_rows_still_sees_the_chain_issue():
    mm, orphans = scan_sales([("S001", "SKU-100040", 20, 800.0, 19)], MASTER)
    assert integrity_issues("S030", date(2026, 9, 1), date(2026, 9, 1), mm, orphans, Config(), min_usd=0)[0]["kind"] == "sku_key_mismatch"


def test_small_key_variants_are_summarised_not_alerted():
    mm, orphans = scan_sales(SALES, MASTER)
    issues = integrity_issues("S030", date(2026, 9, 1), date(2026, 9, 1), mm, orphans, Config())  # default $10k bar
    assert [i["kind"] for i in issues] == ["orphan_sku"]
