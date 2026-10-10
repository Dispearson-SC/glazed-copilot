"""Dimension tables. Each ``build_*`` reads ``raw.*`` + the SQL normalizers and
creates one clean table in the main schema, logging every treatment in ``DQLog``."""
from __future__ import annotations

from .dq import DQLog


def build_sites(con, dq: DQLog) -> None:
    con.execute("""
        create or replace table sites as
        select upper(trim(site_id)) as site_id, trim(site_name) as site_name,
               trim(site_type) as site_type, trim(region) as region,
               try_cast(traffic_tier as double) as traffic_tier
        from (select *, row_number() over (partition by upper(trim(site_id)) order by _rn) as rk
              from raw.sites where site_id is not null) where rk = 1
    """)
    dq.add_sql(con, "sites", "SI01", "Duplicate site_id", "excluded",
               "select (select count(*) from raw.sites) - (select count(*) from sites)",
               "Kept the first occurrence.")


def build_suppliers(con, dq: DQLog) -> None:
    con.execute("""
        create or replace table suppliers as
        select upper(trim(supplier_id)) as supplier_id, trim(supplier_name) as supplier_name,
               trim(category_focus) as category_focus,
               try_cast(standard_lead_time_days as integer) as standard_lead_time_days,
               try_cast(contract_fill_rate as double) as contract_fill_rate,
               try_cast(contract_on_time_rate as double) as contract_on_time_rate,
               try_cast(min_order_value as double) as min_order_value, trim(delivery_days) as delivery_days
        from (select *, row_number() over (partition by upper(trim(supplier_id)) order by _rn) as rk
              from raw.suppliers where supplier_id is not null) where rk = 1
    """)
    dq.add_sql(con, "suppliers", "SU01", "Duplicate supplier_id", "excluded",
               "select (select count(*) from raw.suppliers) - (select count(*) from suppliers)")


def build_calendar(con, dq: DQLog) -> None:
    con.execute("""
        create or replace table calendar as
        select d as date, strftime(d, '%a') as day_of_week, weekofyear(d)::integer as iso_week,
               month(d)::integer as month, year(d)::integer as year, quarter(d)::integer as quarter,
               dayofweek(d) in (0, 6) as is_weekend,
               coalesce(try_cast(is_holiday as integer), 0) = 1 as is_holiday,
               nullif(trim(holiday_name), '') as holiday_name,
               coalesce(try_cast(is_school_break as integer), 0) = 1 as is_school_break
        from (select norm_date(date) as d, * from raw.calendar) where d is not null
    """)
    dq.add_sql(con, "calendar", "CA01", "quarter_idx inconsistent with the date (not the 0-based calendar quarter)",
               "fixed",
               "select count(*) from (select norm_date(date) d, try_cast(quarter_idx as integer) q from raw.calendar) "
               "where q is distinct from quarter(d) - 1",
               "Replaced by `quarter` (1-4) derived from the date.")
    dq.add_sql(con, "calendar", "CA02", "day_of_week / iso_week / month / year / is_weekend disagree with the date",
               "fixed",
               "select count(*) from (select norm_date(date) d, * from raw.calendar) "
               "where day_of_week is distinct from strftime(d, '%a') or try_cast(iso_week as int) is distinct from weekofyear(d) "
               "or try_cast(month as int) is distinct from month(d) or try_cast(year as int) is distinct from year(d) "
               "or try_cast(is_weekend as int) is distinct from (case when dayofweek(d) in (0,6) then 1 else 0 end)",
               "Derived columns recomputed from the date.")


