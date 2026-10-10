"""Fact tables. Same contract as ``dimensions``: raw.* in, clean table + DQ log entries out."""
from __future__ import annotations

from .dq import DQLog

_EPS = 0.011  # tolerance for 2-decimal money arithmetic


def build_sales(con, dq: DQLog) -> None:
    con.execute("""
        create or replace temp table _s_n as
        select _rn, norm_date(date) as d, map_store(store_id) as store_id, norm_sku(sku) as sku,
               try_cast(units_sold as double) as u, try_cast(unit_price as double) as p,
               try_cast(gross_sales as double) as g, try_cast(discount_amount as double) as disc,
               try_cast(net_sales as double) as n, nullif(upper(trim(promo_id)), '') as promo_id
        from raw.sales_daily
    """)
    dq.add_sql(con, "sales_daily", "SD00", "Unparseable date", "excluded", "select count(*) from _s_n where d is null")
    dq.add_sql(con, "sales_daily", "SD04", "Sales for a store that is not in stores (after id normalization / merge)",
               "excluded", "select count(*) from _s_n where d is not null and (store_id is null or store_id not in (select store_id from stores))")
    dq.add_sql(con, "sales_daily", "SD03", "Sales for a SKU that is not in products (random SKU-7xxxxx orphans)", "excluded",
               "select count(*) from _s_n where d is not null and store_id in (select store_id from stores) "
               "and (sku is null or sku not in (select sku from products))",
               "These rows are absent from store_daily_kpis totals.")
    con.execute("""
        create or replace temp table _s_o as
        select * from _s_n where d is not null and store_id in (select store_id from stores)
          and sku in (select sku from products)
    """)
    con.execute("""
        create or replace temp table _s_conf as
        select d, store_id, sku from _s_o group by all
        having count(*) > 1 and count(distinct (coalesce(u, -999999), p, g, disc, n, coalesce(promo_id, ''))) > 1
    """)
    con.execute("""
        create or replace temp table _s_d as
        select * exclude (rk) from (select *, row_number() over (partition by d, store_id, sku order by _rn) as rk from _s_o)
        where rk = 1
    """)
    dq.add_sql(con, "sales_daily", "SD01", "Duplicate (date, store, sku) rows", "excluded",
               "select (select count(*) from _s_o) - (select count(*) from _s_d)", "Kept the first occurrence.")
    dq.add_sql(con, "sales_daily", "SD02", "Duplicate keys whose copies disagree on units / amounts", "flagged",
               "select count(*) from _s_conf", "First copy kept (these all fall on closure days in the source data).")
    dq.add_sql(con, "sales_daily", "SD05", "Sales while the store was not trading (before opening, closure window, after closure)",
               "excluded", "select count(*) from _s_d d join store_calendar c on c.store_id = d.store_id and c.date = d.d where c.status <> 'open'")
    con.execute("""
        create or replace temp table _s_t as
        select d.*, (c.d is not null) as is_conflict from _s_d d
        join store_calendar sc on sc.store_id = d.store_id and sc.date = d.d and sc.status = 'open'
        left join _s_conf c on c.d = d.d and c.store_id = d.store_id and c.sku = d.sku
    """)
    con.execute(f"""
        create or replace temp table _s_u as
        select *,
               case when u is null and p > 0 then 'derived_from_gross'
                    when u > 0 and p > 0 and g > 0 and u * p / g between 9.5 and 10.5 then 'corrected_x10'
                    else 'raw' end as units_source
        from _s_t
    """)
    con.execute("""
        create or replace temp table _s_f as
        select *, case when units_source <> 'raw' then round(g / p)::integer else u::integer end as units_final,
               case when g > 0 and disc > g + 0.011 then g else disc end as disc_final
        from _s_u
    """)
    dq.add_sql(con, "sales_daily", "SD06", "units_sold null", "fixed",
               "select count(*) from _s_f where units_source = 'derived_from_gross'", "units = round(gross_sales / unit_price).")
    dq.add_sql(con, "sales_daily", "SD07", "units_sold ~10x the amount implied by gross / price", "fixed",
               "select count(*) from _s_f where units_source = 'corrected_x10'", "units = round(gross_sales / unit_price).")
    dq.add_sql(con, "sales_daily", "SD08", "Negative units (returns)", "flagged",
               "select count(*) from _s_f where units_final < 0", "Kept with is_return = true; exclude from demand, keep in net sales (KPIs include them).")
    dq.add_sql(con, "sales_daily", "SD09", "gross_sales != units x unit_price", "flagged",
               f"select count(*) from _s_f where units_source = 'raw' and abs(g - units_final * p) > {_EPS}",
               "Kept as reported (the invoiced gross is trusted); likely a price different from the one recorded.")
    dq.add_sql(con, "sales_daily", "SD11", "discount_amount greater than gross_sales", "fixed",
               "select count(*) from _s_f where disc_final <> disc", "Discount capped at gross_sales.")
    dq.add_sql(con, "sales_daily", "SD10", "net_sales != gross_sales - discount_amount", "fixed",
               f"select count(*) from _s_f where abs(n - (g - disc_final)) > {_EPS}", "net_sales = gross_sales - discount (the store KPIs follow this identity).")
    dq.add_sql(con, "sales_daily", "SD12", "promo_id not present in promotions (e.g. PR999)", "fixed",
               "select count(*) from _s_f where promo_id is not null and promo_id not in (select promo_id from promotions)",
               "promo_id set to NULL.")
    con.execute(f"""
        create or replace table sales_daily as
        select d as date, store_id, sku, units_final as units_sold, p as unit_price, g as gross_sales,
               disc_final as discount_amount, round(g - disc_final, 2) as net_sales,
               case when promo_id in (select promo_id from promotions) then promo_id end as promo_id,
               units_final < 0 as is_return, units_source,
               nullif(concat_ws(';',
                   case when is_conflict then 'conflicting_duplicate' end,
                   case when units_source = 'raw' and abs(g - units_final * p) > {_EPS} then 'gross_ne_units_x_price' end,
                   case when disc_final <> disc then 'discount_capped' end,
                   case when abs(n - (g - disc_final)) > {_EPS} then 'net_recomputed' end,
                   case when promo_id is not null and promo_id not in (select promo_id from promotions) then 'invalid_promo' end), '') as dq_flags,
               _rn as src_row
        from _s_f order by d, store_id, sku
    """)


