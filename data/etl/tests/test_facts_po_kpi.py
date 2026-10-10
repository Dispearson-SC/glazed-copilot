from datetime import date

from tests.helpers import make_world, rows
from tests.test_dimensions_core import _log_has


def PO(po="PO1", sku="SKU-100001", store="S001", sup="SUP01", od="2026-01-05", ed="2026-01-06", rd="2026-01-06",
       qo="12", qr="12", uc="0.5", status="Delivered"):
    return {"po_id": po, "store_id": store, "supplier_id": sup, "sku": sku, "order_date": od, "expected_date": ed,
            "received_date": rd, "qty_ordered": qo, "qty_received": qr, "unit_cost": uc, "status": status}


def po_world(tmp_path, pos):
    return make_world(tmp_path, purchase_orders=pos)


def test_po_duplicates_keep_status_consistent_version(tmp_path):
    con, log = po_world(tmp_path, [
        PO("PO1", qo="18", qr="12"), PO("PO1", qo="12", qr="12"),    # Delivered => received == ordered
        PO("PO2", qo="36", qr="48"), PO("PO2", qo="48", qr="48"),
    ])
    assert rows(con, "select po_id, qty_ordered, qty_received from purchase_orders order by po_id") == [("PO1", 12, 12), ("PO2", 48, 48)]
    assert _log_has(log, "purchase_orders", "PO01", "excluded", 2)


def test_po_supplier_expected_date_and_cost_imputation(tmp_path):
    con, log = po_world(tmp_path, [
        PO("PO1", sup="SUP99"),                                 # unknown supplier -> product master supplier
        PO("PO2", ed="", sku="SKU-100002", uc="0"),             # expected = order + lead time (2d); cost from master (1.0)
        PO("PO3", uc="-1"),
    ])
    got = {r[0]: r[1:] for r in rows(con, "select po_id, supplier_id, expected_date, unit_cost, dq_flags from purchase_orders")}
    assert got["PO1"][0] == "SUP01" and "supplier_corrected" in got["PO1"][3]
    assert got["PO2"][1] == date(2026, 1, 7) and got["PO2"][2] == 1.0
    assert "expected_date_imputed" in got["PO2"][3] and "unit_cost_imputed" in got["PO2"][3]
    assert got["PO3"][2] == 0.5
    assert _log_has(log, "purchase_orders", "PO02", "fixed", 1)
    assert _log_has(log, "purchase_orders", "PO03", "fixed", 1)
    assert _log_has(log, "purchase_orders", "PO09", "fixed", 2)


def test_po_dates_quantities_and_status(tmp_path):
    con, log = po_world(tmp_path, [
        PO("PO1", rd="2026-01-02"),                                  # received before ordered
        PO("PO2", qo="12", qr="14"),                                 # over-received
        PO("PO3", qo="12", qr="6"),                                  # Delivered but short
        PO("PO4", rd=""),                                            # Delivered without date
        PO("PO5", qo="0", qr="0"),                                   # invalid ordered qty
        PO("PO6", store="S077"),                                     # orphan store
        PO("PO8", status="In transit", rd="", qr=""),                # open order: nulls are legitimate
    ])
    got = {r[0]: r[1:] for r in rows(con, "select po_id, received_date, qty_received, status, dq_flags from purchase_orders")}
    assert set(got) == {"PO1", "PO2", "PO3", "PO4", "PO8"}
    assert got["PO1"][0] is None and "received_date_invalid" in got["PO1"][3]
    assert got["PO2"][1] == 12 and "qty_received_capped" in got["PO2"][3]
    assert got["PO3"][2] == "Short-shipped" and "status_reclassified" in got["PO3"][3]
    assert "delivered_without_received_date" in got["PO4"][3]
    assert got["PO8"][1] is None and got["PO8"][3] is None
    for rule, treat in [("PO04", "fixed"), ("PO05", "fixed"), ("PO06", "fixed"), ("PO07", "flagged")]:
        assert _log_has(log, "purchase_orders", rule, treat, 1), rule
    assert _log_has(log, "purchase_orders", "PO08", "excluded", 1)
    assert _log_has(log, "purchase_orders", "PO11", "excluded", 1)


def test_po_unknown_cost_flagged(tmp_path):
    prods = [{"sku": "SKU-100005", "product_name": "Z", "unit_cost": "0", "list_price_base": "0", "is_perishable": "0"}]
    con, log = make_world(tmp_path, products=prods, purchase_orders=[PO("PO1", sku="SKU-100005", uc="0")])
    assert rows(con, "select unit_cost, dq_flags from purchase_orders") == [(None, "unit_cost_unknown")]
    assert _log_has(log, "purchase_orders", "PO10", "flagged", 1)


# ---------------------------------------------------------------- KPIs
def K(d, store="S001", ff="1000", tx="100", u="170", net="800", sh="50", oh="18"):
    return {"store_id": store, "date": d, "footfall": ff, "transactions": tx, "units_sold": u, "net_sales": net,
            "staff_hours": sh, "open_hours": oh}


def test_kpi_duplicates_orphans_and_sentinels(tmp_path):
    con, log = make_world(tmp_path, store_daily_kpis=[
        K("2026-01-02"), K("2026-01-02"),                      # exact duplicate
        K("2026-01-03", store="S077"),                         # orphan
        K("2026-01-04", ff=""), K("2026-01-05", ff="0"),       # footfall missing / zero with transactions
        K("2026-01-06", ff="50", tx="80"),                     # transactions > footfall
        K("2026-01-07", sh="999"), K("2026-01-08", sh="0"), K("2026-01-12", sh="-5"),
        K("2026-01-13", net="5000"),                           # ticket 50 -> implausible
        K("2026-01-14", u="50"),                               # fewer units than transactions
    ])
    got = {r[0]: r[1:] for r in rows(con, "select date, footfall, staff_hours, conversion_valid, dq_flags from store_daily_kpis")}
    assert len(got) == 9 and date(2026, 1, 3) not in got
    assert got[date(2026, 1, 4)][0] is None and "footfall_invalid" in got[date(2026, 1, 4)][3]
    assert got[date(2026, 1, 5)][0] is None
    assert got[date(2026, 1, 6)][2] is False and "transactions_gt_footfall" in got[date(2026, 1, 6)][3]
    assert got[date(2026, 1, 7)][1] is None and "staff_hours_invalid" in got[date(2026, 1, 7)][3]
    assert got[date(2026, 1, 8)][1] is None and got[date(2026, 1, 12)][1] is None
    assert "implausible_ticket" in got[date(2026, 1, 13)][3] and "implausible_ticket" in got[date(2026, 1, 14)][3]
    assert got[date(2026, 1, 2)] == (1000, 50.0, True, None)
    for rule, treat, n in [("KP01", "excluded", 1), ("KP02", "excluded", 1), ("KP03", "fixed", 2), ("KP04", "flagged", 1),
                           ("KP05", "fixed", 3), ("KP06", "flagged", 2)]:
        assert _log_has(log, "store_daily_kpis", rule, treat, n), rule


def test_kpi_missing_days_listed(tmp_path):
    con, log = make_world(tmp_path, store_daily_kpis=[K("2026-01-02"), K("2026-01-04")],
                          stores=[{"store_id": "S001", "site_id": "ST01", "store_name": "A", "format": "x",
                                   "opened_date": "2026-01-02", "closed_date": "2026-01-05",
                                   "opening_time": "05:00", "closing_time": "21:00"}])
    assert rows(con, "select store_id, date from kpi_missing_days order by date") == [("S001", date(2026, 1, 3))]
    assert _log_has(log, "store_daily_kpis", "KP07", "flagged", 1)
