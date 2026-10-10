from datetime import date

from glazed_etl import dimensions as dim
from glazed_etl.dq import DQLog
from tests.helpers import make_con, rows
from tests.test_dimensions_core import _log_has
from tests.test_dimensions_products import P


# ---------------------------------------------------------------- promotions
def promo(pid, start, end, **kw):
    return {"promo_id": pid, "promo_name": "x", "promo_type": "Percent Off", "start_date": start, "end_date": end,
            "discount_pct": "10", "department": "Bakery", "category": "", "region_scope": "ALL",
            "expected_uplift_pct": "20", **kw}


def test_promotions_repairs_inverted_dates_with_sales_evidence_and_flags_unapplied(tmp_path):
    sales = [{"date": d, "store_id": "S001", "sku": "SKU-100001", "promo_id": p}
             for d, p in [("2025-11-24", "PR003"), ("2025-12-24", "PR003"), ("12/20/2025", "PR003"),
                          ("2026-01-05", "PR004"), ("2026-01-06", "PR999")]]
    con = make_con(tmp_path, promotions=[
        promo("PR003", "2025-11-24", "2025-11-19"), promo("PR004", "2026-01-05", "2026-01-25"),
        promo("PR013", "2026-04-01", "2026-04-30")], sales_daily=sales)
    log = DQLog()
    dim.build_promotions(con, log)
    got = {r[0]: r[1:] for r in rows(con, "select promo_id, start_date, end_date, applied_rows, category, discount_pct, dq_flags from promotions")}
    assert got["PR003"][:3] == (date(2025, 11, 24), date(2025, 12, 24), 3)
    assert "end_date_repaired" in got["PR003"][5]
    assert got["PR004"][2] == 1 and got["PR004"][3] is None and got["PR004"][4] == 10.0 and got["PR004"][5] is None
    assert got["PR013"][2] == 0 and "never_applied" in got["PR013"][5]
    assert _log_has(log, "promotions", "PM01", "fixed", 1)
    assert _log_has(log, "promotions", "PM02", "flagged", 1)


# ---------------------------------------------------------------- prices
def prc(pid, sku, price, frm, to="", store="S001", cur="USD", upd="2025-01-01"):
    return {"price_id": pid, "store_id": store, "sku": sku, "unit_price": price, "currency": cur,
            "effective_from": frm, "effective_to": to, "price_list": "STANDARD", "last_updated": upd}


def build_prices(tmp_path, prices):
    products = [P("SKU-100001", list_price_base="2.0"), P("SKU-100002", list_price_base="2.0"),
                P("SKU-100003", list_price_base="2.0")]
    stores = [{"store_id": "S001", "site_id": "ST01", "store_name": "A", "format": "Full Counter", "opened_date": "2020-01-01"}]
    con = make_con(tmp_path, prices=prices, products=products, stores=stores, sites=[{"site_id": "ST01"}])
    log = DQLog()
    dim.build_sites(con, log)
    dim.build_stores(con, log)
    dim.build_products(con, log)
    dim.build_prices(con, log)
    return con, log


def test_prices_normalization_and_scd2_windows(tmp_path):
    con, log = build_prices(tmp_path, [
        prc("PRC1", "SKU-100001", "2.0", "2025-01-01", "2026-02-28"),
        prc("PRC2", "SKU-100001", "2.2", "03/01/2026", cur="Usd", upd="2026-03-01"),
        prc("PRC2", "SKU-100001", "2.2", "03/01/2026", cur="Usd", upd="2026-03-01"),   # duplicate price_id
        prc("PRC3", "SKU-100002", "2.0", "2025-01-01"),                                 # two open windows
        prc("PRC4", "SKU-100002", "2.1", "2026-03-01", upd="2026-03-01"),
    ])
    out = rows(con, "select price_id, unit_price, currency, effective_from, effective_to from prices order by sku, effective_from")
    assert out == [
        ("PRC1", 2.0, "USD", date(2025, 1, 1), date(2026, 2, 28)),
        ("PRC2", 2.2, "USD", date(2026, 3, 1), None),
        ("PRC3", 2.0, "USD", date(2025, 1, 1), date(2026, 2, 28)),   # truncated by the later window
        ("PRC4", 2.1, "USD", date(2026, 3, 1), None),
    ]
    assert _log_has(log, "prices", "PRC01", "fixed", 1)      # 'Usd'
    assert _log_has(log, "prices", "PRC02", "fixed", 1)      # '03/01/2026' (after dedupe)
    assert _log_has(log, "prices", "PRC03", "excluded", 1)
    assert _log_has(log, "prices", "PRC08", "fixed", 1)      # PRC3 truncated


