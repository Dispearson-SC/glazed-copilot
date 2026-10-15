# Stress battery compare: phase5c -> phase5d

| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |
|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | 17.51 | 8.28 | -9.23 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 | 4.24 | 5.23 | 0.99 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 | 10.31 | 6.26 | -4.05 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 | 18.53 | 12.4 | -6.13 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_stockout_risk | 0 | 7.23 | 5.21 | -2.02 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_expiring_items | 0 | 10.33 | 3.22 | -7.11 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_upcoming_deliveries | 0 | 6.26 | 5.17 | -1.09 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 | 6.23 | 3.19 | -3.04 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_promo_list | 0 | 4.15 | 3.22 | -0.93 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_data_integrity | 0 | 7.27 | 4.31 | -2.96 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_transfer_options | 0 | 48.17 | 14.45 | -33.72 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 | 18.47 | 7.26 | -11.21 | done -> done | 3 -> 2 | 0 -> 0 | - | - |
| specialist_supply | 0 | 23.68 | 14.46 | -9.22 | done -> done | 2 -> 2 | 0 -> 0 | - | - |
| specialist_strategist | 0 | 17.47 | 7.26 | -10.21 | done -> done | 4 -> 4 | 0 -> 0 | - | - |
| multi_specialist | 0 | 145.8 | 32.04 | -113.76 | done -> done | 4 -> 8 | 3 -> 2 | - | - |
| proposal | 0 | 81.31 | 7.22 | -74.09 | done -> done | 4 -> 2 | 2 -> 0 | - | - |
| unsupported | 0 | 15.41 | 11.38 | -4.03 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 0 | 12.35 | 5.2 | -7.15 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 | 19.51 | 6.27 | -13.24 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 2 | 10.4 | 5.22 | -5.18 | done -> done | 0 -> 0 | 0 -> 0 | - | - |
| burst | 0 | 6.55 | 4.54 | -2.01 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 1 | 6.56 | 9.62 | 3.06 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 | 5.48 | 6.65 | 1.17 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 | 5.46 | 3.53 | -1.93 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 4 | 28.89 | 5.59 | -23.3 | done -> done | 2 -> 1 | 0 -> 0 | - | - |

## Aggregates

| metric | before | after | delta |
|---|---|---|---|
| latency_p50_s | 10.4 | 6.26 | -4.14 |
| latency_p95_s | 81.31 | 14.46 | -66.85 |
| latency_max_s | 145.8 | 32.04 | -113.76 |
| first_text_p50_s | 5.14 | 3.08 | -2.06 |
| first_text_p95_s | 14.97 | 12.53 | -2.44 |
| failure_rate | 0 | 0 | 0 |
| tool_calls_total | 38 | 38 | 0 |
| peer_asks_total | 6 | 3 | -3 |

- flags before: {}
- flags after: {}
- burst before: {"turns": 5, "failed": 0, "latency_max_s": 28.89, "latency_p50_s": 6.55}
- burst after: {"turns": 5, "failed": 0, "latency_max_s": 9.62, "latency_p50_s": 5.59}


## Phase 5d routing (read from audit_turn_routes / audit_turn_intents / turns / turn_events)

Deployed: Agent-Core 92758eb (reasoning_effort low for every glazed role, resumed person turn streamed, orchestrator
peers.visibility full capped 4000 chars; DBOS pin stays agent-core-turns.12, no drain), glazed 3ea8eae (backend SSE
open retry about 3 s). `ask_peer` shape: orchestrator ask_peer calls issued within 1 s count as parallel.
`ask->callee start s`: first orchestrator ask_peer to the first callee `started` event. `deltas after last ask`: reply
chunks the orchestrator streamed after its last ask_peer (0 in every resumed turn of phase5c). Output tokens: sum of
stored usage over every turn of the tree (router, plan, callees, orchestrator).