def build_inventory(con, dq: DQLog) -> None:
    con.execute("""
        create or replace temp table _i_n as
        select _rn, norm_date(date) as d, map_store(store_id) as store_id, norm_sku(sku) as sku,
               try_cast(opening_qty as double) as o, try_cast(received_qty as double) as r,
               try_cast(units_sold as double) as u, try_cast(expired_qty as double) as e,
               try_cast(damaged_qty as double) as m, try_cast(closing_qty as double) as c,
               try_cast(on_order_qty as double) as oo, try_cast(stockout_hours as double) as so
        from raw.inventory_daily
    """)
    valid = ("d is not null and store_id in (select store_id from stores) and sku in (select sku from products) "
             "and o is not null and r is not null and u is not null and e is not null and m is not null and c is not null")
    dq.add_sql(con, "inventory_daily", "IV02", "Row for an unknown store / SKU, or with unparseable date / quantities", "excluded",
               f"select count(*) from _i_n where not coalesce(({valid}), false)")
    con.execute(f"""
        create or replace temp table _i_d as
        select * exclude (rk) from (select *, row_number() over (partition by d, store_id, sku order by _rn) as rk
                                    from _i_n where {valid}) where rk = 1
    """)
    dq.add_sql(con, "inventory_daily", "IV01", "Duplicate (date, store, sku) rows", "excluded",
               f"select (select count(*) from _i_n where {valid}) - (select count(*) from _i_d)", "Exact duplicates; first kept.")
    dq.add_sql(con, "inventory_daily", "IV03", "Inventory rows on days the store was closed (temporary closure window)", "excluded",
               "select count(*) from _i_d d join store_calendar c on c.store_id = d.store_id and c.date = d.d where c.status <> 'open'",
               "Includes receptions recorded during closures.")
    con.execute("""
        create or replace temp table _i_c as
        select d.*, d.o + d.r - d.u - d.e - d.m as calc, abs(d.c - (d.o + d.r - d.u - d.e - d.m)) <= 0.001 as identity_ok,
               greatest(d.o + d.r - d.u - d.e - d.m, 0) as closing_final,
               coalesce(st.typical_open_hours, 24) as open_cap, p.is_perishable
        from _i_d d
        join store_calendar sc on sc.store_id = d.store_id and sc.date = d.d and sc.status = 'open'
        join stores st on st.store_id = d.store_id join products p on p.sku = d.sku
    """)
    dq.add_sql(con, "inventory_daily", "IV04", "closing_qty != opening + received - sold - expired - damaged", "fixed",
               "select count(*) from _i_c where not identity_ok", "closing_qty recomputed from the identity; source value kept in closing_qty_raw.")
    dq.add_sql(con, "inventory_daily", "IV05", "Negative closing_qty in the source", "flagged", "select count(*) from _i_c where c < 0")
    dq.add_sql(con, "inventory_daily", "IV10", "Identity yields negative stock (sold more than available)", "flagged",
               "select count(*) from _i_c where calc < 0", "closing_qty clamped to 0 (flag closing_clamped); identity then no longer holds for the row.")
    dq.add_sql(con, "inventory_daily", "IV06", "stockout_hours above the store's open hours (up to 60 h in a day)", "fixed",
               "select count(*) from _i_c where so > open_cap", "Capped at the store's typical open hours (24 if unknown).")
    dq.add_sql(con, "inventory_daily", "IV08", "Expired quantity on a non-perishable SKU", "flagged",
               "select count(*) from _i_c where e > 0 and not coalesce(is_perishable, false)", "Kept; review product master (is_perishable).")
    con.execute("""
        create or replace temp table _i_l as
        select *, lag(closing_final) over w as prev_closing, lag(d) over w as prev_d
        from _i_c window w as (partition by store_id, sku order by d)
    """)
    dq.add_sql(con, "inventory_daily", "IV07", "opening_qty differs from the previous day's closing_qty", "flagged",
               "select count(*) from _i_l where prev_d = d - 1 and o <> prev_closing", "Stock discontinuity (transfers / counts); not corrected.")
    con.execute("""
        create or replace table inventory_daily as
        select d as date, store_id, sku, o::integer as opening_qty, r::integer as received_qty, u::integer as units_sold,
               e::integer as expired_qty, m::integer as damaged_qty, closing_final::integer as closing_qty,
               c as closing_qty_raw, identity_ok, oo::integer as on_order_qty, least(so, open_cap) as stockout_hours,
               nullif(concat_ws(';',
                   case when d < (select min(date) from calendar) + 7 then 'cold_start_week' end,
                   case when not identity_ok then 'closing_recomputed' end,
                   case when calc < 0 then 'closing_clamped' end,
                   case when so > open_cap then 'stockout_hours_capped' end,
                   case when prev_d = d - 1 and o <> prev_closing then 'opening_ne_prev_closing' end,
                   case when e > 0 and not coalesce(is_perishable, false) then 'expired_on_nonperishable' end), '') as dq_flags
        from _i_l order by d, store_id, sku
    """)


