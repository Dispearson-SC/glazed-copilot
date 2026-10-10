# Glazed frontend

React + Vite + TypeScript + Tailwind app ("Artisanal Roast" theme ported from the Glazed-Co design), PWA-ready (web manifest + service worker via `vite-plugin-pwa`; installable, no push yet). Talks to the backend through the public API (`/api/v1/*`).

## Run

```bash
npm install
npm run dev       # http://localhost:5173, proxies /api to the backend
npm test -- --run # Vitest + Testing Library (fetch is mocked, no backend needed)
npm run build     # type-check + production build into dist/
npm run preview
```

## Environment

| Variable | Default | Use |
|---|---|---|
| `VITE_API_URL` | dev: empty (Vite proxy to `http://localhost:8100`, the host port of the backend); build: `http://localhost:8080` unless set. Use `VITE_API_URL=""` for a same-origin production build behind the reverse proxy | Backend base URL. In dev it is also the proxy target. |
| `VITE_DEFAULT_SIM_TODAY` | `2026-07-19` (day 292 of the 2025-10-01..2026-09-30 dataset) | Default simulation date: the app opens on (and auto-creates, if missing) the live case at this date; also the default of the new-case form. |

## Pages

- `/` (Inicio): dashboard of the current case's store, from the simulation clock (never the wall clock). Hero with the day's net sales and delta vs the same-weekday average ("promedio de N semanas"), metric cards (transactions, average ticket, units), 7-day net-sales trend, top 3 products, observed weather and calendar chips, and the copilot briefing (headline, orders due today/tomorrow, suggested focus), plus the legacy loss cards and alert semaphore.
- `/login`: store and case picker (no credentials; access control is the reverse proxy's basic auth). The choice lives in `SessionContext` (`storeId`, `caseId`).

- `/alerts`: store selector, alerts of the store (auto-refresh every 10 s), "Marcar vista", and a detail panel with the issue payload and pending proposals (Aprobar / Rechazar with reason).
- `/stores/:storeId/trace?case=&turn=`: agent inspector. Pick a case; see the trace as a chronological conversational channel (from -> to bubbles, kind, expandable payload) and as one lane per agent (orchestrator highlighted). With `turn=<id>` it polls every 3 s while the turn is `pending`.
- `/cases`: list, create and fork cases, and an "ask" box that posts a message to a case and shows the reply when the turn finishes (with a link to its trace).

All pages show error and empty states when the backend is unreachable.

## API assumptions

`TraceEvent` is `{event_id?, case_id, store_id, ts, from_agent, to_agent, kind: message|tool_call|tool_result|escalation, payload}`. Agent ids for lanes: `orchestrator, present, past, supply, strategist, sentinel, auditor, liaison`; any other id (for example `manager`) appears in the timeline only. Payload summary uses `payload.text`, else `payload.tool`, else JSON.

## Dashboard data mapping

| Widget | Source |
|---|---|
| Hero, metric cards, top products, chips | `GET /cases/{id}/day-summary` (default date = `as_of` - 1) |
| 7-day trend | `day-summary?date=D` for the 6 days before the summary date, plus the summary itself |
| Headline, orders due, suggested focus | `GET /cases/{id}/briefing` |
| Loss cards | `GET /cases/{id}/kpis` (lost sales shown as a low-high range) |

Rules: a day with `totals: null` (HTTP 200) shows "Sin datos", never 0, and a trend day without data is marked "sin datos" instead of drawing a bar. HTTP errors (for example 400, date after `as_of`) are an error state, not "Sin datos". Average ticket shows "—" with zero transactions. `staff_hours` is not shown. Weather is observed, not a forecast. There is no hourly data and no daily goal. Store names use `display_name`.

## Layout

`src/api.ts` typed client, `src/trace.ts` pure trace helpers, `src/usePolling.ts` polling hook, `src/pages/*` pages, `src/dashboard/*` dashboard widgets, `src/shell/*` top bar and bottom navigation, `src/index.css` Tailwind layers (tokens in `tailwind.config.ts`), `src/test/helpers.tsx` fake API for tests.
