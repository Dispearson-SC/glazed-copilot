from datetime import date

from tests.helpers import make_world, rows
from tests.test_dimensions_core import _log_has


def I(d, o="0", r="0", u="0", e="0", m="0", c=None, oo="0", so="0", store="S001", sku="SKU-100001"):
    calc = float(o) + float(r) - float(u) - float(e) - float(m)
    return {"date": d, "store_id": store, "sku": sku, "opening_qty": o, "received_qty": r, "units_sold": u,
            "expired_qty": e, "damaged_qty": m, "closing_qty": c if c is not None else f"{calc:g}",
            "on_order_qty": oo, "stockout_hours": so}


def run(tmp_path, inv, **extra):
    return make_world(tmp_path, inventory_daily=inv, **extra)


def test_keys_normalized_duplicates_orphans_and_closure_days(tmp_path):
    con, log = run(tmp_path, [
        I("2026-01-05", r="10", u="3"), I("2026-01-05", r="10", u="3"),            # exact duplicate
        I("2026-01-05", store="s001 ", sku="sku100002", r="5"),                    # normalised keys
        I("2026-01-05", store="S077"),                                             # orphan store
        I("2026-01-09", r="4"),                                                    # S001 closure window
    ])
    assert rows(con, "select store_id, sku from inventory_daily order by sku") == [("S001", "SKU-100001"), ("S001", "SKU-100002")]
    assert _log_has(log, "inventory_daily", "IV01", "excluded", 1)
    assert _log_has(log, "inventory_daily", "IV02", "excluded", 1)
    assert _log_has(log, "inventory_daily", "IV03", "excluded", 1)


def test_identity_recomputed_and_negative_stock_clamped(tmp_path):
    con, log = run(tmp_path, [
        I("2026-01-05", r="10", u="3", c="7"),            # ok
        I("2026-01-06", o="7", u="2", c="9"),             # identity broken -> 5
        I("2026-01-07", o="5", u="8", c="-3"),            # calc -3 -> clamp 0, raw negative
    ])
    got = rows(con, "select date, closing_qty, closing_qty_raw, identity_ok, dq_flags from inventory_daily order by date")
    assert got == [
        (date(2026, 1, 5), 7, 7.0, True, "cold_start_week"),
        (date(2026, 1, 6), 5, 9.0, False, "cold_start_week;closing_recomputed"),
        (date(2026, 1, 7), 0, -3.0, True, "cold_start_week;closing_clamped"),
    ]
    assert _log_has(log, "inventory_daily", "IV04", "fixed", 1)
    assert _log_has(log, "inventory_daily", "IV05", "flagged", 1)
    assert _log_has(log, "inventory_daily", "IV10", "flagged", 1)


def test_stockout_hours_capped_at_open_hours(tmp_path):
    kpis = [{"store_id": "S001", "date": "2026-01-02", "open_hours": "16"}]
    con, log = run(tmp_path, [I("2026-01-15", so="30.5"), I("2026-01-16", so="12")], store_daily_kpis=kpis)
    assert rows(con, "select stockout_hours, dq_flags from inventory_daily order by date") == [
        (16.0, "stockout_hours_capped"), (12.0, None)]
    assert _log_has(log, "inventory_daily", "IV06", "fixed", 1)


def test_opening_vs_previous_closing_and_nonperishable_expiry_flagged(tmp_path):
    con, log = run(tmp_path, [
        I("2026-01-15", r="10", u="3"),                  # closing 7
        I("2026-01-16", o="6", u="1"),                   # opening 6 != 7
        I("2026-01-15", sku="SKU-100002", r="10", e="2"),  # expiry on non-perishable SKU
    ])
    flags = {(r[0], r[1]): r[2] for r in rows(con, "select sku, date, dq_flags from inventory_daily")}
    assert flags[("SKU-100001", date(2026, 1, 16))] == "opening_ne_prev_closing"
    assert flags[("SKU-100002", date(2026, 1, 15))] == "expired_on_nonperishable"
    assert _log_has(log, "inventory_daily", "IV07", "flagged", 1)
    assert _log_has(log, "inventory_daily", "IV08", "flagged", 1)