def build_purchase_orders(con, dq: DQLog) -> None:
    con.execute("""
        create or replace temp table _p_n as
        select _rn, trim(po_id) as po_id, map_store(store_id) as store_id, upper(trim(supplier_id)) as supplier_id,
               norm_sku(sku) as sku, norm_date(order_date) as od, norm_date(expected_date) as ed,
               norm_date(received_date) as rd, try_cast(qty_ordered as double) as qo, try_cast(qty_received as double) as qr,
               try_cast(unit_cost as double) as uc, trim(status) as status
        from raw.purchase_orders
    """)
    valid = "po_id is not null and od is not null and store_id in (select store_id from stores) and sku in (select sku from products)"
    dq.add_sql(con, "purchase_orders", "PO11", "PO line for an unknown store / SKU or without order date", "excluded",
               f"select count(*) from _p_n where not coalesce(({valid}), false)")
    con.execute(f"""
        create or replace temp table _p_d as
        select * exclude (rk) from (
            select *, row_number() over (partition by po_id, store_id, sku order by
                (not ((status = 'Delivered' and qr = qo) or (status = 'Short-shipped' and qr < qo) or status = 'In transit')), _rn) as rk
            from _p_n where {valid}) where rk = 1
    """)
    dq.add_sql(con, "purchase_orders", "PO01", "Duplicate PO line (same po_id, store, sku) with different quantities", "excluded",
               f"select (select count(*) from _p_n where {valid}) - (select count(*) from _p_d)",
               "Kept the copy consistent with its status (Delivered => received = ordered; Short-shipped => received < ordered), else the first.")
    dq.add_sql(con, "purchase_orders", "PO08", "qty_ordered <= 0 or null", "excluded", "select count(*) from _p_d where qo is null or qo <= 0")
    con.execute("create or replace temp table _p_v as select * from _p_d where qo > 0")
    con.execute("""
        create or replace temp table _p_f as
        select v.*, case when v.supplier_id in (select supplier_id from suppliers) then v.supplier_id else pr.supplier_id end as sup_final,
               pr.unit_cost as master_cost
        from _p_v v join products pr on pr.sku = v.sku
    """)
    dq.add_sql(con, "purchase_orders", "PO02", "supplier_id not in suppliers (e.g. SUP99)", "fixed",
               "select count(*) from _p_f where sup_final is distinct from supplier_id", "Replaced by the supplier of the SKU in the product master.")
    dq.add_sql(con, "purchase_orders", "PO03", "expected_date null", "fixed", "select count(*) from _p_f where ed is null",
               "expected_date = order_date + supplier standard lead time.")
    dq.add_sql(con, "purchase_orders", "PO04", "received_date earlier than order_date", "fixed", "select count(*) from _p_f where rd < od",
               "received_date set to NULL (not invented).")
    dq.add_sql(con, "purchase_orders", "PO05", "qty_received greater than qty_ordered", "fixed", "select count(*) from _p_f where qr > qo", "Capped at qty_ordered.")
    dq.add_sql(con, "purchase_orders", "PO06", "Delivered line received short", "fixed",
               "select count(*) from _p_f where status = 'Delivered' and qr < qo", "Status reclassified to Short-shipped.")
    dq.add_sql(con, "purchase_orders", "PO07", "Delivered line without received_date", "flagged",
               "select count(*) from _p_f where status = 'Delivered' and rd is null")
    dq.add_sql(con, "purchase_orders", "PO09", "unit_cost null, 0 or negative", "fixed",
               "select count(*) from _p_f where coalesce(uc, 0) <= 0 and master_cost > 0", "Imputed from the product master unit_cost.")
    dq.add_sql(con, "purchase_orders", "PO10", "unit_cost invalid and product cost unknown", "flagged",
               "select count(*) from _p_f where coalesce(uc, 0) <= 0 and coalesce(master_cost, 0) <= 0", "Left NULL.")
    con.execute("""
        create or replace table purchase_orders as
        select f.po_id, f.store_id, f.sup_final as supplier_id, f.sku, f.od as order_date,
               coalesce(f.ed, f.od + s.standard_lead_time_days::integer) as expected_date,
               case when f.rd < f.od then null else f.rd end as received_date,
               f.qo::integer as qty_ordered, case when f.qr is not null then least(f.qr, f.qo)::integer end as qty_received,
               case when f.uc > 0 then f.uc when f.master_cost > 0 then f.master_cost end as unit_cost,
               case when f.status = 'Delivered' and f.qr < f.qo then 'Short-shipped' else f.status end as status,
               nullif(concat_ws(';',
                   case when f.sup_final is distinct from f.supplier_id then 'supplier_corrected' end,
                   case when f.ed is null then 'expected_date_imputed' end,
                   case when f.rd < f.od then 'received_date_invalid' end,
                   case when f.qr > f.qo then 'qty_received_capped' end,
                   case when f.status = 'Delivered' and f.qr < f.qo then 'status_reclassified' end,
                   case when f.status = 'Delivered' and f.rd is null then 'delivered_without_received_date' end,
                   case when coalesce(f.uc, 0) <= 0 and f.master_cost > 0 then 'unit_cost_imputed' end,
                   case when coalesce(f.uc, 0) <= 0 and coalesce(f.master_cost, 0) <= 0 then 'unit_cost_unknown' end), '') as dq_flags
        from _p_f f left join suppliers s on s.supplier_id = f.sup_final
        order by f.od, f.po_id
    """)


