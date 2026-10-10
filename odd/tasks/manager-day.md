# Feature: manager-day

## Objective
The UI answers a store manager's full-day questions (yesterday, today and above all the future: what to order, what runs out, what expires, rotation, deliveries, promos, staffing, decisions and their outcomes) from real backend data.

## Why
User request (2026-10-10). Gap research mapped 38 manager questions: 19 READY, 12 PARTIAL, 7 GAP. Core (backend owner) is building Wave 11 (turns, decisions, forecast) and Wave 12 (inventory, expiring, pass-throughs, deliveries, promos, staffing) with contracts agreed with this session.

## Scope (authorized)
`frontend/` only, branch `feat/manager-day` from `feat/foundation` (worktree `glazed-copilot-wt/manager-day`). No backend changes, no push, no `make up`. Core merges and deploys.

## Constraints
- No look-ahead: never render actuals dated after `as_of`; the backend returns `actual: null`, and the UI shows a "hoy" marker at `sim_today`.
- Ranges `{low,mid,high}` are rendered as ranges. Store names come from `display_name`. Show `model` as given.
- Routes not yet deployed (404/501) render a quiet "Disponible pronto" state, never an error and never fabricated data.
- "Sin datos" for G5 (order cut-off hour), G8 (weather forecast), G9 (intraday).
- UI copy in Spanish; code in English. Strict TDD (Vitest), `cd frontend && npm test -- --run`, plus `npm run build`.

## Contracts (agreed with Core)
Common envelope: `{as_of, store_id, store_display_name, source, ...}`; projections carry `projected: true`; lists are sorted server-side and accept `?limit=`.
- W11 `GET /cases/{id}/turns` → `[{turn_id, ts, user_text, reply, reply_meta?}]`
- W11 `GET /cases/{id}/decisions?from=&to=` → `[{decision_id, ts, kind: proposal|decision|execution|outcome|skip_order, issue_id, action_type, sku?, supplier?, qty?, deadline?, status, reason?, outcome?{observed, simulated, label, score}}]`
- W11 `GET /cases/{id}/forecast?sku=&from=&to=&level=sku|store` → `{store_id, sku|null, level, as_of, forecast_origin, model, model_version, unit, horizon_days, points:[{date, forecast, p10, p90, baseline, actual|null, censored, stockout_hours?}], metrics_to_date:{wape, bias, coverage_p10_p90, wape_baseline, n_days}}`
- W12 G2 `GET /cases/{id}/inventory?sort=days_of_cover|turnover|slow&limit=` → `{coverage:{skus_with_inventory, skus_selling}, items:[{sku, product_name, department, on_hand, avg_daily_demand, days_of_cover, turnover_28d, weeks_of_supply, inventory_value_usd, last_sale_date, slow_mover, projected_stockout_date|null}]}`
- W12 G3 `GET /cases/{id}/expiring?days=7` → `{items:[{sku, product_name, expiring_units, expiry_date, shelf_life_days, waste_usd:{low,mid,high}, lot_age_inferred}], by_day:[{date, waste_usd}], total_waste_usd}`
- W12 G7 pass-throughs (internal shapes): `/cases/{id}/issues?kind=&category=`, `/inventory/projection?sku=&horizon=`, `/suppliers/performance`, `/history?weeks=`
- W12 G4 `GET /cases/{id}/deliveries?days=7` → `{days:[{date, deliveries:[{supplier_id, supplier_name, po_id|null, kind: open_po|scheduled, lines:[{sku, product_name, qty}], value_usd, status: on_time|late|expected}]}]}`
- W12 G6 `GET /cases/{id}/promos?status=active|upcoming|past&days=14` → `{items:[{promo_id, name, department, discount_pct, start_date, end_date, status, audit_verdict|null, evaluation:{uplift_pct}|null}]}`
- W12 G1 `GET /cases/{id}/staffing?days=7` → `{benchmark:{format, tx_per_staff_hour_p50}, days:[{date, forecast_transactions, recommended_staff_hours, planned_staff_hours|null, gap_hours|null, basis:"daily"}], note}`

## TDD
Mode: strict (project mode). Runner: `cd frontend && npm test -- --run`.

## Tasks
- [x] T1 "Lo que viene" on Home from live routes: orders due today/tomorrow (briefing `order_plan`), next stockouts and expected waste (`order-plan` lines), worst supplier; order deadline shown as a date with "hora no disponible". Route: delegated writer. Evidence: 194 tests pass (183 + 11 new), `npm run build` OK; live shapes confirmed against case fce42dd29fba (briefing, order-plan); also fixed PurchasesPage crash on live object-shaped min_order_warning / range waste.
- [x] T2 Forecast overlay on the Home trend: past 7 days actual plus next 7 days forecast, p10–p90 band, "hoy" marker, model label, metrics_to_date vs baseline; falls back to the current trend when the route is missing. Route: delegated writer. Evidence: 206 tests pass (194 + 12 new), build OK; route GET /cases/{id}/forecast not deployed on :8100 (404), built against contract with fixtures; 404/501 falls back to the 7-day trend.
- [x] T3 Decisions timeline page `/stores/:storeId/decisions` plus a BottomNav entry; grouped by decision, outcome expected vs observed; refreshes after advance. Route: delegated writer. Evidence: 214 tests pass (206 + 8 new), build OK; GET /cases/{id}/decisions is live on :8100 (200) but returns [] for case fce42dd29fba, so row shapes are verified against backend source (application/decisions.py), not live data.
- [x] T4 Chat history from `GET /turns` when available, falling back to the trace parser on 404. Route: delegated writer. Evidence: 225 tests pass (220 + 5 new), build OK; GET /cases/{id}/turns live on :8100 (200, [] for case fce42dd29fba; row keys turn_id, ts, user_text, reply, status confirmed). Any error from the route falls back to the trace parser. Retry button now resends the failed turn's own text.
- [ ] T5 Inventory page (G2 + G3: days of cover, slow movers, expiring) and a "Semana" page (G4 deliveries, G6 promos, G1 staffing), each with a "Disponible pronto" state. Route: delegated writer.

## Delivery
Forecast is well over the ~400 line budget. Strategy: ask-on-risk. One commit per task; Core merges the branch.

## Progress
- 2026-10-10: worktree created; contracts agreed with Core.
- 2026-10-10: T1 done, commit 24eb3d9
- 2026-10-10: T2 done, commit 0a63f38
- 2026-10-10: T3 done, commit 8f5fb52
- 2026-10-10: T2 follow-up (live forecast verified on :8100: band is sum over SKUs, censored days apart, /forecast/accuracy table), 220 tests, build OK, commit 5609765
- 2026-10-10: T4 done, commit 7b6e038