def test_prices_orphans_and_outliers_excluded(tmp_path):
    con, log = build_prices(tmp_path, [
        prc("PRC1", "SKU-100001", "2.0", "2025-01-01"),
        prc("PRC2", "SKU-100001", "2.0", "2025-01-01", store="S099"),
        prc("PRC3", "SKU-999999", "2.0", "2025-01-01"),
        prc("PRC4", "SKU-100002", "0", "2025-01-01"),
        prc("PRC5", "SKU-100002", "-1", "2025-01-01"),
        prc("PRC6", "SKU-100002", "20.0", "2025-01-01"),      # 10x the list price
        prc("PRC7", "SKU-100002", "", "2025-01-01"),
        prc("PRC8", "SKU-100002", "2.4", "2025-01-01", upd="2025-02-01"),  # legit +20% price, same-start loser of nothing
    ])
    assert rows(con, "select price_id from prices order by 1") == [("PRC1",), ("PRC8",)]
    assert _log_has(log, "prices", "PRC04", "excluded", 1)
    assert _log_has(log, "prices", "PRC05", "excluded", 1)
    assert _log_has(log, "prices", "PRC06", "excluded", 4)


def test_prices_inverted_window_is_repaired_and_loses_same_start_conflict(tmp_path):
    con, log = build_prices(tmp_path, [
        prc("PRC8", "SKU-100003", "2.0", "2026-04-29", "2026-02-28", upd="2026-04-29"),
        prc("PRC9", "SKU-100003", "2.2", "2026-04-29", upd="2026-04-29"),
        prc("PRC10", "SKU-100001", "2.0", "2025-01-01", "2024-11-28"),   # lone inverted window -> open-ended
    ])
    assert rows(con, "select price_id, effective_to from prices order by price_id") == [("PRC10", None), ("PRC9", None)]
    assert _log_has(log, "prices", "PRC07", "fixed", 2)
    assert _log_has(log, "prices", "PRC09", "excluded", 1)


def test_prices_never_overlap_per_store_sku(tmp_path):
    con, _ = build_prices(tmp_path, [
        prc("PRC1", "SKU-100001", "2.0", "2025-01-01", "2026-06-30"),
        prc("PRC2", "SKU-100001", "2.1", "2026-03-01", "2026-12-31"),
        prc("PRC3", "SKU-100001", "2.2", "2026-05-01"),
    ])
    assert rows(con, "select price_id, effective_from, effective_to from prices order by effective_from") == [
        ("PRC1", date(2025, 1, 1), date(2026, 2, 28)),
        ("PRC2", date(2026, 3, 1), date(2026, 4, 30)),
        ("PRC3", date(2026, 5, 1), None)]


def test_build_dimensions_runs_end_to_end_on_header_only_input(tmp_path):
    con = make_con(tmp_path)
    log = DQLog()
    dim.build_dimensions(con, log)
    for t in ("sites", "suppliers", "calendar", "stores", "store_closures", "store_calendar", "products",
              "product_barcodes", "promotions", "prices"):
        assert rows(con, f"select count(*) from {t}") == [(0,)]
    assert len(log.entries) > 20
