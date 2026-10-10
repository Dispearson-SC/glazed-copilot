from datetime import date

from tests.helpers import make_world, rows
from tests.test_dimensions_core import _log_has


def S(d, units="3", price="2.0", gross=None, disc="0", net=None, store="S001", sku="SKU-100001", promo=""):
    g = gross if gross is not None else (f"{float(units) * float(price):.2f}" if units not in ("", None) else "0")
    n = net if net is not None else f"{float(g) - float(disc):.2f}"
    return {"date": d, "store_id": store, "sku": sku, "units_sold": units, "unit_price": price,
            "gross_sales": g, "discount_amount": disc, "net_sales": n, "promo_id": promo}


def clean(tmp_path, sales):
    con, log = make_world(tmp_path, sales_daily=sales)
    return con, log


def test_keys_normalized_and_typed(tmp_path):
    con, _ = clean(tmp_path, [S("01/05/2026", store="s001 ", sku="sku100001")])
    assert rows(con, "select date, store_id, sku, units_sold, net_sales, is_return, units_source, dq_flags from sales_daily") == [
        (date(2026, 1, 5), "S001", "SKU-100001", 3, 6.0, False, "raw", None)]


def test_exact_duplicates_removed_conflicts_flagged_keep_first(tmp_path):
    con, log = clean(tmp_path, [
        S("2026-01-05"), S("2026-01-05"),                        # exact dup
        S("2026-01-06", units="10"), S("2026-01-06", units="13"),  # conflicting
    ])
    assert rows(con, "select date, units_sold, dq_flags from sales_daily order by date") == [
        (date(2026, 1, 5), 3, None), (date(2026, 1, 6), 10, "conflicting_duplicate")]
    assert _log_has(log, "sales_daily", "SD01", "excluded", 2)
    assert _log_has(log, "sales_daily", "SD02", "flagged", 1)


def test_orphans_excluded(tmp_path):
    con, log = clean(tmp_path, [S("2026-01-05"), S("2026-01-05", sku="SKU-700001"), S("2026-01-05", store="S077")])
    assert rows(con, "select count(*) from sales_daily") == [(1,)]
    assert _log_has(log, "sales_daily", "SD03", "excluded", 1)
    assert _log_has(log, "sales_daily", "SD04", "excluded", 1)


def test_sales_outside_open_windows_excluded(tmp_path):
    con, log = clean(tmp_path, [
        S("2026-01-05"),                         # ok
        S("2026-01-09"),                         # S001 closure window
        S("2026-01-05", store="S002"),           # S002 opens 2026-01-10
        S("2026-01-20", store="S003"),           # S003 closed from 2026-01-20
    ])
    assert rows(con, "select count(*) from sales_daily") == [(1,)]
    assert _log_has(log, "sales_daily", "SD05", "excluded", 3)


def test_units_reconstructed_from_gross_and_price(tmp_path):
    con, log = clean(tmp_path, [
        S("2026-01-05", units="", gross="8.00", net="8.00"),     # null units
        S("2026-01-06", units="40", gross="8.00", net="8.00"),   # x10 outlier
        S("2026-01-07", units="3", gross="7.50", net="7.50"),    # mismatch we cannot attribute: keep, flag
    ])
    got = rows(con, "select date, units_sold, units_source, dq_flags from sales_daily order by date")
    assert got[0] == (date(2026, 1, 5), 4, "derived_from_gross", None)
    assert got[1] == (date(2026, 1, 6), 4, "corrected_x10", None)
    assert got[2] == (date(2026, 1, 7), 3, "raw", "gross_ne_units_x_price")
    assert _log_has(log, "sales_daily", "SD06", "fixed", 1)
    assert _log_has(log, "sales_daily", "SD07", "fixed", 1)
    assert _log_has(log, "sales_daily", "SD09", "flagged", 1)


def test_negative_units_are_returns(tmp_path):
    con, log = clean(tmp_path, [S("2026-01-05", units="-3", gross="-6.00", net="-6.00")])
    assert rows(con, "select units_sold, net_sales, is_return from sales_daily") == [(-3, -6.0, True)]
    assert _log_has(log, "sales_daily", "SD08", "flagged", 1)


def test_net_recomputed_and_discount_capped(tmp_path):
    con, log = clean(tmp_path, [
        S("2026-01-05", units="5", gross="10.00", disc="2.00", net="11.00"),    # net != gross - discount
        S("2026-01-06", units="5", gross="10.00", disc="15.00", net="10.00"),   # discount > gross
        S("2026-01-07", units="5", gross="10.00", disc="1.00", net="9.00"),     # fine
    ])
    assert rows(con, "select date, discount_amount, net_sales, dq_flags from sales_daily order by date") == [
        (date(2026, 1, 5), 2.0, 8.0, "net_recomputed"),
        (date(2026, 1, 6), 10.0, 0.0, "discount_capped;net_recomputed"),
        (date(2026, 1, 7), 1.0, 9.0, None)]
    assert _log_has(log, "sales_daily", "SD10", "fixed", 2)
    assert _log_has(log, "sales_daily", "SD11", "fixed", 1)


def test_invalid_promo_nulled(tmp_path):
    con, log = clean(tmp_path, [S("2026-01-05", promo="PR999"), S("2026-01-06", promo="PR001")])
    assert rows(con, "select date, promo_id, dq_flags from sales_daily order by date") == [
        (date(2026, 1, 5), None, "invalid_promo"), (date(2026, 1, 6), "PR001", None)]
    assert _log_has(log, "sales_daily", "SD12", "fixed", 1)
