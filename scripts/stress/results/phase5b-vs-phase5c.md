# Stress battery compare: phase5b -> phase5c

| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |
|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | 15.46 | 17.51 | 2.05 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 | 7.26 | 4.24 | -3.02 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 | 6.25 | 10.31 | 4.06 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 | 12.29 | 18.53 | 6.24 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_stockout_risk | 0 | 8.19 | 7.23 | -0.96 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_expiring_items | 0 | 4.18 | 10.33 | 6.15 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_upcoming_deliveries | 0 | 4.18 | 6.26 | 2.08 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 | 4.23 | 6.23 | 2 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_promo_list | 0 | 4.24 | 4.15 | -0.09 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_data_integrity | 0 | 4.18 | 7.27 | 3.09 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_transfer_options | 0 | 101.63 | 48.17 | -53.46 | done -> done | 3 -> 2 | 2 -> 1 | - | - |
| specialist_past | 0 | 22.52 | 18.47 | -4.05 | done -> done | 4 -> 3 | 0 -> 0 | - | - |
| specialist_supply | 0 | 18.41 | 23.68 | 5.27 | done -> done | 2 -> 2 | 0 -> 0 | - | internal_names |
| specialist_strategist | 0 | 11.37 | 17.47 | 6.1 | done -> done | 4 -> 4 | 0 -> 0 | - | - |
| multi_specialist | 0 | 147.72 | 145.8 | -1.92 | done -> done | 8 -> 4 | 2 -> 3 | - | - |
| proposal | 0 | 22.49 | 81.31 | 58.82 | done -> done | 2 -> 4 | 0 -> 2 | - | - |
| unsupported | 0 | 8.29 | 15.41 | 7.12 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 0 | 9.22 | 12.35 | 3.13 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 | 18.45 | 19.51 | 1.06 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 2 | 14.41 | 10.4 | -4.01 | done -> done | 0 -> 0 | 0 -> 0 | - | - |
| burst | 0 | 4.54 | 6.55 | 2.01 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 1 | 7.61 | 6.56 | -1.05 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 | 9.56 | 5.48 | -4.08 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 | 6.52 | 5.46 | -1.06 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 4 | 13.75 | 28.89 | 15.14 | done -> done | 1 -> 2 | 0 -> 0 | - | - |

## Aggregates

| metric | before | after | delta |
|---|---|---|---|
| latency_p50_s | 9.22 | 10.4 | 1.18 |
| latency_p95_s | 101.63 | 81.31 | -20.32 |
| latency_max_s | 147.72 | 145.8 | -1.92 |
| first_text_p50_s | - | 5.14 | - |
| first_text_p95_s | - | 14.97 | - |
| failure_rate | 0 | 0 | 0 |
| tool_calls_total | 41 | 38 | -3 |
| peer_asks_total | 4 | 6 | 2 |

- flags before: {"internal_names": 1}
- flags after: {}
- burst before: {"turns": 5, "failed": 0, "latency_max_s": 13.75, "latency_p50_s": 7.61}
- burst after: {"turns": 5, "failed": 0, "latency_max_s": 28.89, "latency_p50_s": 6.55}
## All stages per case (baseline / phase3 / phase5 / phase5b / phase5c)