| case | turn | decision | label | profile | confidence | reason | actor | on behalf of | plan used / reply | intent fallback | ask_peer shape | ask->callee start s | deltas after last ask | output tokens (turn tree) | latency s | first text s | rewritten |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | pass | none_of_these | glazed_orchestrator | 0.97 | escape | - | - | - | - | 0 | - | - | 470 | 8.28 | 4.55 | - |
| intent_day_summary | 0 | intent | day_summary | glazed_present | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | - | - | 398 | 5.23 | 3.01 | - |
| intent_active_issues | 0 | intent | active_issues | glazed_present | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | - | - | 503 | 6.26 | 3.02 | - |
| intent_order_plan | 0 | intent | order_plan | glazed_supply | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | - | - | 2390 | 12.4 | 4.59 | - |
| intent_stockout_risk | 0 | intent | stockout_risk | glazed_supply | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | - | - | 391 | 5.21 | 4.42 | - |
| intent_expiring_items | 0 | intent | expiring_items | glazed_present | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | - | - | 462 | 3.22 | 2.64 | - |
| intent_upcoming_deliveries | 0 | intent | upcoming_deliveries | glazed_supply | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | - | - | 677 | 5.17 | 4.16 | - |
| intent_staffing | 0 | intent | staffing | glazed_strategist | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | - | - | 282 | 3.19 | 2.16 | - |
| intent_promo_list | 0 | intent | promo_list | glazed_strategist | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | - | - | 105 | 3.22 | 2.67 | - |
| intent_data_integrity | 0 | intent | data_integrity | glazed_auditor | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | - | - | 406 | 4.31 | 2.96 | - |
| intent_transfer_options | 0 | pass | request_action | glazed_orchestrator | 0.40 | pass_route | - | - | - | - | 1 | 0.5 | 8 | 850 | 14.45 | 12.53 | - |
| specialist_past | 0 | route | past_experience | glazed_past | 1.00 | - | peer-agent | manager-1 | - | - | 0 | - | - | 457 | 7.26 | 1.8 | - |
| specialist_supply | 0 | route | supply_analysis | glazed_supply | 0.97 | - | peer-agent | manager-1 | - | - | 0 | - | - | 334 | 14.46 | 1.78 | - |
| specialist_strategist | 0 | route | strategy_flow | glazed_strategist | 0.57 | - | peer-agent | manager-1 | - | - | 0 | - | - | 400 | 7.26 | 2.15 | - |
| multi_specialist | 0 | pass | none_of_these | glazed_orchestrator | 0.75 | escape | - | - | - | - | 2 (parallel) | 1.4 | 45 | 4479 | 32.04 | 24.14 | - |
| proposal | 0 | pass | request_action | glazed_orchestrator | 0.90 | pass_route | - | - | - | - | 0 | - | - | 522 | 7.22 | 1.93 | - |
| unsupported | 0 | route | present_metrics | glazed_present | 0.93 | - | peer-agent | manager-1 | - | - | 0 | - | - | 273 | 11.38 | 6.64 | - |
| follow_up | 0 | intent | stockout_risk | glazed_supply | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | - | - | 372 | 5.2 | 3.66 | - |
| follow_up | 1 | skip | - | glazed_orchestrator | - | follow_up | - | - | - | - | 0 | - | - | 491 | 6.27 | 3.65 | - |
| follow_up | 2 | skip | - | glazed_orchestrator | - | follow_up | - | - | - | - | 0 | - | - | 272 | 5.22 | 2.61 | - |
| burst | 0 | intent | day_summary | glazed_present | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | - | - | 135 | 4.54 | 3.08 | - |
| burst | 1 | intent | active_issues | glazed_present | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | - | - | 186 | 9.62 | 9.16 | - |
| burst | 2 | intent | upcoming_deliveries | glazed_supply | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | - | - | 115 | 6.65 | 5.68 | - |
| burst | 3 | intent | promo_list | glazed_strategist | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | - | - | 76 | 3.53 | 2.76 | - |
| burst | 4 | route | present_metrics | glazed_present | 0.93 | - | peer-agent | manager-1 | - | - | 0 | - | - | 364 | 5.59 | 3.46 | - |

Decisions: {"pass": 4, "intent": 14, "route": 5, "skip": 2}
Backend quality-guard rewrites kept: 0

Notes:
- Resumed replies stream now: the two orchestrator turns that asked specialists streamed their final reply after the
  answers (`multi_specialist` 45 chunks, `intent_transfer_options` 8). Both report `first_text_s` for the first time
  (24.1 s and 12.5 s); 25 of 25 turns report first text (phase5c: 23). First text p50 5.1 -> 3.1 s, p95 15.0 -> 12.5 s.
- No summary call before an ask: the ask -> callee start gap is 0.5-1.4 s (phase5c 2.4-10.5 s).
- `multi_specialist` 145.8 -> 32.0 s. Timeline: briefing 1.9 s, asks at 4.5 s (2 in parallel, 1 ms apart), callees start
  1.4 s later, strategist 6.0 s and supply 12.7 s (5 tools in one round), 4.0 s to 5 `propose_action` calls, then 7.3 s
  of streamed compose. Asked 2 specialists (supply, strategist) instead of 3; the expiry part came from supply.
  The 5 unrequested `propose_action` calls are not new (phase3 and phase5b did the same; phase5c did none).
- `proposal` 81.3 -> 7.2 s: the orchestrator proposed directly again (0 asks, as in phase5b; phase5c consulted 2
  specialists first). Pending-proposal check passes. The persona choice (direct vs consult first) is still open.
- Reasoning effort low: no provider refusal of `reasoning_effort` in the core, peer-worker or backend logs.
- Quality: no battery flags, but a text scan of the replies finds 7 garbled fragments in phase5d (6 in
  `multi_specialist`: "y， merma", "en1 de cada 10", "**:asek.recibidos", "Pedido inflationado, mismo trusted.",
  "hoyusted") against 2 in phase5c and 2 in phase5b. Same class of model artefact as before, more of it in the
  longest reply; the battery's quality checks do not catch it. Watch it in the next runs before attributing it to
  the low reasoning effort.
- Single run per stage: LLM variance applies.
