# Data quality report

Generated from `Dataset/clean/dq_log.csv` by the pipeline (`python3 -m glazed_etl`). Counts are rows of the raw table affected by each rule. Treatments: **fixed** (value repaired), **flagged** (kept, marked in `dq_flags` or a boolean column), **excluded** (row removed from the clean table). Raw files are never modified. A count of 0 means the rule was checked and nothing was found.

Row counts raw -> clean: sites 20->20, stores 40->38, store_closures 7->7, products 1,028->991, product_barcodes 1,457->1,422, suppliers 8->8, prices 3,097->2,758, sales_daily 592,602->588,882, inventory_daily 494,111->489,065, purchase_orders 262,748->262,648, store_daily_kpis 12,809->12,784, promotions 13->13, calendar 365->365, weather_daily 7,320->7,300.

Validation (`Dataset/clean/validation.json`): primary keys unique, all foreign keys covered, price windows do not overlap, every site has weather for every calendar date, inventory identity holds after cleaning, and 12,648 of 12,784 store-days (98.9%) have clean sales within 1% of `store_daily_kpis.net_sales` (total $26.27M vs $26.28M).

## sites

Reference table; no defects found, the duplicate check is kept as a guard.

| Rule | Issue | Rows | Treatment | Rationale |
|---|---|---:|---|---|
| SI01 | Duplicate site_id | 0 | excluded | Kept the first occurrence. |

## suppliers

Reference table; no defects found.

| Rule | Issue | Rows | Treatment | Rationale |
|---|---|---:|---|---|
| SU01 | Duplicate supplier_id | 0 | excluded | - |

## calendar

`quarter_idx` was a day-of-year artefact (it jumps at quarter boundaries and does not match the calendar). It is replaced by `quarter` (1-4); every derived column is recomputed from the date. Holiday and school-break flags are kept as delivered.

| Rule | Issue | Rows | Treatment | Rationale |
|---|---|---:|---|---|
| CA01 | quarter_idx inconsistent with the date (not the 0-based calendar quarter) | 122 | fixed | Replaced by `quarter` (1-4) derived from the date. |
| CA02 | day_of_week / iso_week / month / year / is_weekend disagree with the date | 0 | fixed | Derived columns recomputed from the date. |

## stores

S039 is a copy of S004 (same site, format, opening date, size and name) and is merged into S004 through `store_id_map`. S040 points to site `ST99`, which does not exist, and has no activity in any fact table, so it is excluded (deviation from "flag only": keeping it would break the store-to-site key and it would pollute store-level models). Five stores miss `opening_time`; it is inferred from `closing_time` minus the typical `open_hours` seen in the daily KPIs.

| Rule | Issue | Rows | Treatment | Rationale |
|---|---|---:|---|---|
| ST01 | Duplicate store record (same site, format, opening date, size and name) | 1 | excluded | Merged into the lowest store_id; see store_id_map. |
| ST02 | site_id not present in sites (orphan) | 1 | excluded | No fact table references these stores; kept out to keep the store -> site FK clean. |
| ST03 | Store name with stray whitespace or inconsistent casing | 9 | fixed | Trimmed, collapsed whitespace, title-cased all-upper / all-lower names. |
| ST04 | opening_time null / #N/A | 5 | fixed | opening_time = closing_time - typical open_hours (mode of store_daily_kpis.open_hours). |
| ST05 | opening_time null and no KPI evidence to infer it | 0 | flagged | - |

## store_closures

Normalised and keyed on the merged store ids. `store_calendar` (one row per store and date) is derived from `opened_date`, `closed_date` and the closure windows: status is `open`, `not_yet_open`, `temporary_closure` or `closed_permanently`; `closed_date` is the first non-trading day. Every fact table is filtered against it.

| Rule | Issue | Rows | Treatment | Rationale |
|---|---|---:|---|---|
| SC01 | Closure for a store that does not exist in stores | 0 | excluded | - |
| SC02 | end_date before start_date | 0 | fixed | end_date set to start_date. |

## products

The master has 1,028 rows for 991 SKUs: formatting variants (`sku-`, `SKU100040`, padded) and conflicting copies. SKU-100040 looked "missing from the master" in the first audit only because its master row is written `SKU100040` (no dash); after normalisation it matches, so no inferred product row was needed on this dataset (the inference rule PD07 is implemented and tested for other data). Categories contradicting their department/subcategory are corrected only when the group is large and clearly dominated. 144 products have no usable cost (discontinued items with price 0); they have no sales or POs.

