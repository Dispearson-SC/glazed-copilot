"""Read the raw CSVs (untrusted, read-only) into the ``raw`` schema as text."""
from __future__ import annotations

from pathlib import Path

from . import normalize

TABLES = (
    "sites", "stores", "store_closures", "products", "product_barcodes", "suppliers",
    "prices", "sales_daily", "inventory_daily", "purchase_orders", "store_daily_kpis",
    "promotions", "calendar", "weather_daily",
)

# normalizer kind -> [(table, column)] whose distinct raw values feed the lookup map.
_MAP_SOURCES = {
    "store": [(t, "store_id") for t in (
        "stores", "store_closures", "prices", "sales_daily", "inventory_daily",
        "purchase_orders", "store_daily_kpis")],
    "sku": [(t, "sku") for t in (
        "products", "product_barcodes", "prices", "sales_daily", "inventory_daily", "purchase_orders")],
    "date": [
        ("sales_daily", "date"), ("inventory_daily", "date"), ("store_daily_kpis", "date"),
        ("calendar", "date"), ("weather_daily", "date"), ("prices", "effective_from"), ("prices", "effective_to"),
        ("prices", "last_updated"), ("purchase_orders", "order_date"),
        ("purchase_orders", "expected_date"), ("purchase_orders", "received_date"),
        ("promotions", "start_date"), ("promotions", "end_date"),
        ("stores", "opened_date"), ("stores", "closed_date"),
        ("store_closures", "start_date"), ("store_closures", "end_date"),
        ("products", "launch_date"), ("products", "discontinued_date"),
    ],
    "currency": [("prices", "currency")],
    "name": [("stores", "store_name"), ("products", "product_name"), ("sites", "site_name"),
             ("suppliers", "supplier_name"), ("promotions", "promo_name"),
             ("products", "category")],
    "time": [("stores", "opening_time"), ("stores", "closing_time")],
}


def load_raw(con, raw_dir) -> None:
    """Create ``raw.<table>`` (all VARCHAR, plus ``_rn`` = file order) and the SQL normalizers."""
    raw_dir = Path(raw_dir)
    con.execute("create schema if not exists raw")
    for table in TABLES:
        path = raw_dir / f"{table}.csv"
        if not path.is_file():
            raise FileNotFoundError(f"missing raw table file: {path}")
        con.execute(
            f"create or replace table raw.{table} as "
            "select row_number() over () as _rn, * "
            "from read_csv(?, all_varchar=true, header=true, delim=',', quote='\"')",
            [str(path)],
        )
    normalize.register_normalizers(con)
    for kind, sources in _MAP_SOURCES.items():
        for table, col in sources:
            values = [r[0] for r in con.execute(f"select distinct {col} from raw.{table}").fetchall()]
            normalize.populate(con, kind, values)
