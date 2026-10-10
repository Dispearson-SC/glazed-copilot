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

The app has four screens: the three below plus `/copiloto`. The three were copied from the Glazed-Co design (github.com/CesarOliva/Glazed-Co @ b9d4132: markup, Tailwind classes, spacing, Material Symbols icons). Any other path redirects to `/`.

- `/` (Resumen): dashboard of the current case's store, from the simulation clock (never the wall clock). Header with "Fecha simulada" and the sim date, hero with the day's net sales, delta and progress against the same-weekday average, metric cards (transactions, average ticket, units), "Ventas por día" chart (7 actual days plus up to 3 projected days, model name captioned), top 3 products, link to the chat and "Datos al <as_of>". A floating chat bubble opens a compact chat.
- `/login`: store and case picker (no credentials; access control is the reverse proxy's basic auth). The choice lives in `SessionContext` (`storeId`, `caseId`).
- `/chat`: full chat with the copilot over the same logic as the floating panel (turn history, polling, inline pending proposals with Aprobar/Rechazar, reply chip).

- `/copiloto`: the decision copilot (handoff `Copiloto.dc.html`), five windows behind a capsule navigation. It wires real data only; whatever the backend does not serve yet shows "Sin datos" / "Disponible pronto" (see the GAP LIST in `odd/tasks/copiloto.md`).
  - Agente: the chat over `useChat` (polling, history, inline proposals, markdown), pinned context ("Hablando de: ..."), suggestions and analysis/dialogue cards. The context is prefixed into the message text (`chatContextText`) until `POST /messages` accepts a `context` field.
  - Decisiones: approvals = `/issues` whose recommended option is N2/N3; technical = `/order-plan` lines (plus N1 issue options). Aceptar/Aprobar/Rechazar run `POST /proposals` then `POST /proposals/{id}/decision` with Idempotency-Key; the card, toast and learned memory change only after the backend accepted. An order-plan line without issue is read-only.
  - Sucursal: Ayer (day-summary + vs same-weekday average), Hoy and Mañana (forecast / `/outlook` when deployed). Today's real sales are never shown ("Pendiente · Se registra al cierre"). Mañana weather is permanently "Sin pronóstico".
  - Memorias: `/history` decision log, `/suppliers/performance`, plus rejections taught in this session. Advertencias: open `/alerts` and integrity issues; no "Revertir" (N1 auto-execution does not exist).
  - Each source not served yet is one function in `src/data/copilot.ts` returning `{status: "soon"}`; swapping it is a one-line change. `src/data/copilot.ts` holds view-model types and pure adapters only, no sample data.

All pages show error and empty states when the backend is unreachable.

## Dashboard data mapping

| Widget | Source |
|---|---|
| Top bar | `store_display_name` of the active store, Glazed logo |
| Header | "Resumen de hoy"; long date of the day-summary `date`; sim date of the case |
| Hero, metric cards, top products | `GET /cases/{id}/day-summary` (default date = `as_of` - 1) |
| Chart, actual bars | `day-summary?date=D` for the 6 days before the summary date, plus the summary itself |
| Chart, projected bars and caption | `GET /cases/{id}/forecast?level=store` (optional: 404/501/errors just hide them) |

Rules: a day with `totals: null` (HTTP 200) shows "Sin datos", never 0, and a chart day without data is drawn as a dashed stub. HTTP errors (for example 400, date after `as_of`) are an error state, not "Sin datos". Average ticket shows "—" with zero transactions. `staff_hours` is not shown. There is no hourly data, no product photos (thumbnails show initials) and no daily goal: the hero bar compares against the same-weekday average (`weeks_used` weeks as reported). Store names use `display_name`.

## Visual check

Build or run the dev server and compare at 390 px width with the design (`screen.png`, and the handoff's `*.dc.html`, which only render inside the design canvas: expand their `{{ }}`/`sc-if`/`sc-for` with the values of `renderVals()` to get a static page). Note: the backend sends no CORS headers, so use `npm run dev` (Vite proxy), not `vite preview`, against a live backend.

## Layout

`src/api.ts` typed client, `src/format.ts` formatters, `src/usePolling.ts` polling hook, `src/pages/*` the three pages, `src/components/*` design components (top bar, bottom nav, hero, metric cards, activity chart, top products, footer), `src/chat/*` chat view and floating chat, `src/index.css` Tailwind base (tokens in `tailwind.config.ts`, identical to the design's), `src/test/helpers.tsx` fake API for tests.
