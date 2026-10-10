"""End-to-end orchestration: raw CSV directory -> clean DuckDB / Parquet / DQ log / validation."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb

from . import dimensions, facts, loader, validate
from .dq import DQLog

CLEAN_TABLES = (
    "sites", "stores", "store_id_map", "store_closures", "store_calendar", "suppliers", "calendar", "products",
    "product_barcodes", "promotions", "prices", "sales_daily", "inventory_daily", "purchase_orders",
    "store_daily_kpis", "kpi_missing_days", "weather_daily", "dq_log",
)
RAW_TO_CLEAN = {t: t for t in loader.TABLES}

VIEWS = {
    "v_sales_enriched": """
        select s.*, p.product_name, p.department, p.category, p.subcategory, p.is_perishable,
               st.store_name, st.format, st.operator_type, si.region, si.site_type,
               c.day_of_week, c.is_weekend, c.is_holiday, c.holiday_name, c.is_school_break
        from sales_daily s join products p using (sku) join stores st using (store_id)
        join sites si on si.site_id = st.site_id join calendar c on c.date = s.date""",
    "v_demand_sales": "select * from v_sales_enriched where not is_return",
    "v_store_day": """
        select k.*, coalesce(s.net, 0) as sales_net, coalesce(s.units, 0) as sales_units,
               k.net_sales - coalesce(s.net, 0) as net_gap
        from store_daily_kpis k left join (
            select store_id, date, sum(net_sales) as net, sum(units_sold) as units from sales_daily group by 1, 2) s
        using (store_id, date)""",
    "v_store_day_weather": """
        select s.store_id, w.* from stores s join weather_daily w using (site_id)""",
    "v_inventory_waste": """
        select i.*, p.category, p.unit_cost, (i.expired_qty + i.damaged_qty) * p.unit_cost as waste_cost
        from inventory_daily i join products p using (sku)""",
}


def run(raw_dir, out_dir) -> dict:
    raw_dir, out_dir = Path(raw_dir), Path(out_dir)
    con = duckdb.connect()  # in memory: raw tables never reach the output database
    loader.load_raw(con, raw_dir)
    raw_counts = {t: con.execute(f"select count(*) from raw.{t}").fetchone()[0] for t in loader.TABLES}
    dq = DQLog()
    dimensions.build_dimensions(con, dq)
    facts.build_facts(con, dq)
    dq.write(con)
    validation = validate.run_validation(con)

    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("*.parquet"):
        stale.unlink()
    db_path = out_dir / "glazed.duckdb"
    for leftover in (db_path, out_dir / "glazed.duckdb.wal"):
        if leftover.exists():
            leftover.unlink()
    con.execute(f"attach '{db_path}' as out")
    for t in CLEAN_TABLES:
        con.execute(f"create table out.{t} as select * from {t}")
        con.execute(f"copy (select * from {t}) to '{out_dir / (t + '.parquet')}' (format parquet)")
    con.execute("use out")
    for name, sql in VIEWS.items():
        con.execute(f"create view {name} as {sql}")
    con.execute(f"copy (select * from dq_log order by table_name, rule_id) to '{out_dir / 'dq_log.csv'}' (header, delimiter ',')")
    row_counts = {t: {"raw": raw_counts[t], "clean": con.execute(f"select count(*) from {t}").fetchone()[0]}
                  for t in RAW_TO_CLEAN}
    (out_dir / "validation.json").write_text(json.dumps(validation, indent=2, sort_keys=True))
    con.execute("use memory")
    con.execute("detach out")
    con.close()
    return {"row_counts": row_counts, "validation": validation, "dq_entries": len(dq.entries), "out_dir": str(out_dir)}