def build_stores(con, dq: DQLog) -> None:
    # 1) normalise
    con.execute("""
        create or replace temp table _stores_n as
        select _rn, norm_store(store_id) as store_id, upper(trim(site_id)) as site_id,
               norm_name(store_name) as store_name, trim(store_name) as raw_name,
               trim(format) as format, trim(operator_type) as operator_type,
               norm_time(opening_time) as opening_time, norm_time(closing_time) as closing_time,
               norm_date(opened_date) as opened_date, norm_date(closed_date) as closed_date,
               try_cast(sqft as integer) as sqft, try_cast(seats as integer) as seats
        from raw.stores where norm_store(store_id) is not null
    """)
    dq.add_sql(con, "stores", "ST03", "Store name with stray whitespace or inconsistent casing", "fixed",
               "select count(*) from raw.stores where store_name is distinct from norm_name(store_name)",
               "Trimmed, collapsed whitespace, title-cased all-upper / all-lower names.")
    # 2) orphan site
    dq.add_sql(con, "stores", "ST02", "site_id not present in sites (orphan)", "excluded",
               "select count(*) from _stores_n where site_id not in (select site_id from sites)",
               "No fact table references these stores; kept out to keep the store -> site FK clean.")
    con.execute("delete from _stores_n where site_id not in (select site_id from sites)")
    # 3) duplicated stores (same site/format/opening/size, name equal ignoring case)
    con.execute("""
        create or replace temp table _stores_map as
        select store_id as old_store_id,
               min(store_id) over (partition by site_id, format, opened_date, sqft, seats, lower(store_name)) as store_id
        from _stores_n
    """)
    dq.add_sql(con, "stores", "ST01", "Duplicate store record (same site, format, opening date, size and name)",
               "excluded", "select count(*) from _stores_map where old_store_id <> store_id",
               "Merged into the lowest store_id; see store_id_map.")
    con.execute("""
        create or replace table store_id_map as select old_store_id, store_id from _stores_map
    """)
    con.execute("create or replace macro map_store(x) as (select store_id from store_id_map where old_store_id = norm_store(x))")
    con.execute("delete from _stores_n where store_id in (select old_store_id from _stores_map where old_store_id <> store_id)")
    # 4) opening time inference from KPI open_hours
    con.execute("""
        create or replace temp table _open_hours as
        select store_id, mode(oh) as typical_open_hours from (
            select map_store(store_id) as store_id, try_cast(open_hours as double) as oh from raw.store_daily_kpis)
        where oh between 1 and 24 and store_id is not null group by 1
    """)
    con.execute("""
        create or replace table stores as
        select s.store_id, s.site_id, s.store_name, s.format, s.operator_type,
               coalesce(s.opening_time, inf.inferred) as opening_time, s.closing_time,
               h.typical_open_hours, s.opened_date, s.closed_date, s.sqft, s.seats,
               nullif(concat_ws(';',
                   case when s.opening_time is null and inf.inferred is not null then 'opening_time_inferred' end,
                   case when s.opening_time is null and inf.inferred is null then 'opening_time_unknown' end,
                   case when s.raw_name is distinct from s.store_name then 'name_normalized' end), '') as dq_flags
        from _stores_n s
        left join _open_hours h using (store_id)
        left join lateral (
            select case when s.opening_time is null and s.closing_time is not null and h.typical_open_hours is not null
                then printf('%02d:%02d', (((cm - (h.typical_open_hours * 60)::integer) % 1440 + 1440) % 1440) // 60,
                                         (((cm - (h.typical_open_hours * 60)::integer) % 1440 + 1440) % 1440) % 60) end as inferred
            from (select (cast(split_part(s.closing_time, ':', 1) as integer) * 60
                          + cast(split_part(s.closing_time, ':', 2) as integer)) as cm)
        ) inf on true
    """)
    dq.add_sql(con, "stores", "ST04", "opening_time null / #N/A", "fixed",
               "select count(*) from stores where dq_flags like '%opening_time_inferred%'",
               "opening_time = closing_time - typical open_hours (mode of store_daily_kpis.open_hours).")
    dq.add_sql(con, "stores", "ST05", "opening_time null and no KPI evidence to infer it", "flagged",
               "select count(*) from stores where dq_flags like '%opening_time_unknown%'")