| case | turn | latency s (base / p3 / p5 / p5b / p5c) | first text s p5c | tools | peers |
|---|---|---|---|---|---|
| simple | 0 | 13.67 / 10.45 / 7.71 / 15.46 / 17.51 | 2.83 | 1 / 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 / 0 |
| intent_day_summary | 0 | 12.6 / 8.42 / 78.68 / 7.26 / 4.24 | 2.93 | 1 / 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 / 0 |
| intent_active_issues | 0 | 14.64 / 12.48 / 83.82 / 6.25 / 10.31 | 5.09 | 1 / 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 / 0 |
| intent_order_plan | 0 | 10.47 / 9.39 / 112.29 / 12.29 / 18.53 | 5.83 | 1 / 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 / 0 |
| intent_stockout_risk | 0 | 40.14 / 36.72 / 42.6 / 8.19 / 7.23 | 5.75 | 2 / 2 / 1 / 1 / 1 | 1 / 1 / 0 / 0 / 0 |
| intent_expiring_items | 0 | 31.61 / 23.09 / 10.37 / 4.18 / 10.33 | 7.11 | 2 / 2 / 1 / 1 / 1 | 1 / 1 / 0 / 0 / 0 |
| intent_upcoming_deliveries | 0 | 5.36 / 5.25 / 46.72 / 4.18 / 6.26 | 3.71 | 1 / 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 / 0 |
| intent_staffing | 0 | 26.39 / 47.25 / 11.55 / 4.23 / 6.23 | 3.16 | 2 / 2 / 1 / 1 / 1 | 1 / 1 / 0 / 0 / 0 |
| intent_promo_list | 0 | 13.73 / 15.77 / 6.31 / 4.24 / 4.15 | 2.78 | 2 / 2 / 1 / 1 / 1 | 1 / 1 / 0 / 0 / 0 |
| intent_data_integrity | 0 | 12.65 / 25.29 / 22.82 / 4.18 / 7.27 | 5.14 | 2 / 2 / 1 / 1 / 1 | 1 / 1 / 0 / 0 / 0 |
| intent_transfer_options | 0 | 28.45 / 30.4 / 27.28 / 101.63 / 48.17 | - | 2 / 2 / 2 / 3 / 2 | 1 / 1 / 1 / 2 / 1 |
| specialist_past | 0 | 21.0 / 22.14 / 12.53 / 22.52 / 18.47 | 2.14 | 2 / 2 / 3 / 4 / 3 | 1 / 1 / 0 / 0 / 0 |
| specialist_supply | 0 | 4.25 / 5.38 / 7.33 / 18.41 / 23.68 | 12.73 | 1 / 1 / 2 / 2 / 2 | 0 / 0 / 0 / 0 / 0 |
| specialist_strategist | 0 | 18.94 / 17.93 / 9.42 / 11.37 / 17.47 | 2.36 | 2 / 2 / 4 / 4 / 4 | 1 / 1 / 0 / 0 / 0 |
| multi_specialist | 0 | 97.82 / 78.81 / 133.61 / 147.72 / 145.8 | - | 3 / 8 / 6 / 8 / 4 | 2 / 2 / 3 / 2 / 3 |
| proposal | 0 | 32.61 / 8.37 / 38.31 / 22.49 / 81.31 | 1.6 | 3 / 2 / 1 / 2 / 4 | 1 / 0 / 0 / 0 / 2 |
| unsupported | 0 | 11.58 / 5.29 / 11.52 / 8.29 / 15.41 | 7.24 | 2 / 1 / 2 / 1 / 1 | 1 / 0 / 0 / 0 / 0 |
| follow_up | 0 | 15.69 / 54.73 / 37.23 / 9.22 / 12.35 | 6.72 | 1 / 2 / 1 / 1 / 1 | 0 / 1 / 0 / 0 / 0 |
| follow_up | 1 | 14.58 / 15.72 / 39.39 / 18.45 / 19.51 | 14.97 | 1 / 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 / 0 |
| follow_up | 2 | 43.79 / 5.26 / 21.98 / 14.41 / 10.4 | 7.6 | 2 / 0 / 1 / 0 / 0 | 1 / 0 / 0 / 0 / 0 |
| burst | 0 | 22.71 / 17.28 / 10.85 / 4.54 / 6.55 | 5.34 | 2 / 2 / 1 / 1 / 1 | 1 / 1 / 0 / 0 / 0 |
| burst | 1 | 62.69 / 6.56 / 5.56 / 7.61 / 6.56 | 5.82 | 2 / 1 / 1 / 1 / 1 | 1 / 0 / 0 / 0 / 0 |
| burst | 2 | 4.69 / 5.6 / 30.41 / 9.56 / 5.48 | 5.01 | 1 / 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 / 0 |
| burst | 3 | 15.17 / 24.67 / 4.61 / 6.52 / 5.46 | 4.68 | 2 / 2 / 1 / 1 / 1 | 1 / 1 / 0 / 0 / 0 |
| burst | 4 | 41.52 / 26.55 / 7.77 / 13.75 / 28.89 | 19.52 | 2 / 2 / 3 / 1 / 2 | 1 / 1 / 0 / 0 / 0 |