| Rule | Issue | Rows | Treatment | Rationale |
|---|---|---:|---|---|
| PD01 | Duplicate SKU rows (formatting variants and conflicting attributes) | 37 | excluded | Survivor: valid cost > 0, then category equal to the canonical one, then not-ALL-CAPS name, then first in file. |
| PD02 | category with inconsistent casing / whitespace | 18 | fixed | Canonical spelling = most frequent properly cased variant. |
| PD03 | category contradicting the dominant category of its department + subcategory | 19 | fixed | Replaced when the group has >= 5 rows and >= 80% agree. |
| PD04 | unit_cost null or 0 | 40 | fixed | Imputed: median PO unit_cost > 0 for the SKU, else median cost/price ratio of its subcategory x list price. |
| PD05 | unit_cost null or 0 and not imputable | 144 | flagged | Left NULL (typically discontinued items with no price either). |
| PD06 | discontinued_date earlier than launch_date | 121 | flagged | - |
| PD07 | SKU sold / ordered / stocked but absent from the product master | 0 | fixed | Added an inferred master row (inferred=true): list price = median sold unit_price, cost = median PO cost, supplier = most frequent PO supplier; descriptive attributes unknown. Avoids dropping its sales. |
| PD08 | list_price_base null or 0 | 144 | fixed | Set to NULL. |

## product_barcodes

Barcodes of SKUs outside the master are dropped; a barcode shared by several SKUs is kept for the lowest SKU only.

| Rule | Issue | Rows | Treatment | Rationale |
|---|---|---:|---|---|
| BC01 | Exact duplicate rows (after SKU normalization) | 0 | excluded | - |
| BC02 | Barcode for a SKU that is not in the product master | 20 | excluded | - |
| BC03 | Barcode shared by several SKUs | 15 | excluded | Kept the lowest SKU for each barcode. |

## promotions

PR003 ends before it starts (2025-11-19 vs 2025-11-24). Sales tagged PR003 run until 2025-12-24, so that date is used (assumption supported by evidence). PR013 never appears in sales; it is kept and flagged `never_applied` (useful as a placebo for uplift analysis). `applied_rows`, `first_applied` and `last_applied` come from raw sales.

| Rule | Issue | Rows | Treatment | Rationale |
|---|---|---:|---|---|
| PM01 | end_date before start_date | 1 | fixed | end_date = last date on which sales carry the promo_id (assumption validated by sales evidence). |
| PM02 | Promotion never applied in sales | 1 | flagged | Kept: usable as a placebo / control when measuring uplift. |

## prices

Prices are rebuilt as a non-overlapping SCD2 per store and SKU. Legit high prices (merch, take-home coffee) exist, so outliers are detected against the SKU list price (0.5x to 2x), not with a fixed cap. A window ending before it starts belongs to a store that opened after the 2026-03-01 price change; it is re-opened and loses against the real price starting the same day.

| Rule | Issue | Rows | Treatment | Rationale |
|---|---|---:|---|---|
| PRC01 | Non-standard currency spelling (Usd, usd, US$, 'USD ') | 98 | fixed | Normalised to USD. |
| PRC02 | Non-ISO effective_from / effective_to | 83 | fixed | Parsed as MM/DD/YYYY. |
| PRC03 | Duplicate price_id | 40 | excluded | Kept the first occurrence. |
| PRC04 | Price for a store that is not in stores | 39 | excluded | - |
| PRC05 | Price for a SKU that is not in products | 60 | excluded | - |
| PRC06 | Invalid price: null, <= 0, or outside 0.5x-2x of the SKU list price | 102 | excluded | Covers 0 / -1 / blank and x10 / x100 / x0.1 outliers; legitimate high prices (merch, take-home coffee) are kept. |
| PRC07 | effective_to earlier than effective_from | 57 | fixed | Window opened (effective_to = NULL) and then resolved against the other windows of the store-SKU. |
| PRC08 | Overlapping / simultaneously open price windows | 21 | fixed | Non-overlapping SCD2: a window ends the day before the next effective_from (latest start wins). |
| PRC09 | Several prices starting the same day for one store-SKU | 98 | excluded | Kept the non-repaired, most recently updated row (highest price_id as final tie-break). |

