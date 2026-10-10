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
- [x] T1 Tokens and fonts per the handoff (partition, elevation, card/hero/sheet shadows; Playfair/Plus Jakarta), plus the shared copilot shell: CopilotTopBar, CapsuleNav with badges, AgentOrb, Toast, `/copiloto` route and state store. Route: delegated writer.
- [ ] T2 Agente window over useChat (orb, status, pinned context, suggestions, composer, AnalysisCard). Route: delegated writer.
- [ ] T3 Decisiones window (ApprovalCard, TechDecisionCard, ⋯ menu, RejectSheet) wired to proposals/decision. Route: delegated writer.
- [ ] T4 Sucursal window (Ayer/Hoy/Mañana, sales card, weather, KPIs, inventory, scheduled purchases). Route: delegated writer.
- [ ] T5 Memorias and Advertencias windows. Route: delegated writer.
- [ ] T6 Realign Main, Login and Chat to their `.dc.html`; BottomNav "Chat" → "Copiloto". Route: delegated writer.
- [ ] T7 390px screenshots vs the designs, README, and the GAP LIST (design field → backend status). Route: delegated writer.

## Progress
- 2026-10-10: worktree created; all mapped routes answer 200 on :8100.
- T1 done: RED observed (4 files failing: theme, copilotStore, shell, App), GREEN 210/210 tests (187 baseline + 23), `npm run build` ok, `tsc --noEmit` ok. Route: inline single writer (no sub-agents; instruction said single writer). Deviation: top bar shows the branch name instead of the store code ("users never see the code").