first_text_s non-null turns: {"base": 0, "p3": 0, "p5": 0, "p5b": 0, "p5c": 23}

## Aggregates per stage

| metric | base | p3 | p5 | p5b | p5c |
|---|---|---|---|---|---|
| latency_p50_s | 15.69 | 15.77 | 21.98 | 9.22 | 10.4 |
| latency_p95_s | 62.69 | 54.73 | 112.29 | 101.63 | 81.31 |
| latency_max_s | 97.82 | 78.81 | 133.61 | 147.72 | 145.8 |
| first_text_p50_s | - | - | - | - | 5.14 |
| first_text_p95_s | - | - | - | - | 14.97 |
| failure_rate | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| tool_calls_total | 43 | 44 | 40 | 41 | 38 |
| peer_asks_total | 17 | 14 | 4 | 4 | 6 |
| burst | {"turns": 5, "failed": 0, "latency_max_s": 62.69, "latency_p50_s": 22.71} | {"turns": 5, "failed": 0, "latency_max_s": 26.55, "latency_p50_s": 17.28} | {"turns": 5, "failed": 0, "latency_max_s": 30.41, "latency_p50_s": 7.77} | {"turns": 5, "failed": 0, "latency_max_s": 13.75, "latency_p50_s": 7.61} | {"turns": 5, "failed": 0, "latency_max_s": 28.89, "latency_p50_s": 6.55} |
| flags | {} | {"internal_names": 1, "untraceable_numbers": 1} | {"check:proposal_pending": 1} | {"internal_names": 1} | {} |

## Phase 5c routing (read from audit_turn_routes / audit_turn_intents / audit_turn_costs / turn_events / glazed.turns)

Deployed: Agent-Core e54fb97 (P11: orchestrator asks independent specialists in the same step; DBOS pin stays
agent-core-turns.12, no drain), glazed 3a37332 (AGENT_CORE_STREAM_REPLIES default true for core and core-peer-worker;
backend follows chunk identity). `ask_peer` shape: groups of orchestrator ask_peer calls issued within 1 s (one step).

| case | turn | decision | label | profile | confidence | reason | actor | on behalf of | plan used / reply | intent fallback | ask_peer shape | turn output tokens | latency s | first text s | rewritten |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | pass | none_of_these | glazed_orchestrator | 0.98 | escape | - | - | - | - | 0 | 1360 | 17.51 | 2.83 | - |
| intent_day_summary | 0 | intent | day_summary | glazed_present | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | 291 | 4.24 | 2.93 | - |
| intent_active_issues | 0 | intent | active_issues | glazed_present | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | 493 | 10.31 | 5.09 | - |
| intent_order_plan | 0 | intent | order_plan | glazed_supply | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | 1228 | 18.53 | 5.83 | - |
| intent_stockout_risk | 0 | intent | stockout_risk | glazed_supply | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | 390 | 7.23 | 5.75 | - |
| intent_expiring_items | 0 | intent | expiring_items | glazed_present | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | 377 | 10.33 | 7.11 | - |
| intent_upcoming_deliveries | 0 | intent | upcoming_deliveries | glazed_supply | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | 468 | 6.26 | 3.71 | - |
| intent_staffing | 0 | intent | staffing | glazed_strategist | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | 313 | 6.23 | 3.16 | - |
| intent_promo_list | 0 | intent | promo_list | glazed_strategist | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | 137 | 4.15 | 2.78 | - |
| intent_data_integrity | 0 | intent | data_integrity | glazed_auditor | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | 413 | 7.27 | 5.14 | - |
| intent_transfer_options | 0 | pass | request_action | glazed_orchestrator | 0.41 | pass_route | - | - | - | - | 1 | - | 48.17 | - | - |
| specialist_past | 0 | route | past_experience | glazed_past | 1.00 | - | peer-agent | manager-1 | - | - | 0 | 1164 | 18.47 | 2.14 | - |
| specialist_supply | 0 | route | supply_analysis | glazed_supply | 0.98 | - | peer-agent | manager-1 | - | - | 0 | 1709 | 23.68 | 12.73 | - |
| specialist_strategist | 0 | route | strategy_flow | glazed_strategist | 0.54 | - | peer-agent | manager-1 | - | - | 0 | 1439 | 17.47 | 2.36 | - |
| multi_specialist | 0 | pass | none_of_these | glazed_orchestrator | 0.76 | escape | - | - | - | - | 3 (parallel) | - | 145.8 | - | - |
| proposal | 0 | pass | request_action | glazed_orchestrator | 0.93 | pass_route | - | - | - | - | 2 (parallel) | - | 81.31 | 1.6 | - |
| unsupported | 0 | route | present_metrics | glazed_present | 0.93 | - | peer-agent | manager-1 | - | - | 0 | 839 | 15.41 | 7.24 | - |
| follow_up | 0 | intent | stockout_risk | glazed_supply | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | 352 | 12.35 | 6.72 | - |
| follow_up | 1 | skip | - | glazed_orchestrator | - | follow_up | - | - | - | - | 0 | 1846 | 19.51 | 14.97 | - |
| follow_up | 2 | skip | - | glazed_orchestrator | - | follow_up | - | - | - | - | 0 | 1022 | 10.4 | 7.6 | - |
| burst | 0 | intent | day_summary | glazed_present | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | 76 | 6.55 | 5.34 | - |
| burst | 1 | intent | active_issues | glazed_present | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | 212 | 6.56 | 5.82 | - |
| burst | 2 | intent | upcoming_deliveries | glazed_supply | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | 172 | 5.48 | 5.01 | - |
| burst | 3 | intent | promo_list | glazed_strategist | 1.00 | - | peer-agent | manager-1 | t / compose | - | 0 | 130 | 5.46 | 4.68 | - |
| burst | 4 | route | present_metrics | glazed_present | 0.93 | - | peer-agent | manager-1 | - | - | 0 | 1492 | 28.89 | 19.52 | - |