def build_store_daily_kpis(con, dq: DQLog) -> None:
    con.execute("""
        create or replace temp table _k_n as
        select _rn, map_store(store_id) as store_id, norm_date(date) as d, try_cast(footfall as double) as ff,
               try_cast(transactions as double) as tx, try_cast(units_sold as double) as u, try_cast(net_sales as double) as n,
               try_cast(staff_hours as double) as sh, try_cast(open_hours as double) as oh
        from raw.store_daily_kpis
    """)
    valid = "d is not null and store_id in (select store_id from stores)"
    dq.add_sql(con, "store_daily_kpis", "KP02", "KPI row for an unknown store or unparseable date", "excluded",
               f"select count(*) from _k_n where not coalesce(({valid}), false)")
    con.execute(f"""
        create or replace temp table _k_d as
        select * exclude (rk) from (select *, row_number() over (partition by store_id, d order by _rn) as rk
                                    from _k_n where {valid}) where rk = 1
    """)
    dq.add_sql(con, "store_daily_kpis", "KP01", "Duplicate (store, date) rows", "excluded",
               f"select (select count(*) from _k_n where {valid}) - (select count(*) from _k_d)", "Exact duplicates; first kept.")
    con.execute("""
        create or replace temp table _k_t as
        select k.* from _k_d k join store_calendar c on c.store_id = k.store_id and c.date = k.d and c.status = 'open'
    """)
    dq.add_sql(con, "store_daily_kpis", "KP08", "KPI row on a day the store was not trading", "excluded",
               "select (select count(*) from _k_d) - (select count(*) from _k_t)")
    dq.add_sql(con, "store_daily_kpis", "KP03", "footfall null or 0", "fixed", "select count(*) from _k_t where ff is null or ff <= 0",
               "footfall set to NULL (not imputed); excluded from conversion metrics.")
    dq.add_sql(con, "store_daily_kpis", "KP04", "transactions greater than footfall", "flagged",
               "select count(*) from _k_t where ff > 0 and tx > ff", "conversion_valid = false.")
    dq.add_sql(con, "store_daily_kpis", "KP05", "staff_hours <= 0 or the 999 sentinel", "fixed",
               "select count(*) from _k_t where sh is null or sh <= 0 or sh = 999", "staff_hours set to NULL (excluded from productivity metrics).")
    plausible_bad = "(tx > 0 and (n / tx < 2 or n / tx > 40)) or u < tx"
    dq.add_sql(con, "store_daily_kpis", "KP06", "units < transactions or average ticket outside $2-$40", "flagged",
               f"select count(*) from _k_t where {plausible_bad}", "Kept; flagged implausible_ticket.")
    con.execute(f"""
        create or replace table store_daily_kpis as
        select store_id, d as date, case when ff > 0 then ff::integer end as footfall, tx::integer as transactions,
               u::integer as units_sold, n as net_sales,
               case when sh > 0 and sh <> 999 then sh end as staff_hours, oh as open_hours,
               coalesce(ff > 0 and tx <= ff, false) as conversion_valid,
               nullif(concat_ws(';',
                   case when ff is null or ff <= 0 then 'footfall_invalid' end,
                   case when ff > 0 and tx > ff then 'transactions_gt_footfall' end,
                   case when sh is null or sh <= 0 or sh = 999 then 'staff_hours_invalid' end,
                   case when {plausible_bad} then 'implausible_ticket' end), '') as dq_flags
        from _k_t order by store_id, d
    """)
    con.execute("""
        create or replace table kpi_missing_days as
        select c.store_id, c.date from store_calendar c where c.status = 'open'
          and not exists (select 1 from store_daily_kpis k where k.store_id = c.store_id and k.date = c.date)
    """)
    dq.add_sql(con, "store_daily_kpis", "KP07", "Open store-days with no KPI row", "flagged", "select count(*) from kpi_missing_days",
               "Listed in kpi_missing_days; not imputed.")