def build_store_closures(con, dq: DQLog) -> None:
    con.execute("""
        create or replace temp table _clos as
        select map_store(store_id) as store_id, norm_store(store_id) as raw_store,
               norm_date(start_date) as start_date, norm_date(end_date) as end_date, trim(reason) as reason
        from raw.store_closures
    """)
    dq.add_sql(con, "store_closures", "SC01", "Closure for a store that does not exist in stores", "excluded",
               "select count(*) from _clos where store_id is null or store_id not in (select store_id from stores)")
    con.execute("""
        create or replace table store_closures as
        select distinct store_id, start_date, greatest(start_date, end_date) as end_date, reason,
               coalesce(lower(reason) like 'permanent%', false) as is_permanent
        from _clos where store_id in (select store_id from stores) and start_date is not null
    """)
    dq.add_sql(con, "store_closures", "SC02", "end_date before start_date", "fixed",
               "select count(*) from _clos where end_date < start_date", "end_date set to start_date.")


def build_store_calendar(con, dq: DQLog) -> None:
    """One row per (store, date) saying whether the store could trade that day."""
    con.execute("""
        create or replace table store_calendar as
        select s.store_id, c.date,
               case when s.opened_date is not null and c.date < s.opened_date then 'not_yet_open'
                    when s.closed_date is not null and c.date >= s.closed_date then 'closed_permanently'
                    when exists (select 1 from store_closures k where k.store_id = s.store_id
                                 and not k.is_permanent and c.date between k.start_date and k.end_date)
                         then 'temporary_closure'
                    else 'open' end as status
        from stores s cross join calendar c
    """)


# ------------------------------------------------------------------ products
INFER_MIN_SALE_DAYS = 30  # a SKU missing from the master is inferred if sold on >= this many days (or in PO/inventory)
_DOMINANT_MIN_ROWS = 5
_DOMINANT_MIN_SHARE = 0.8