Decisions: {"pass": 4, "intent": 14, "route": 5, "skip": 2}
Backend quality-guard rewrites kept: 0
Intent fallbacks: none

Notes:
- Streaming works: 23 of 25 turns report `first_text_s` (every earlier stage: 0); first text p50 5.1 s, p95 15.0 s.
  Intent plans show text at 2.8-7.1 s, routed specialists at 2.1-12.7 s.
- P11 works: the orchestrator issued all its `ask_peer` calls in one step in every turn that asked more than one
  specialist (`multi_specialist` 3 within 3 ms, `proposal` 2 within 1 ms) and the callees ran concurrently.
- Still slow: `multi_specialist` 145.8 s even with 3 parallel asks. Timeline: briefing 1.8 s, 14 s of orchestrator
  reasoning before the asks, 7.3 s from the asks to the callees starting, then the slowest callee (supply, 7 tools in
  3 rounds, 70.1 s) bounds the fan-out, then 51 s of orchestrator composing. Parallelism removed the sum of callees
  (phase5b: 44.5 s + 19.6 s sequential) but the slowest callee and the final compose dominate.
- Regression: `proposal` 22.5 s -> 81.3 s. With P11 the orchestrator now consults present and supply (in parallel,
  36-47 s) before `propose_action`; phase5b proposed directly. Pending-proposal check still passes.
- `first_text_s` is null on the two orchestrator turns whose answer comes after peer asks (`multi_specialist`,
  `intent_transfer_options`): turn_events hold no `delta` after the first `ask_peer` in any orchestrator turn of this
  run (`proposal` streamed only its pre-ask text, 1.6 s). The final reply of an orchestrator turn resumed after a peer
  answer is not streamed.
- Peer dispatch gap: 2.4-10.5 s between the orchestrator's `ask_peer` and the callee's `started` event.
- `intent_transfer_options` 101.6 s -> 48.2 s: one specialist this time (liaison 29.6 s), router still below threshold (0.41).
- `burst[4]` 13.8 s -> 28.9 s (routed present_metrics, 1492 output tokens): model variance on a routed specialist.
- The backend's SSE open retries (0.15/0.3/0.6 s on 404) can run out before a routed turn exists: in the smoke run
  the first intent turn after restart (router 596 ms) got four 404s and reported no first text; in this run every
  intent turn streamed.
- Single run per stage: LLM variance applies.