_SENTINEL = -999  # raw "no reading" marker in both temperature columns


def _neighbours(col: str) -> str:
    """SQL select-list: nearest valid previous / next value and date of ``col`` within the same site."""
    w = "partition by site_id order by d"
    prev, nxt = "rows between unbounded preceding and 1 preceding", "rows between 1 following and unbounded following"
    dated = f"case when {col} is not null then d end"
    return (f"last_value({col} ignore nulls) over ({w} {prev}) as {col}_pv, last_value({dated} ignore nulls) over ({w} {prev}) as {col}_pd, "
            f"first_value({col} ignore nulls) over ({w} {nxt}) as {col}_nv, first_value({dated} ignore nulls) over ({w} {nxt}) as {col}_nd")


def _interp(col: str) -> str:
    """Linear interpolation by day distance between the neighbours; one available neighbour is copied."""
    return (f"case when {col} is not null then {col} "
            f"when {col}_pv is not null and {col}_nv is not null "
            f"then round({col}_pv + ({col}_nv - {col}_pv) * (d - {col}_pd) / ({col}_nd - {col}_pd), 2) "
            f"else coalesce({col}_pv, {col}_nv) end")


def build_weather(con, dq: DQLog) -> None:
    con.execute(f"""
        create or replace temp table _w_n as
        select _rn, upper(trim(site_id)) as site_id, norm_date(date) as d,
               try_cast(temp_max_c as double) as tx, try_cast(temp_min_c as double) as tn,
               try_cast(precip_mm as double) as precip
        from raw.weather_daily
    """)
    dq.add_sql(con, "weather_daily", "WX00", "Unparseable date or site not in sites", "excluded",
               "select count(*) from _w_n where d is null or site_id not in (select site_id from sites)")
    con.execute("""
        create or replace temp table _w_d as
        select * exclude (rk) from (select *, row_number() over (partition by site_id, d order by _rn) as rk
              from _w_n where d is not null and site_id in (select site_id from sites)) where rk = 1
    """)
    dq.add_sql(con, "weather_daily", "WX01", "Duplicate (site, date) rows", "excluded",
               "select (select count(*) from _w_n where d is not null and site_id in (select site_id from sites)) "
               "- (select count(*) from _w_d)", "Exact duplicates; first kept.")
    dq.add_sql(con, "weather_daily", "WX03", "temp_min_c greater than temp_max_c", "fixed",
               "select count(*) from _w_d where tn > tx and tx <> -999 and tn <> -999", "Values swapped.")
    dq.add_sql(con, "weather_daily", "WX02", "Sentinel -999 in a temperature column", "fixed",
               f"select count(*) from _w_d where tx = {_SENTINEL} or tn = {_SENTINEL}",
               "Set to NULL, then linearly interpolated from the nearest valid days of the same site (flag temp_imputed).")
    # swap on valid pairs first so interpolation only ever sees consistent readings
    con.execute(f"""
        create or replace temp table _w_c as
        select *, (tx = {_SENTINEL} or tn = {_SENTINEL}) as was_sentinel,
               (tn > tx and tx <> {_SENTINEL} and tn <> {_SENTINEL}) as swapped,
               case when tx = {_SENTINEL} then null when tn > tx and tn <> {_SENTINEL} then tn else tx end as cx,
               case when tn = {_SENTINEL} then null when tn > tx and tx <> {_SENTINEL} then tx else tn end as cn
        from _w_d
    """)
    con.execute(f"""
        create or replace temp table _w_i as
        select *, {_interp("cx")} as ix, {_interp("cn")} as imn
        from (select *, {_neighbours("cx")}, {_neighbours("cn")} from _w_c)
    """)
    dq.add_sql(con, "weather_daily", "WX05", "Temperature still unknown after imputation (no valid day for the site)", "flagged",
               "select count(*) from _w_i where ix is null or imn is null", "Left NULL; flag temp_unknown.")
    dq.add_sql(con, "weather_daily", "WX04", "precip_mm null", "flagged", "select count(*) from _w_i where precip is null",
               "Kept NULL (not assumed to be 0); flag precip_missing.")
    con.execute("""
        create or replace table weather_daily as
        select site_id, d as date, ix as temp_max_c, imn as temp_min_c, precip as precip_mm,
               (was_sentinel and ix is not null and imn is not null) as temp_imputed,
               nullif(concat_ws(';',
                   case when swapped then 'temp_swapped' end,
                   case when was_sentinel and ix is not null and imn is not null then 'temp_imputed' end,
                   case when ix is null or imn is null then 'temp_unknown' end,
                   case when precip is null then 'precip_missing' end), '') as dq_flags
        from _w_i order by site_id, d
    """)


def build_facts(con, dq: DQLog) -> None:
    """Build every fact table (dimensions must already exist)."""
    build_sales(con, dq)
    build_inventory(con, dq)
    build_purchase_orders(con, dq)
    build_store_daily_kpis(con, dq)
    build_weather(con, dq)