def build_products(con, dq: DQLog) -> None:
    con.execute("""
        create or replace temp table _canon_cat as
        select k, norm_name(arg_max(c, (case when c <> upper(c) and c <> lower(c) then 1000000 else 0 end) + n)) as category
        from (select lower(trim(category)) as k, trim(category) as c, count(*) as n
              from raw.products where category is not null group by all) group by k
    """)
    con.execute("""
        create or replace temp table _prod_n as
        select _rn, norm_sku(sku) as sku, norm_name(product_name) as product_name, trim(product_name) as raw_name,
               trim(department) as department, trim(p.category) as raw_category, cc.category as category_cased,
               trim(subcategory) as subcategory, trim(brand) as brand, upper(trim(supplier_id)) as supplier_id,
               try_cast(unit_cost as double) as unit_cost, try_cast(list_price_base as double) as list_price_base,
               try_cast(case_size as integer) as case_size, try_cast(shelf_life_days as integer) as shelf_life_days,
               try_cast(is_perishable as integer) = 1 as is_perishable, trim(storage_type) as storage_type,
               try_cast(inventory_tracked as integer) = 1 as inventory_tracked,
               try_cast(is_seasonal as integer) = 1 as is_seasonal,
               norm_date(launch_date) as launch_date, norm_date(discontinued_date) as discontinued_date,
               trim(status) as status
        from raw.products p left join _canon_cat cc on cc.k = lower(trim(p.category))
        where norm_sku(sku) is not null
    """)
    # dominant category per (department, subcategory)
    con.execute(f"""
        create or replace temp table _dominant as
        select department, subcategory, top from (
            select department, subcategory, sum(n) as tot, max(n) as topn, arg_max(category_cased, n) as top
            from (select department, subcategory, category_cased, count(*) as n from _prod_n group by all)
            group by 1, 2)
        where tot >= {_DOMINANT_MIN_ROWS} and topn * 1.0 / tot >= {_DOMINANT_MIN_SHARE}
    """)
    con.execute("""
        create or replace temp table _prod_c as
        select p.*, coalesce(d.top, p.category_cased) as category
        from _prod_n p left join _dominant d using (department, subcategory)
    """)
    dq.add_sql(con, "products", "PD02", "category with inconsistent casing / whitespace", "fixed",
               "select count(*) from _prod_c where raw_category is distinct from category_cased",
               "Canonical spelling = most frequent properly cased variant.")
    dq.add_sql(con, "products", "PD03", "category contradicting the dominant category of its department + subcategory",
               "fixed", "select count(*) from _prod_c where category is distinct from category_cased",
               f"Replaced when the group has >= {_DOMINANT_MIN_ROWS} rows and >= {int(_DOMINANT_MIN_SHARE * 100)}% agree.")
    dq.add_sql(con, "products", "PD01", "Duplicate SKU rows (formatting variants and conflicting attributes)", "excluded",
               "select count(*) - count(distinct sku) from _prod_c",
               "Survivor: valid cost > 0, then category equal to the canonical one, then not-ALL-CAPS name, then first in file.")
    con.execute("""
        create or replace temp table _prod_d as
        select * exclude (rk) from (
            select *, row_number() over (partition by sku order by
                (coalesce(unit_cost, 0) > 0) desc, (category is not distinct from category_cased) desc,
                (raw_name is distinct from upper(raw_name)) desc, _rn) as rk
            from _prod_c) where rk = 1
    """)
    # cost imputation
    con.execute("""
        create or replace temp table _po_cost as
        select norm_sku(sku) as sku, median(c) as cost from (select sku, try_cast(unit_cost as double) as c from raw.purchase_orders)
        where c > 0 and norm_sku(sku) is not null group by 1
    """)
    con.execute("""
        create or replace temp table _ratio as
        select department, subcategory, median(unit_cost / list_price_base) as ratio
        from _prod_d where unit_cost > 0 and list_price_base > 0 group by 1, 2
    """)
    con.execute("""
        create or replace temp table _products_core as
        select p.sku, coalesce(p.product_name, p.raw_name) as product_name, p.department, p.category, p.subcategory,
               p.brand, p.supplier_id,
               case when p.unit_cost > 0 then p.unit_cost
                    when pc.cost is not null then pc.cost
                    when r.ratio is not null and p.list_price_base > 0 then round(r.ratio * p.list_price_base, 4) end as unit_cost,
               case when p.unit_cost > 0 then 'raw' when pc.cost is not null then 'po_median'
                    when r.ratio is not null and p.list_price_base > 0 then 'subcategory_ratio' else 'unknown' end as unit_cost_source,
               case when p.list_price_base > 0 then p.list_price_base end as list_price_base,
               p.case_size, p.shelf_life_days, p.is_perishable, p.storage_type, p.inventory_tracked, p.is_seasonal,
               p.launch_date, p.discontinued_date, p.status, false as inferred,
               nullif(concat_ws(';',
                   case when not coalesce(p.unit_cost, 0) > 0 and (pc.cost is not null or (r.ratio is not null and p.list_price_base > 0))
                        then 'unit_cost_imputed' end,
                   case when not coalesce(p.unit_cost, 0) > 0 and pc.cost is null and not (r.ratio is not null and p.list_price_base > 0)
                        then 'unit_cost_unknown' end,
                   case when not coalesce(p.list_price_base, 0) > 0 then 'list_price_missing' end,
                   case when p.discontinued_date < p.launch_date then 'discontinued_before_launch' end), '') as dq_flags
        from _prod_d p left join _po_cost pc using (sku) left join _ratio r using (department, subcategory)
    """)
    dq.add_sql(con, "products", "PD04", "unit_cost null or 0", "fixed",
               "select count(*) from _products_core where dq_flags like '%unit_cost_imputed%'",
               "Imputed: median PO unit_cost > 0 for the SKU, else median cost/price ratio of its subcategory x list price.")
    dq.add_sql(con, "products", "PD05", "unit_cost null or 0 and not imputable", "flagged",
               "select count(*) from _products_core where dq_flags like '%unit_cost_unknown%'",
               "Left NULL (typically discontinued items with no price either).")
    dq.add_sql(con, "products", "PD06", "discontinued_date earlier than launch_date", "flagged",
               "select count(*) from _products_core where dq_flags like '%discontinued_before_launch%'")
    dq.add_sql(con, "products", "PD08", "list_price_base null or 0", "fixed",
               "select count(*) from _products_core where dq_flags like '%list_price_missing%'", "Set to NULL.")
    _infer_missing_products(con, dq)
    con.execute("create or replace table products as select * from _products_core")


