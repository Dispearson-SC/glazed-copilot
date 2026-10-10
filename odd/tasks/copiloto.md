# Feature: copiloto

## Objective
Implement the "Copiloto de decisiones" handoff (`glazed-copiloto-handoff.zip`: `HANDOFF.md` plus `design/{Copiloto,Main,Login,Chat}.dc.html`) pixel perfect in `frontend/`, filled with real backend data. Produce a gap list: what data the design needs that the backend does not serve yet.

## Why
User request (2026-10-10): the user strongly prefers this design over the previous pixel-perfect port.

## Scope (authorized)
`frontend/` only, branch `feat/copiloto` stacked on `feat/glazed-co-pixel-perfect` @ 36edca3 (worktree `glazed-copilot-wt/copiloto`). No backend changes, no push. Core merges and deploys.

## Design source
The handoff is extracted at `scratchpad/handoff/glazed-copiloto-handoff/`. The `.dc.html` files are the exact visual reference: copy measurements, colors, radii, shadows, typography and icons from their inline styles. Do not copy the runtime syntax (`{{ }}`, `sc-if`, `sc-for`). The `<script>` `Component` class in `Copiloto.dc.html` is the behavior specification. Main, Login and Chat are realigned to their `.dc.html`. `/copiloto` is new, with 5 windows and the capsule nav.

## Data rule
The UI does not calculate: every number comes from the backend. Where the backend lacks data, show an honest empty state ("Sin datos" / "Disponible pronto") and record the gap. Never fake values. Product photos from the handoff are coffee crops of `screen.png` and do not match our products, so use the initials thumbnail.

## Real API mapping (public `/api/v1`, case-scoped)
| Design | Source |
|---|---|
| Approval items (N2/N3) and tech decisions | `GET /cases/{id}/issues` (options with `tier`, `confidence`, deadline, `expected_benefit_usd`, `if_act`, `if_not`), `GET /alerts?store_id=`, `GET /cases/{id}/order-plan` |
| Aceptar / Aprobar | `POST /proposals {case_id, issue_id, option_id, rationale}` then `POST /proposals/{id}/decision {approved: true}` with `Idempotency-Key` |
| Rechazar + motivo | same, with `{approved: false, reason}`; the backend classifies `reason_category` (Jev) |
| Chat / Analizar / Dialogar | existing useChat: `POST /cases/{id}/messages` + `/turns` polling (no SSE). Context is prefixed into the text. |
| Sucursal Ayer | `day-summary?date=as_of-1` (actuals plus vs-average) |
| Sucursal Hoy | `forecast` for `as_of` (expected); real sales shown as "Pendiente · Se registra al cierre" per the design |
| Sucursal Mañana | `forecast` for `as_of+1` |
| Clima | `context.weather` (observed; Ayer only) |
| Merma / venta perdida | `kpis`, `expiring` |
| Inventario | `GET /cases/{id}/inventory`, `inventory/projection` |
| Programados | `GET /cases/{id}/deliveries`, `order-plan` |
| Memorias | `GET /cases/{id}/history` (`decision_log`); rejections add a local "Nuevo aprendizaje" entry only after the backend accepted the decision |
| Advertencias | `GET /alerts?store_id=`, `issues?category=integrity` |
| Badges | counts of pending items from the sources above |

## TDD
Strict. Runner: `cd frontend && npm test -- --run`; plus `npm run build` and `npx tsc --noEmit`.

## Tasks
- [x] T1 (dfecad6) Tokens and fonts per the handoff (partition, elevation, card/hero/sheet shadows; Playfair/Plus Jakarta), plus the shared copilot shell: CopilotTopBar, CapsuleNav with badges, AgentOrb, Toast, `/copiloto` route and state store. Route: delegated writer.
- [x] T2 (e9d9ced) Agente window over useChat (orb, status, pinned context, suggestions, composer, AnalysisCard). Route: delegated writer.
- [x] T3 (ca8bf87) Decisiones window (ApprovalCard, TechDecisionCard, ⋯ menu, RejectSheet) wired to proposals/decision. Route: delegated writer.
- [x] T4 (d803d40) Sucursal window (Ayer/Hoy/Mañana, sales card, weather, KPIs, inventory, scheduled purchases). Route: delegated writer.
- [x] T5 Memorias and Advertencias windows. Route: delegated writer.
- [ ] T6 Realign Main, Login and Chat to their `.dc.html`; BottomNav "Chat" → "Copiloto". Route: delegated writer.
- [ ] T7 390px screenshots vs the designs, README, and the GAP LIST (design field → backend status). Route: delegated writer.

