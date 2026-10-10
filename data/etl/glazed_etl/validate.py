"""Reconciliation and integrity checks over the clean tables."""
from __future__ import annotations

PRIMARY_KEYS = {
    "sites": ["site_id"], "stores": ["store_id"], "store_closures": ["store_id", "start_date"],
    "products": ["sku"], "product_barcodes": ["barcode"], "suppliers": ["supplier_id"], "prices": ["price_id"],
    "sales_daily": ["date", "store_id", "sku"], "inventory_daily": ["date", "store_id", "sku"],
    "purchase_orders": ["po_id", "store_id", "sku"], "store_daily_kpis": ["store_id", "date"],
    "promotions": ["promo_id"], "calendar": ["date"], "store_calendar": ["store_id", "date"],
    "weather_daily": ["site_id", "date"],
}
# (child table, child column, parent table, parent column); NULL child values are allowed.
FOREIGN_KEYS = [
    ("stores", "site_id", "sites", "site_id"),
    ("store_closures", "store_id", "stores", "store_id"),
    ("products", "supplier_id", "suppliers", "supplier_id"),
    ("product_barcodes", "sku", "products", "sku"),
    ("prices", "store_id", "stores", "store_id"), ("prices", "sku", "products", "sku"),
    ("sales_daily", "store_id", "stores", "store_id"), ("sales_daily", "sku", "products", "sku"),
    ("sales_daily", "promo_id", "promotions", "promo_id"), ("sales_daily", "date", "calendar", "date"),
    ("inventory_daily", "store_id", "stores", "store_id"), ("inventory_daily", "sku", "products", "sku"),
    ("purchase_orders", "store_id", "stores", "store_id"), ("purchase_orders", "sku", "products", "sku"),
    ("purchase_orders", "supplier_id", "suppliers", "supplier_id"),
    ("store_daily_kpis", "store_id", "stores", "store_id"),
    ("weather_daily", "site_id", "sites", "site_id"),
]
MIN_RECONCILED_SHARE = 0.98


def check_primary_keys(con, keys=PRIMARY_KEYS) -> dict:
    dups = {}
    for table, cols in keys.items():
        c = ", ".join(cols)
        dups[table] = con.execute(
            f"select coalesce(sum(n - 1), 0) from (select count(*) as n from {table} group by {c} having count(*) > 1)"
        ).fetchone()[0]
    return {"ok": not any(dups.values()), "duplicates": {k: int(v) for k, v in dups.items()}}


def check_foreign_keys(con, fks=FOREIGN_KEYS) -> dict:
    orphans = {}
    for child, col, parent, pcol in fks:
        orphans[f"{child}.{col}->{parent}.{pcol}"] = con.execute(
            f"select count(*) from {child} c where c.{col} is not null and not exists "
            f"(select 1 from {parent} p where p.{pcol} = c.{col})"
        ).fetchone()[0]
    return {"ok": not any(orphans.values()), "orphans": orphans}


def check_inventory_identity(con) -> dict:
    total, broken, raw_ok = con.execute("""
        select count(*),
               count(*) filter (where closing_qty <> opening_qty + received_qty - units_sold - expired_qty - damaged_qty
                                 and (dq_flags is null or dq_flags not like '%closing_clamped%')),
               count(*) filter (where identity_ok)
        from inventory_daily""").fetchone()
    return {"ok": broken == 0, "rows": total, "identity_violations_after_cleaning": broken,
            "source_identity_holds_share": round(raw_ok / total, 4) if total else None}


def check_price_windows(con) -> dict:
    n = con.execute("""
        select count(*) from prices a join prices b on a.store_id = b.store_id and a.sku = b.sku and a.price_id < b.price_id
        and a.effective_from <= coalesce(b.effective_to, date '9999-12-31')
        and b.effective_from <= coalesce(a.effective_to, date '9999-12-31')""").fetchone()[0]
    return {"ok": n == 0, "overlapping_pairs": n}


def check_sales_vs_kpi(con) -> dict:
    row = con.execute("""
        with s as (select store_id, date, sum(net_sales) as net from sales_daily group by 1, 2)
        select count(*), count(*) filter (where abs(coalesce(s.net, 0) - k.net_sales) <= 0.01 * abs(k.net_sales) + 0.005),
               count(*) filter (where abs(coalesce(s.net, 0) - k.net_sales) <= 0.5),
               sum(coalesce(s.net, 0)), sum(k.net_sales)
        from store_daily_kpis k left join s using (store_id, date)""").fetchone()
    n, w1, w50, sales, kpi = row
    no_kpi = con.execute("""select count(*) from (select distinct store_id, date from sales_daily) s
        where not exists (select 1 from store_daily_kpis k where k.store_id = s.store_id and k.date = s.date)""").fetchone()[0]
    share = w1 / n if n else 1.0
    return {"ok": share >= MIN_RECONCILED_SHARE, "target_share": MIN_RECONCILED_SHARE, "store_days_compared": n,
            "within_1pct": w1, "within_1pct_share": round(share, 4), "within_50_cents": w50,
            "sales_net_total": round(sales or 0, 2), "kpi_net_total": round(kpi or 0, 2),
            "sales_store_days_without_kpi_row": no_kpi}


def check_weather_coverage(con) -> dict:
    """Every site must have a weather row for every calendar date."""
    expected, missing = con.execute("""
        select count(*), count(*) filter (where not exists (
                 select 1 from weather_daily w where w.site_id = s.site_id and w.date = c.date))
        from sites s cross join calendar c""").fetchone()
    return {"ok": missing == 0, "expected_site_days": expected, "missing_site_days": missing}


def run_validation(con) -> dict:
    checks = {
        "primary_keys": check_primary_keys(con), "foreign_keys": check_foreign_keys(con),
        "inventory_identity": check_inventory_identity(con), "price_windows": check_price_windows(con),
        "sales_vs_kpi": check_sales_vs_kpi(con), "weather_coverage": check_weather_coverage(con),
    }
    return {"ok": all(c["ok"] for c in checks.values()), "checks": checks}