## sales_daily

Duplicates are exact copies except 4 keys (all on closure days). Units are reconstructed from gross/price when null or about 10x too high. `net_sales = gross - discount` with the discount capped at gross; this identity makes 98.9% of store-days match the KPI totals (the raw net matched 98.6% within $0.5 vs 97.7%). Returns (negative units) stay in net sales because the KPIs include them; use `v_demand_sales` for demand. Rows where gross differs from units x price are kept as reported and flagged (586).

| Rule | Issue | Rows | Treatment | Rationale |
|---|---|---:|---|---|
| SD00 | Unparseable date | 0 | excluded | - |
| SD01 | Duplicate (date, store, sku) rows | 3,004 | excluded | Kept the first occurrence. |
| SD02 | Duplicate keys whose copies disagree on units / amounts | 4 | flagged | First copy kept (these all fall on closure days in the source data). |
| SD03 | Sales for a SKU that is not in products (random SKU-7xxxxx orphans) | 400 | excluded | These rows are absent from store_daily_kpis totals. |
| SD04 | Sales for a store that is not in stores (after id normalization / merge) | 0 | excluded | - |
| SD05 | Sales while the store was not trading (before opening, closure window, after closure) | 316 | excluded | - |
| SD06 | units_sold null | 100 | fixed | units = round(gross_sales / unit_price). |
| SD07 | units_sold ~10x the amount implied by gross / price | 80 | fixed | units = round(gross_sales / unit_price). |
| SD08 | Negative units (returns) | 150 | flagged | Kept with is_return = true; exclude from demand, keep in net sales (KPIs include them). |
| SD09 | gross_sales != units x unit_price | 586 | flagged | Kept as reported (the invoiced gross is trusted); likely a price different from the one recorded. |
| SD10 | net_sales != gross_sales - discount_amount | 180 | fixed | net_sales = gross_sales - discount (the store KPIs follow this identity). |
| SD11 | discount_amount greater than gross_sales | 29 | fixed | Discount capped at gross_sales. |
| SD12 | promo_id not present in promotions (e.g. PR999) | 60 | fixed | promo_id set to NULL. |

## inventory_daily

`closing_qty` is recomputed from the stock identity (source value kept in `closing_qty_raw`); negative results are clamped to 0 and flagged. `cold_start_week` marks the first 7 days (opening stock 0), which should be excluded from stock-out statistics. Rows on temporary-closure days are excluded (4,546, of which about 1.8k record receptions).

| Rule | Issue | Rows | Treatment | Rationale |
|---|---|---:|---|---|
| IV01 | Duplicate (date, store, sku) rows | 500 | excluded | Exact duplicates; first kept. |
| IV02 | Row for an unknown store / SKU, or with unparseable date / quantities | 0 | excluded | - |
| IV03 | Inventory rows on days the store was closed (temporary closure window) | 4,546 | excluded | Includes receptions recorded during closures. |
| IV04 | closing_qty != opening + received - sold - expired - damaged | 2,183 | fixed | closing_qty recomputed from the identity; source value kept in closing_qty_raw. |
| IV05 | Negative closing_qty in the source | 391 | flagged | - |
| IV06 | stockout_hours above the store's open hours (up to 60 h in a day) | 59 | fixed | Capped at the store's typical open hours (24 if unknown). |
| IV07 | opening_qty differs from the previous day's closing_qty | 884 | flagged | Stock discontinuity (transfers / counts); not corrected. |
| IV08 | Expired quantity on a non-perishable SKU | 0 | flagged | Kept; review product master (is_perishable). |
| IV10 | Identity yields negative stock (sold more than available) | 115 | flagged | closing_qty clamped to 0 (flag closing_clamped); identity then no longer holds for the row. |

## purchase_orders

Duplicate PO lines keep the copy consistent with its status. Unit cost 0 (6.5k lines) is replaced by the cleaned product cost. Delivered lines without a received date are flagged, not invented. The 65 "Delivered but short" lines of the first audit all came from the duplicate copies, so PO06 finds 0 after de-duplication.