## Progress
- 2026-10-10: worktree created; all mapped routes answer 200 on :8100.
- T1 done: RED observed (4 files failing: theme, copilotStore, shell, App), GREEN 210/210 tests (187 baseline + 23), `npm run build` ok, `tsc --noEmit` ok. Route: inline single writer (no sub-agents; instruction said single writer). Deviation: top bar shows the branch name instead of the store code ("users never see the code").
- T2 done: RED observed (agent.test, chatHistory ts, useChat display failing), GREEN 235/235 tests, build ok, tsc ok. Adds Issue/OrderPlan/Alert API types, `api.listIssues/getOrderPlan/listAlerts/propose`, decision adapters in `src/data/copilot.ts`, AgentWindow, AnalysisCard; `ChatMessage.ts` (message time); `useChat.send(text, {display})`.

- T3 done: RED observed (CopilotPage.test 11 failing), GREEN 246/246, build ok, tsc ok. Decisiones window (ApprovalCard, TechDecisionCard, ⋯ menu, RejectSheet) wired to `POST /proposals` + `POST /proposals/{id}/decision` with Idempotency-Key; local state changes only after the backend accepts. `useCopilotData`, `useDecide`.

- T4 done: RED observed (branch.test 7 and CopilotBranch.test 9 failing), GREEN 265/265, build ok, tsc ok. Sucursal window (Ayer/Hoy/Mañana) over forecast, day-summary (Ayer), kpis, expiring, inventory, deliveries, order-plan; Hoy/Mañana adapter prefers `/outlook` when it answers. Hoy never shows actual sales. Inventory pill shows days of cover (no invented status).

- T5 done: RED observed (memories.test and CopilotMemAlerts.test failing), GREEN 282/282, build ok, tsc ok. Memorias (decision_log + supplier performance + session learnings) and Advertencias (open alerts + integrity issues; no Revertir; Automáticas empty state; Preguntar sends the question to the chat with context).

## Coordinator decisions applied (2026-10-10)
- Approvals = `/issues` whose recommended option tier is N2/N3; technical = order-plan lines plus issue options with tier N1. Tiers are the backend's. Order-plan lines without issue/option are read-only with "Disponible pronto".
- No N1 auto-execution exists: no "Revertir"; the "Automáticas" filter shows its empty state.
- Mañana weather: "Sin pronóstico", permanent. `/forecast?level=store` is live (new `calibration`, `band_method` fields; band rendered as a plain range).
- Each not-yet-served source is one function in `src/data/copilot.ts` returning `{status:"soon"}` (UI: "Disponible pronto").

## GAP LIST
Format: design element | needed field/endpoint | current backend status | suggested contract.

