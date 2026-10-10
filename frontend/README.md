# Glazed frontend

Minimal React + Vite + TypeScript app, PWA-ready (web manifest + service worker via `vite-plugin-pwa`; installable, no push yet). Talks to the backend through the public API (`/api/v1/*`).

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
| `VITE_API_URL` | dev: empty (Vite proxy to `http://localhost:8080`); build: `http://localhost:8080` | Backend base URL. In dev it is also the proxy target. |

## Pages

- `/alerts`: store selector, alerts of the store (auto-refresh every 10 s), "Marcar vista", and a detail panel with the issue payload and pending proposals (Aprobar / Rechazar with reason).
- `/stores/:storeId/trace?case=&turn=`: agent inspector. Pick a case; see the trace as a chronological conversational channel (from -> to bubbles, kind, expandable payload) and as one lane per agent (orchestrator highlighted). With `turn=<id>` it polls every 3 s while the turn is `pending`.
- `/cases`: list, create and fork cases, and an "ask" box that posts a message to a case and shows the reply when the turn finishes (with a link to its trace).

All pages show error and empty states when the backend is unreachable.

## API assumptions

`TraceEvent` is `{event_id?, case_id, store_id, ts, from_agent, to_agent, kind: message|tool_call|tool_result|escalation, payload}`. Agent ids for lanes: `orchestrator, present, past, supply, strategist, sentinel, auditor, liaison`; any other id (for example `manager`) appears in the timeline only. Payload summary uses `payload.text`, else `payload.tool`, else JSON.

## Layout

`src/api.ts` typed client, `src/trace.ts` pure trace helpers, `src/usePolling.ts` polling hook, `src/pages/*` pages, `src/test/helpers.tsx` fake API for tests.
