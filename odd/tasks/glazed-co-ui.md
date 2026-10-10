# Feature: glazed-co-ui

## Objective
Port the Glazed-Co PWA design (github.com/CesarOliva/Glazed-Co: Vite + React + Tailwind "Artisanal Roast" theme, TopBar / HeroCard / MetricCards / ActivityChart / TopProducts / ActionsFooter / BottomNav, Login) into `frontend/`, wired to the real public API `/api/v1`. No mock data.

## Problem / why
The current frontend is functional but plain. The team's UI design lives in a separate mock-only repo. The demo needs that design on top of real numbers.

## Scope (authorized)
- `frontend/` only, branch `feat/glazed-co-ui` (worktree `glazed-copilot-wt/glazed-co-ui`, base `feat/foundation`).
- No backend changes. Core (owner) merges and deploys. Never push, never `make up SERVICES=web`.

## Constraints (agreed with Core and Datos-Core, 2026-10-10)
- Data is DAILY only: no hourly chart. The ActivityChart becomes a 7-day daily trend (one `GET /cases/{id}/day-summary?date=D` per day).
- "Today" is the simulation clock (`case.sim_today` / `as_of`), never the wall clock. Missing KPI days show "Sin datos", never 0.
- No invented daily goal: hero compares against `vs_same_weekday_avg` (baseline, weeks_used, delta_pct).
- Money ranges `{low, mid, high}` (for example `lost_sales_usd`) are shown as a range, never collapsed.
- Store names use `display_name`, never codes.
- Login = store/case picker on `SessionContext`; no credentials (real access control is Traefik basic auth).
- Keep `resolveBase()` in `api.ts`. Dev proxy default target `http://localhost:8100` (host port), overridable by `VITE_API_URL`; production build with `VITE_API_URL=""`.
- Keep all existing pages, routes and tests green. Strict TDD (Vitest + Testing Library, `npm test -- --run`), RED before GREEN.
- Commits: Conventional Commits, author Gerardo Suastegui, no AI attribution.

## Data mapping (public API)
| Widget | Source |
|---|---|
| Hero: day net sales, delta | `GET /cases/{id}/day-summary` → `totals.net_sales`, `vs_same_weekday_avg.{baseline_net_sales,delta_pct,weeks_used}`, `date`, `store_display_name`, `context` |
| Metric cards | `totals.transactions`, avg ticket = `net_sales/transactions`, `totals.units_sold` |
| 7-day trend | `day-summary?date=` for the 7 days ending at `date` |
| Top products | `top_skus[0..2]` `{product_name, net_sales, units}` |
| Headline / focus | `GET /cases/{id}/briefing` → `headline[]`, `suggested_focus`, `snapshot.kpis.lost_sales_usd{low,mid,high}`, `snapshot.order_plan.{due_today,due_tomorrow}` |
| Nav | existing pages: Inicio, Compras, Alertas, Casos, Inspector |

## TDD
Mode: strict (project mode, source: Core / project config). Runner: `cd frontend && npm test -- --run`.

## Tasks
- [x] T1 Theme tooling: Tailwind + Artisanal Roast tokens, fonts, Material Symbols, logo/icons, manifest colors; vite proxy default 8100. Route: delegated writer. Evidence: RED (theme.test.ts failed on missing tailwind.config), GREEN 108 tests, build ok. Tailwind v3.4 + postcss; legacy CSS moved to legacy.css, shell rules scoped to `.app > header`.
- [ ] T2 Shell: TopBar + BottomNav layout, LoginPage as store/case picker (`/login`), existing routes preserved. Route: delegated writer.
- [ ] T3 Dashboard (HomePage) with real data: hero, metric cards, 7-day trend, top products, briefing headline + lost-sales range, empty/error states. Route: delegated writer.
- [ ] T4 Restyle Alerts, Cases, Purchases, Trace with theme tokens (no behavior change). Route: delegated writer.
- [ ] T5 Docs: frontend README (env, ports, pages, data mapping). Route: delegated writer.

## Acceptance
- `npm test -- --run` and `npm run build` green; new tests cover dashboard mapping, missing-day state, range rendering, login picker.
- Dashboard renders against the live backend on :8100.

## Delivery
Strategy: ask-on-risk. Forecast ~1,500 authored lines (UI port) → exceeds the ~400 budget; Core merges the branch, slicing to be decided with Core.

## Progress
- 2026-10-10: worktree created, contract agreed with Core.