| Rule | Issue | Rows | Treatment | Rationale |
|---|---|---:|---|---|
| PO01 | Duplicate PO line (same po_id, store, sku) with different quantities | 100 | excluded | Kept the copy consistent with its status (Delivered => received = ordered; Short-shipped => received < ordered), else the first. |
| PO02 | supplier_id not in suppliers (e.g. SUP99) | 50 | fixed | Replaced by the supplier of the SKU in the product master. |
| PO03 | expected_date null | 100 | fixed | expected_date = order_date + supplier standard lead time. |
| PO04 | received_date earlier than order_date | 60 | fixed | received_date set to NULL (not invented). |
| PO05 | qty_received greater than qty_ordered | 40 | fixed | Capped at qty_ordered. |
| PO06 | Delivered line received short | 0 | fixed | Status reclassified to Short-shipped. |
| PO07 | Delivered line without received_date | 78 | flagged | - |
| PO08 | qty_ordered <= 0 or null | 0 | excluded | - |
| PO09 | unit_cost null, 0 or negative | 6,579 | fixed | Imputed from the product master unit_cost. |
| PO10 | unit_cost invalid and product cost unknown | 0 | flagged | Left NULL. |
| PO11 | PO line for an unknown store / SKU or without order date | 0 | excluded | - |

## store_daily_kpis

Sentinels become NULL (not imputed) with a flag: footfall 0/null, staff_hours <= 0 or 999. `conversion_valid` is false when footfall is missing or transactions exceed it. The 46 missing open store-days are listed in `kpi_missing_days`.

| Rule | Issue | Rows | Treatment | Rationale |
|---|---|---:|---|---|
| KP01 | Duplicate (store, date) rows | 25 | excluded | Exact duplicates; first kept. |
| KP02 | KPI row for an unknown store or unparseable date | 0 | excluded | - |
| KP03 | footfall null or 0 | 80 | fixed | footfall set to NULL (not imputed); excluded from conversion metrics. |
| KP04 | transactions greater than footfall | 40 | flagged | conversion_valid = false. |
| KP05 | staff_hours <= 0 or the 999 sentinel | 40 | fixed | staff_hours set to NULL (excluded from productivity metrics). |
| KP06 | units < transactions or average ticket outside $2-$40 | 40 | flagged | Kept; flagged implausible_ticket. |
| KP07 | Open store-days with no KPI row | 46 | flagged | Listed in kpi_missing_days; not imputed. |
| KP08 | KPI row on a day the store was not trading | 0 | excluded | - |

## weather_daily

One row per site and day (20 sites x 365 days). Temperatures are in Celsius with a constant 8.0 spread between daily max and min on every valid row, which is what makes the repairs below safe. The `-999` sentinel is nulled and imputed by linear interpolation by day distance between the nearest valid days of the same site (the single available neighbour at the edges); imputed rows carry `temp_imputed = true` and the tag `temp_imputed` in `dq_flags`. Missing precipitation is deliberately not imputed: whether to treat it as dry is a modelling decision. Tags: `temp_swapped`, `temp_imputed`, `temp_unknown`, `precip_missing`.

| Rule | Issue | Rows | Treatment | Rationale |
|---|---|---:|---|---|
| WX00 | Unparseable date or site not in sites | 0 | excluded | - |
| WX01 | Duplicate (site, date) rows | 20 | excluded | Exact duplicates; first kept. |
| WX02 | Sentinel -999 in temp_max_c and temp_min_c | 40 | fixed | Set to NULL, then interpolated from neighbouring days of the same site; flag temp_imputed. |
| WX03 | temp_min_c greater than temp_max_c | 25 | fixed | Values swapped (the spread is exactly -8.0 on these rows, i.e. columns were exchanged); flag temp_swapped. |
| WX04 | precip_mm null | 60 | flagged | Kept NULL, not assumed 0; flag precip_missing. |
| WX05 | Temperature still unknown after imputation | 0 | flagged | Left NULL; flag temp_unknown. |

## Known limitations

- 586 sales rows keep a gross that differs from units x price; the cause (list vs actual price) cannot be determined from the data.
- 144 products have no usable unit cost; margin calculations must skip them.
- Footfall and staff hours are nulled, not imputed; imputation is a modelling decision.
- The analysis note counted 374 expiries on non-perishable SKUs; with the cleaned `is_perishable` flag no such row remains (IV08 = 0).
- Prices cover only 254 SKUs; analyses should use the observed `unit_price` in sales.
- Weather precipitation is NULL on 60 site-days (not imputed); interpolated temperatures (40 site-days) are estimates, filter on `temp_imputed` when accuracy matters.