def _infer_missing_products(con, dq: DQLog) -> None:
    """SKUs that trade (sales on many days, or any PO / inventory) but are absent from the master get an inferred row."""
    con.execute(f"""
        create or replace temp table _inferred as
        with s as (select norm_sku(sku) as sku, count(distinct norm_date(date)) as days, median(try_cast(unit_price as double)) as price
                   from raw.sales_daily where norm_sku(sku) is not null group by 1),
        po as (select norm_sku(sku) as sku, median(try_cast(unit_cost as double)) filter (where try_cast(unit_cost as double) > 0) as cost,
                      mode(upper(trim(supplier_id))) as supplier
               from raw.purchase_orders where norm_sku(sku) is not null group by 1),
        inv as (select distinct norm_sku(sku) as sku from raw.inventory_daily where norm_sku(sku) is not null)
        select coalesce(s.sku, po.sku, inv.sku) as sku, s.price, po.cost, po.supplier,
               (po.sku is not null or inv.sku is not null) as tracked
        from s full join po on s.sku = po.sku full join inv on coalesce(s.sku, po.sku) = inv.sku
        where coalesce(s.sku, po.sku, inv.sku) not in (select sku from _products_core)
          and (s.days >= {INFER_MIN_SALE_DAYS} or po.sku is not null or inv.sku is not null)
    """)
    n = con.execute("select count(*) from _inferred").fetchone()[0]
    con.execute("""
        insert into _products_core
        select sku, 'Unknown product ' || sku, null, null, null, null, supplier, cost,
               case when cost is not null then 'po_median' else 'unknown' end, price,
               null, null, null, null, tracked, null, null, null, 'Unknown', true,
               'inferred_from_transactions' || case when cost is null then ';unit_cost_unknown' else '' end
        from _inferred
    """)
    dq.add("products", "PD07", "SKU sold / ordered / stocked but absent from the product master", "fixed", n,
           "Added an inferred master row (inferred=true): list price = median sold unit_price, cost = median PO cost, "
           "supplier = most frequent PO supplier; descriptive attributes unknown. Avoids dropping its sales.")


def build_product_barcodes(con, dq: DQLog) -> None:
    con.execute("""
        create or replace temp table _bc as
        select distinct trim(barcode) as barcode, norm_sku(sku) as sku, trim(barcode_type) as barcode_type
        from raw.product_barcodes where barcode is not null
    """)
    dq.add_sql(con, "product_barcodes", "BC01", "Exact duplicate rows (after SKU normalization)", "excluded",
               "select (select count(*) from raw.product_barcodes) - (select count(*) from _bc)")
    dq.add_sql(con, "product_barcodes", "BC02", "Barcode for a SKU that is not in the product master", "excluded",
               "select count(*) from _bc where sku not in (select sku from products)")
    con.execute("""
        create or replace temp table _bc2 as
        select *, row_number() over (partition by barcode order by sku) as rk
        from _bc where sku in (select sku from products)
    """)
    dq.add_sql(con, "product_barcodes", "BC03", "Barcode shared by several SKUs", "excluded",
               "select count(*) from _bc2 where rk > 1", "Kept the lowest SKU for each barcode.")
    con.execute("create or replace table product_barcodes as select barcode, sku, barcode_type from _bc2 where rk = 1")