| Design element | Needed field/endpoint | Backend status | Suggested contract |
|---|---|---|---|
| Analyze/dialogue context in chat | `context` on messages | missing (context is prefixed into the text: `chatContextText`) | `POST /cases/{id}/messages {text, context:{issue_id, option_id?, mode}}` |
| Analysis card sections (Problema/Pros/Contras...) | per-issue analysis | missing (sections are built from issue fields, backend strings in English) | `GET /cases/{id}/issues/{issue_id}/analysis -> {problem[], recommendation[], pros[], cons[], approval[]}` in Spanish |
| Approvals vs technical lists | pending split | partial (derived from `/issues` + `/order-plan` + `/proposals`) | `GET /cases/{id}/decisions/pending -> {approvals, technical}` |
| Aceptar/Aprobar in one call | atomic decision | partial (2 calls: `POST /proposals`, `POST /proposals/{id}/decision`) | `POST /cases/{id}/decisions {issue_id, option_id, approved, reason?}` |
| Order-plan line without issue | decidable option | partial (read-only card, "Disponible pronto") | every line carries `issue` + winning `option_id` |
| Hour deadline ("Hoy antes de 14:00") | time of day in urgency | missing (date only) | `urgency.deadline_at` ISO datetime |
| Expected visits, weather forecast (Hoy/Mañana) | `/forecast?metric=traffic|weather` | missing (Mañana: "Sin pronóstico", permanent) | `/forecast?metric=traffic -> points[{date,value,p10,p90}]` |
| Expected orders, ticket, conversion (Hoy/Mañana) | forecast of transactions/ticket/conversion | missing | `/forecast?metric=transactions|ticket|conversion` |
| Forecast confidence "Pronóstico 80%" | forecast confidence | partial (`calibration`, `band_method`, `metrics_to_date` null) | `calibration.coverage` as a number |
| Expected sales Ayer / Hoy / Mañana | `/forecast?level=store&from=as_of-1&to=as_of+1` | exists (now returns past and as_of points with `actual`; Hoy's actual is never rendered) | none |
| Hoy/Mañana orders, ticket, waste, lost sales ranges | `GET /cases/{id}/outlook?days=2` | approved, answers 404 today -> "Disponible pronto" (adapter `fetchOutlook`; shape as proposed, unverified) | `{days:[{date, net_sales{low,mid,high}, transactions, ticket, expected_waste_usd, expected_lost_sales_usd, weather:null}]}` |
| Conversion (Hoy/Mañana) | expected conversion | missing | add `conversion{low,mid,high}` to outlook days |
| Ayer waste (per day) | real waste of a given day | missing (only 7-day `kpis.waste_usd`) | `/kpis?date_from=&date_to=` already supports a window: expose per-day |
| Expected waste per day | per-day waste forecast and per-day real waste | partial (`/expiring.by_day` forward; `/kpis.waste_usd` 7-day) | `/kpis?date=` or `/expiring` for a given day |
| Inventory pill critical/follow-up/ok | status fields | missing (UI shows days of cover instead) | `inventory.items[].status: critical|watch|ok` |
| Memorias (Proveedores/Demanda/Eventos/Preferencias) | memory store with category, source, case count | missing (only `history.decision_log` and `suppliers/performance`) | `GET /cases/{id}/memories -> [{id, category, text, source, n_cases, confidence, created_at}]` |
| Alert severity/tone (Crítica/Seguimiento) | `severity` level on alerts | missing (all open alerts show "Seguimiento"; integrity "Datos") | `severity: critical|watch|info` |
| Alert category, agent, time | `category`, `agent_id` on alerts | missing (`alert_type` numeric, no agent, mixed old cases) | `GET /alerts` with `category: operacion|datos|auto`, `agent_id`, `created_at` |
| N1 automatic actions + Revertir | `GET /cases/{id}/autonomy/log`, revert | missing (N1 auto-execution does not exist; button hidden) | `GET /cases/{id}/autonomy/log`, `POST /cases/{id}/autonomy/{action_id}/revert` |
| "6 agentes conectados" | `GET /agents/status` | missing (orb shows "Listo"/"Pensando…") | `GET /agents/status -> [{agent_id, name, state}]` |
| "Consultando a Abastecimiento y Pasado…" | turn `progress[]` | missing (shows "Esperando respuesta…") | `GET /turns/{id}` -> `progress:[{agent, state}]` |
| Capsule badges | `GET /cases/{id}/inbox-counts` | missing (counted from loaded lists) | `{decisiones, memorias, alertas}` |
| Product photos | image URL per SKU | missing (initials thumbnail) | `products[].image_url` |
| Spanish narrative | backend text fields (`urgency.reason`, `risk[]`, `tier_reasons[]`) are English | partial (shown as received) | return Spanish or codes |
