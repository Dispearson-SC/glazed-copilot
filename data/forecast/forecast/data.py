"""Read the cleaned parquet tables (read-only) and assemble the modelling panel."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from forecast import panel as P

TABLES = [
    "sales_daily", "inventory_daily", "store_calendar", "calendar",
    "products", "stores", "sites", "promotions",
]


def load_tables(clean_dir) -> dict[str, pd.DataFrame]:
    clean = Path(clean_dir)
    con = duckdb.connect()
    out = {}
    for t in TABLES:
        f = clean / f"{t}.parquet"
        if not f.exists():
            raise FileNotFoundError(f"missing clean table: {f}")
        out[t] = con.execute("select * from read_parquet(?)", [str(f)]).df()
    con.close()
    return out


def build_model_panel(tables: dict[str, pd.DataFrame], frac: float = 0.8):
    """Returns (panel, cutoff, last_day). Panel covers the shared span of sales and inventory."""
    spans = [
        (tables[t]["date"].min(), tables[t]["date"].max()) for t in ("sales_daily", "inventory_daily")
    ]
    lo, hi = P.shared_span(spans)
    cutoff = P.compute_cutoff(lo, hi, frac)
    sales = tables["sales_daily"]
    inv = tables["inventory_daily"]
    sales = sales[(pd.to_datetime(sales["date"]) >= lo) & (pd.to_datetime(sales["date"]) <= hi)]
    inv = inv[(pd.to_datetime(inv["date"]) >= lo) & (pd.to_datetime(inv["date"]) <= hi)]
    base = P.build_panel(sales, inv, tables["store_calendar"])
    base = base[base["date"] <= hi]
    panel = P.add_static_features(
        base, tables["calendar"], tables["products"], tables["stores"], tables["sites"], tables["promotions"]
    )
    return panel, cutoff, hi, lo