# ------------------------------------------------------------------ promotions
def build_promotions(con, dq: DQLog) -> None:
    con.execute("""
        create or replace temp table _promo_use as
        select upper(trim(promo_id)) as promo_id, count(*) as applied_rows,
               min(norm_date(date)) as first_applied, max(norm_date(date)) as last_applied
        from raw.sales_daily where promo_id is not null group by 1
    """)
    con.execute("""
        create or replace table promotions as
        select p.promo_id, p.promo_name, p.promo_type, p.start_date,
               case when p.end_date < p.start_date
                    then case when u.last_applied >= p.start_date then u.last_applied else p.start_date end
                    else p.end_date end as end_date,
               p.discount_pct, p.department, p.category, p.region_scope, p.expected_uplift_pct,
               coalesce(u.applied_rows, 0) as applied_rows, u.first_applied, u.last_applied,
               nullif(concat_ws(';',
                   case when p.end_date < p.start_date then 'end_date_repaired' end,
                   case when coalesce(u.applied_rows, 0) = 0 then 'never_applied' end), '') as dq_flags
        from (select upper(trim(promo_id)) as promo_id, trim(promo_name) as promo_name, trim(promo_type) as promo_type,
                     norm_date(start_date) as start_date, norm_date(end_date) as end_date,
                     try_cast(discount_pct as double) as discount_pct, nullif(trim(department), '') as department,
                     nullif(trim(category), '') as category, nullif(trim(region_scope), '') as region_scope,
                     try_cast(expected_uplift_pct as double) as expected_uplift_pct
              from raw.promotions where promo_id is not null) p
        left join _promo_use u using (promo_id)
    """)
    dq.add_sql(con, "promotions", "PM01", "end_date before start_date", "fixed",
               "select count(*) from promotions where dq_flags like '%end_date_repaired%'",
               "end_date = last date on which sales carry the promo_id (assumption validated by sales evidence).")
    dq.add_sql(con, "promotions", "PM02", "Promotion never applied in sales", "flagged",
               "select count(*) from promotions where dq_flags like '%never_applied%'",
               "Kept: usable as a placebo / control when measuring uplift.")


# ------------------------------------------------------------------ prices
_PRICE_MIN_RATIO, _PRICE_MAX_RATIO, _PRICE_MAX_NO_LIST = 0.5, 2.0, 100.0


