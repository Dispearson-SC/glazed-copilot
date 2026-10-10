from glazed_etl import dimensions as dim
from glazed_etl.dq import DQLog
from tests.helpers import make_con, rows
from tests.test_dimensions_core import _log_has


def P(sku, **kw):
    base = {"sku": sku, "product_name": "Plain Donut", "department": "Bakery", "category": "Bakery",
            "subcategory": "Breakfast Pastry", "brand": "House Brand", "supplier_id": "SUP01",
            "unit_cost": "0.5", "list_price_base": "2.0", "case_size": "12", "shelf_life_days": "1",
            "is_perishable": "1", "storage_type": "Ambient", "inventory_tracked": "1", "is_seasonal": "0",
            "launch_date": "2024-01-01", "discontinued_date": "", "status": "Active"}
    base.update(kw)
    return base


def build(tmp_path, products, **facts):
    con = make_con(tmp_path, products=products, **facts)
    log = DQLog()
    dim.build_products(con, log)
    return con, log


def test_sku_normalized_and_types_cast(tmp_path):
    con, _ = build(tmp_path, [P(" sku-100001 "), P("SKU100002", is_perishable="0", unit_cost="1.25")])
    assert rows(con, "select sku, unit_cost, is_perishable, inventory_tracked, case_size, launch_date::varchar "
                     "from products order by sku") == [
        ("SKU-100001", 0.5, True, True, 12, "2024-01-01"),
        ("SKU-100002", 1.25, False, True, 12, "2024-01-01")]


def test_duplicates_survivor_prefers_valid_cost_and_clean_name(tmp_path):
    con, log = build(tmp_path, [
        P("SKU-100003", product_name="CREAM", unit_cost="0.0"),
        P("sku-100003", product_name="Cream", unit_cost="0.4"),
        P("SKU-100004", product_name="Latte", unit_cost="0.63"),
        P("SKU-100004", product_name="Latte", unit_cost="0.51"),  # both valid -> first row wins
    ])
    assert rows(con, "select sku, product_name, unit_cost from products order by sku") == [
        ("SKU-100003", "Cream", 0.4), ("SKU-100004", "Latte", 0.63)]
    assert _log_has(log, "products", "PD01", "excluded", 2)


def test_category_casing_and_cross_department_values_fixed(tmp_path):
    prods = [P(f"SKU-1000{i:02d}") for i in range(10, 16)]  # 6 solid Bakery/Bakery/Breakfast Pastry rows
    prods += [P("SKU-100020", category="BAKERY "), P("SKU-100021", category="Grab & Go"),
              P("SKU-100022", department="Beverage", category="Coffee & Tea", subcategory="Hot Tea")]
    con, log = build(tmp_path, prods)
    cats = dict(rows(con, "select sku, category from products"))
    assert cats["SKU-100020"] == "Bakery"
    assert cats["SKU-100021"] == "Bakery"  # contradicts dominant category of (Bakery, Breakfast Pastry)
    assert cats["SKU-100022"] == "Coffee & Tea"  # tiny group: untouched
    assert _log_has(log, "products", "PD02", "fixed", 1)
    assert _log_has(log, "products", "PD03", "fixed", 1)


def test_missing_cost_imputed_from_po_then_subcategory_ratio(tmp_path):
    prods = [
        P("SKU-100030", unit_cost="0.0"),                                     # PO median available
        P("SKU-100031", unit_cost="", subcategory="Dessert Pastry", list_price_base="4.0"),  # ratio route
        P("SKU-100032", subcategory="Dessert Pastry", unit_cost="1.0", list_price_base="4.0"),  # ratio 0.25
        P("SKU-100033", unit_cost="0.0", list_price_base="0.0", subcategory="Cookies"),         # unknowable
    ]
    pos = [{"po_id": f"PO{i}", "sku": "SKU-100030", "unit_cost": c} for i, c in enumerate(["0.30", "0.50", "0", "0.40"])]
    con, log = build(tmp_path, prods, purchase_orders=pos)
    got = {r[0]: r[1:] for r in rows(con, "select sku, unit_cost, unit_cost_source, dq_flags from products")}
    assert got["SKU-100030"][:2] == (0.40, "po_median")
    assert got["SKU-100031"][:2] == (1.0, "subcategory_ratio")
    assert got["SKU-100033"][:2] == (None, "unknown")
    assert "unit_cost_imputed" in got["SKU-100030"][2]
    assert "unit_cost_unknown" in got["SKU-100033"][2]
    assert got["SKU-100032"][1] == "raw"
    assert _log_has(log, "products", "PD04", "fixed", 2)
    assert _log_has(log, "products", "PD05", "flagged", 1)


