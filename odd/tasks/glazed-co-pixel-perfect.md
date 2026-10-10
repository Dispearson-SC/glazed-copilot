# Feature: glazed-co-pixel-perfect

## Objective
The frontend becomes exactly the Glazed-Co design (github.com/CesarOliva/Glazed-Co @ b9d4132): Dashboard, Login and Chat, pixel perfect, filled with real backend data. Everything else is removed.

## Why
User decision (2026-10-10): the original frontend was only an initial flow. Keep only the three screens of the design repo; manager questions outside them are answered through the chat.

## Scope (authorized)
`frontend/` only, branch `feat/glazed-co-pixel-perfect` from `feat/foundation` @ 924750f (worktree `glazed-copilot-wt/pixel-perfect`). No backend changes, no push. Core merges and deploys.

## Remove
Pages Alerts, Cases, Purchases, Trace, Decisions, Inventory, Week; SimControl, CentinelaPanel, IssueDetail, ComingSoon, legacy KPI cards and semaphore, the legacy CSS layer, routes and nav entries pointing to them, "Ver razonamiento" / trace links, and the tests and helpers that only serve removed code. Unused api.ts methods and types go too.

## Keep (behavior)
`resolveBase()`, `DEFAULT_SIM_TODAY` (2026-07-19) and the auto-created live case, SessionContext, useCurrentCase, the chat logic (useChat, turns history, trace fallback parser, polling with transient-error budget, sanitize, inline pending proposals with Aprobar/Rechazar + Idempotency-Key, reply_meta chip), and the PWA setup.

## Design source
`Glazed-Co` at b9d4132: `src/components/*`, `src/pages/{DashboardPage,LoginPage,ChatPage}.tsx`, `FloatingChat.tsx`, `tailwind.config.js`, `index.html` (fonts, Material Symbols), `index.css`, `DESIGN.md`, and `screen.png` (422x1600 reference of the dashboard). Markup, classes, spacing, typography and colors are copied, not reinterpreted.

## Data mapping (real data, no mock)
| Design element | Source |
|---|---|
| TopBar store name / logo | `store_display_name` (no codes), Glazed logo asset |
| Live badge / time | "Fecha simulada" + `sim_today` (no wall clock) |
| PageHeader title / date | "Resumen de hoy"; long Spanish date of the day-summary `date` |
| HeroCard total, delta | day-summary `totals.net_sales`, `vs_same_weekday_avg.delta_pct` ("vs promedio mismo día") |
| Hero goal bar | progress vs `baseline_net_sales`, labelled as the 8-week same-weekday average (no invented goal) |
| MetricCards | `transactions`, avg ticket (guard 0 → "—"), `units_sold` |
| ActivityChart | same visual, daily bars: last 7 days actual + forecast days, "hoy" highlight, tooltip with real values; label "Ventas por día" (no hourly data exists) |
| TopProducts | day-summary `top_skus[0..2]`; no product photos exist → same-size thumbnail with initials in theme colors |
| ActionsFooter / sync text | link to Chat; "Datos al <as_of>" |
| BottomNav | entries for existing screens only (Resumen, Chat, tienda/Login) |
| Login | store picker (display_name) + case selection, no credentials |
| Chat page / FloatingChat | existing useChat wired to the orchestrator |
`totals: null` → "Sin datos". Ranges stay ranges.

## TDD
Strict. Runner: `cd frontend && npm test -- --run`; plus `npm run build`.

## Tasks
- [x] T1 Remove legacy screens, components, routes, CSS and their tests; app still builds, remaining tests green. Route: delegated writer. Evidence: RED 28 failed (legacy.test, App.test, theme.test); GREEN 157 tests / 16 files; `npm run build` ok.
- [x] T2 Dashboard pixel perfect with real data (all components above). Route: delegated writer. Evidence: RED (DashboardPage suite import failure + font parity test); GREEN 164 tests / 15 files; build ok. Forecast model caption added per coordinator note.
- [x] T3 Login pixel perfect as store/case picker. Route: delegated writer. Evidence: RED 1 failed (design-parity test); GREEN 165 tests; build ok.
- [x] T4 Chat page + FloatingChat pixel perfect over the existing chat logic. Route: delegated writer. Evidence: RED 4 failed (chat design parity); GREEN 169 tests; build ok.
- [ ] T5 Visual check vs `screen.png` at 422px width with a headless screenshot; README update. Route: delegated writer.

## Progress
- 2026-10-10: worktree created from feat/foundation 924750f.
- T1 commit c2039a0.
- T2 commit c3be50f.
- T3 commit 2e04877.