def build_prices(con, dq: DQLog) -> None:
    con.execute("""
        create or replace temp table _pr_n as
        select _rn, trim(price_id) as price_id, map_store(store_id) as store_id, norm_sku(sku) as sku,
               try_cast(unit_price as double) as unit_price, norm_currency(currency) as currency,
               norm_date(effective_from) as effective_from, norm_date(effective_to) as effective_to,
               upper(trim(price_list)) as price_list, norm_date(last_updated) as last_updated,
               currency is distinct from 'USD' as cur_fixed,
               coalesce(effective_from not like '____-__-__', false) or coalesce(effective_to not like '____-__-__', false) as date_fixed
        from raw.prices
    """)
    con.execute("""
        create or replace temp table _pr_d as
        select * exclude (rk) from (select *, row_number() over (partition by price_id order by _rn) as rk from _pr_n) where rk = 1
    """)
    dq.add_sql(con, "prices", "PRC01", "Non-standard currency spelling (Usd, usd, US$, 'USD ')", "fixed",
               "select count(*) from _pr_d where cur_fixed and currency = 'USD'", "Normalised to USD.")
    dq.add_sql(con, "prices", "PRC02", "Non-ISO effective_from / effective_to", "fixed",
               "select count(*) from _pr_d where date_fixed", "Parsed as MM/DD/YYYY.")
    dq.add_sql(con, "prices", "PRC03", "Duplicate price_id", "excluded",
               "select (select count(*) from _pr_n) - (select count(*) from _pr_d)", "Kept the first occurrence.")
    dq.add_sql(con, "prices", "PRC04", "Price for a store that is not in stores", "excluded",
               "select count(*) from _pr_d where store_id is null or store_id not in (select store_id from stores)")
    dq.add_sql(con, "prices", "PRC05", "Price for a SKU that is not in products", "excluded",
               "select count(*) from _pr_d where store_id in (select store_id from stores) "
               "and (sku is null or sku not in (select sku from products))")
    con.execute("""
        create or replace temp table _pr_v as
        select d.*, p.list_price_base from _pr_d d join products p using (sku)
        where d.store_id in (select store_id from stores)
    """)
    invalid = f"""(unit_price is null or unit_price <= 0
        or (list_price_base > 0 and (unit_price / list_price_base < {_PRICE_MIN_RATIO} or unit_price / list_price_base > {_PRICE_MAX_RATIO}))
        or (list_price_base is null and unit_price > {_PRICE_MAX_NO_LIST}))"""
    dq.add_sql(con, "prices", "PRC06", "Invalid price: null, <= 0, or outside 0.5x-2x of the SKU list price", "excluded",
               f"select count(*) from _pr_v where {invalid}",
               "Covers 0 / -1 / blank and x10 / x100 / x0.1 outliers; legitimate high prices (merch, take-home coffee) are kept.")
    con.execute(f"""
        create or replace temp table _pr_r as
        select * exclude (list_price_base), coalesce(effective_to < effective_from, false) as repaired
        from _pr_v where not {invalid} and effective_from is not null
    """)
    dq.add_sql(con, "prices", "PRC07", "effective_to earlier than effective_from", "fixed",
               "select count(*) from _pr_r where repaired",
               "Window opened (effective_to = NULL) and then resolved against the other windows of the store-SKU.")
    con.execute("""
        create or replace temp table _pr_k as
        select * exclude (rk) from (
            select *, row_number() over (partition by store_id, sku, effective_from
                                         order by repaired asc, last_updated desc nulls last, price_id desc) as rk
            from _pr_r) where rk = 1
    """)
    dq.add_sql(con, "prices", "PRC09", "Several prices starting the same day for one store-SKU", "excluded",
               "select (select count(*) from _pr_r) - (select count(*) from _pr_k)",
               "Kept the non-repaired, most recently updated row (highest price_id as final tie-break).")
    con.execute("""
        create or replace temp table _pr_w as
        select *, lead(effective_from) over (partition by store_id, sku order by effective_from) as next_from,
               case when repaired then null else effective_to end as orig_to
        from _pr_k
    """)
    con.execute("""
        create or replace table prices as
        select price_id, store_id, sku, unit_price, currency, effective_from,
               case when next_from is null then orig_to
                    else least(coalesce(orig_to, next_from - 1), next_from - 1) end as effective_to,
               price_list, last_updated,
               nullif(concat_ws(';', case when repaired then 'window_repaired' end,
                   case when next_from is not null and (orig_to is null or orig_to >= next_from) then 'window_truncated' end), '') as dq_flags
        from _pr_w order by store_id, sku, effective_from
    """)
    dq.add_sql(con, "prices", "PRC08", "Overlapping / simultaneously open price windows", "fixed",
               "select count(*) from prices where dq_flags like '%window_truncated%'",
               "Non-overlapping SCD2: a window ends the day before the next effective_from (latest start wins).")


def build_dimensions(con, dq: DQLog) -> None:
    """Build every dimension table in dependency order."""
    build_sites(con, dq)
    build_suppliers(con, dq)
    build_calendar(con, dq)
    build_stores(con, dq)
    build_store_closures(con, dq)
    build_store_calendar(con, dq)
    build_products(con, dq)
    build_product_barcodes(con, dq)
    build_promotions(con, dq)
    build_prices(con, dq)
