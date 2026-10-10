"""Test helpers: build tiny raw CSV directories and DuckDB connections."""
from __future__ import annotations

import csv
from pathlib import Path

import duckdb

from glazed_etl import loader

HEADERS = {
    "sites": "site_id,site_name,site_type,region,traffic_tier",
    "stores": "store_id,site_id,store_name,format,operator_type,opening_time,closing_time,opened_date,closed_date,sqft,seats",
    "store_closures": "store_id,start_date,end_date,reason",
    "products": "sku,product_name,department,category,subcategory,brand,supplier_id,unit_cost,list_price_base,case_size,shelf_life_days,is_perishable,storage_type,inventory_tracked,is_seasonal,launch_date,discontinued_date,status",
    "product_barcodes": "barcode,sku,barcode_type",
    "suppliers": "supplier_id,supplier_name,category_focus,standard_lead_time_days,contract_fill_rate,contract_on_time_rate,min_order_value,delivery_days",
    "prices": "price_id,store_id,sku,unit_price,currency,effective_from,effective_to,price_list,last_updated",
    "sales_daily": "date,store_id,sku,units_sold,unit_price,gross_sales,discount_amount,net_sales,promo_id",
    "inventory_daily": "date,store_id,sku,opening_qty,received_qty,units_sold,expired_qty,damaged_qty,closing_qty,on_order_qty,stockout_hours",
    "purchase_orders": "po_id,store_id,supplier_id,sku,order_date,expected_date,received_date,qty_ordered,qty_received,unit_cost,status",
    "store_daily_kpis": "store_id,date,footfall,transactions,units_sold,net_sales,staff_hours,open_hours",
    "promotions": "promo_id,promo_name,promo_type,start_date,end_date,discount_pct,department,category,region_scope,expected_uplift_pct",
    "weather_daily": "site_id,date,temp_max_c,temp_min_c,precip_mm",
    "calendar": "date,day_of_week,iso_week,month,year,quarter_idx,is_weekend,is_holiday,holiday_name,is_school_break",
}


def make_raw(tmp_path: Path, **tables: list[dict]) -> Path:
    """Write all 14 raw CSVs; unspecified tables are header-only."""
    raw = tmp_path / "raw"
    raw.mkdir()
    for name, header in HEADERS.items():
        cols = header.split(",")
        with open(raw / f"{name}.csv", "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(cols)
            for row in tables.get(name, []):
                writer.writerow([row.get(c, "") for c in cols])
    return raw


def make_con(tmp_path: Path, **tables: list[dict]):
    con = duckdb.connect()
    loader.load_raw(con, make_raw(tmp_path, **tables))
    return con


def rows(con, sql: str) -> list[tuple]:
    return con.execute(sql).fetchall()


def calendar_rows(start="2026-01-01", end="2026-01-31"):
    from datetime import date, timedelta

    d, stop, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= stop:
        out.append({"date": d.isoformat()})
        d += timedelta(days=1)
    return out


def make_world(tmp_path, **tables):
    """Dimensions (2 sites, 3 stores, 3 SKUs, 2 promos, calendar Jan-2026) + caller supplied facts, fully built."""
    from glazed_etl import dimensions, facts
    from glazed_etl.dq import DQLog

    base = dict(
        sites=[{"site_id": "ST01"}],
        stores=[
            {"store_id": "S001", "site_id": "ST01", "store_name": "A", "format": "Full Counter", "opened_date": "2020-01-01",
             "opening_time": "05:00", "closing_time": "21:00"},
            {"store_id": "S002", "site_id": "ST01", "store_name": "B", "format": "Express Kiosk", "opened_date": "2026-01-10",
             "opening_time": "05:00", "closing_time": "21:00", "sqft": "50"},
            {"store_id": "S003", "site_id": "ST01", "store_name": "C", "format": "Shop-in-Shop", "opened_date": "2020-01-01",
             "closed_date": "2026-01-20", "opening_time": "00:00", "closing_time": "00:00", "sqft": "70"},
        ],
        store_closures=[{"store_id": "S001", "start_date": "2026-01-09", "end_date": "2026-01-10", "reason": "Renovation"}],
        suppliers=[{"supplier_id": "SUP01", "standard_lead_time_days": "2"}],
        products=[
            {"sku": "SKU-100001", "product_name": "A", "department": "Bakery", "category": "Bakery", "subcategory": "x",
             "supplier_id": "SUP01", "unit_cost": "0.5", "list_price_base": "2.0", "is_perishable": "1", "inventory_tracked": "1"},
            {"sku": "SKU-100002", "product_name": "B", "department": "Bakery", "category": "Bakery", "subcategory": "x",
             "supplier_id": "SUP01", "unit_cost": "1.0", "list_price_base": "4.0", "is_perishable": "0", "inventory_tracked": "1"},
        ],
        promotions=[{"promo_id": "PR001", "start_date": "2026-01-01", "end_date": "2026-01-31", "discount_pct": "10"}],
        calendar=calendar_rows(),
    )
    base.update(tables)
    con = make_con(tmp_path, **base)
    log = DQLog()
    dimensions.build_dimensions(con, log)
    facts.build_facts(con, log)
    return con, log