def test_zero_list_price_nulled_and_inverted_lifecycle_flagged(tmp_path):
    con, log = build(tmp_path, [P("SKU-100040", list_price_base="0.0", launch_date="2024-12-01", discontinued_date="2024-06-01",
                                  status="Discontinued")])
    flags = rows(con, "select list_price_base, dq_flags from products")[0]
    assert flags[0] is None
    assert "list_price_missing" in flags[1] and "discontinued_before_launch" in flags[1]
    assert _log_has(log, "products", "PD06", "flagged", 1)


def test_sold_sku_missing_from_master_is_inferred(tmp_path, monkeypatch):
    sales = [{"date": f"2026-01-{d:02d}", "store_id": "S001", "sku": "SKU-100099", "unit_price": "4.0"} for d in range(1, 5)]
    sales += [{"date": "2026-01-01", "store_id": "S001", "sku": "SKU-700001", "unit_price": "9.0"}]  # random orphan
    pos = [{"po_id": "PO1", "sku": "SKU-100099", "supplier_id": "SUP03", "unit_cost": "1.5"},
           {"po_id": "PO2", "sku": "SKU-100099", "supplier_id": "SUP03", "unit_cost": "2.5"}]
    monkeypatch.setattr(dim, 'INFER_MIN_SALE_DAYS', 3)
    con, log = build(tmp_path, [P("SKU-100001")], sales_daily=sales, purchase_orders=pos)
    r = rows(con, "select sku, inferred, product_name, list_price_base, unit_cost, supplier_id, department, dq_flags "
                  "from products where sku='SKU-100099'")[0]
    assert r[1] is True and r[3] == 4.0 and r[4] == 2.0 and r[5] == "SUP03"
    assert r[6] is None and "inferred_from_transactions" in r[7]
    assert rows(con, "select count(*) from products where sku='SKU-700001'") == [(0,)]
    assert rows(con, "select inferred from products where sku='SKU-100001'") == [(False,)]
    assert _log_has(log, "products", "PD07", "fixed", 1)


# ---------------------------------------------------------------- barcodes
def test_barcodes_orphans_and_shared_codes(tmp_path):
    barcodes = [
        {"barcode": "111", "sku": "SKU-100001", "barcode_type": "UPC-A"},
        {"barcode": "111", "sku": "SKU-100002", "barcode_type": "UPC-A"},   # shared code
        {"barcode": "222", "sku": "SKU-999999", "barcode_type": "UPC-A"},   # SKU not in master
        {"barcode": "333", "sku": "sku-100002", "barcode_type": "EAN-13"},
        {"barcode": "333", "sku": "SKU-100002", "barcode_type": "EAN-13"},  # exact duplicate after normalization
    ]
    con = make_con(tmp_path, products=[P("SKU-100001"), P("SKU-100002")], product_barcodes=barcodes)
    log = DQLog()
    dim.build_products(con, log)
    dim.build_product_barcodes(con, log)
    assert rows(con, "select barcode, sku from product_barcodes order by 1") == [("111", "SKU-100001"), ("333", "SKU-100002")]
    assert _log_has(log, "product_barcodes", "BC01", "excluded", 1)
    assert _log_has(log, "product_barcodes", "BC02", "excluded", 1)
    assert _log_has(log, "product_barcodes", "BC03", "excluded", 1)
