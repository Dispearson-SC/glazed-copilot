# Stress battery compare: phase5 -> phase5b

| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |
|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | 7.71 | 15.46 | 7.75 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 | 78.68 | 7.26 | -71.42 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 | 83.82 | 6.25 | -77.57 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 | 112.29 | 12.29 | -100 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_stockout_risk | 0 | 42.6 | 8.19 | -34.41 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_expiring_items | 0 | 10.37 | 4.18 | -6.19 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_upcoming_deliveries | 0 | 46.72 | 4.18 | -42.54 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 | 11.55 | 4.23 | -7.32 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_promo_list | 0 | 6.31 | 4.24 | -2.07 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_data_integrity | 0 | 22.82 | 4.18 | -18.64 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_transfer_options | 0 | 27.28 | 101.63 | 74.35 | done -> done | 2 -> 3 | 1 -> 2 | - | - |
| specialist_past | 0 | 12.53 | 22.52 | 9.99 | done -> done | 3 -> 4 | 0 -> 0 | - | - |
| specialist_supply | 0 | 7.33 | 18.41 | 11.08 | done -> done | 2 -> 2 | 0 -> 0 | internal_names | - |
| specialist_strategist | 0 | 9.42 | 11.37 | 1.95 | done -> done | 4 -> 4 | 0 -> 0 | - | - |
| multi_specialist | 0 | 133.61 | 147.72 | 14.11 | done -> done | 6 -> 8 | 3 -> 2 | - | - |
| proposal | 0 | 38.31 | 22.49 | -15.82 | done -> done | 1 -> 2 | 0 -> 0 | - | check:proposal_pending |
| unsupported | 0 | 11.52 | 8.29 | -3.23 | done -> done | 2 -> 1 | 0 -> 0 | - | - |
| follow_up | 0 | 37.23 | 9.22 | -28.01 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 | 39.39 | 18.45 | -20.94 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 2 | 21.98 | 14.41 | -7.57 | done -> done | 1 -> 0 | 0 -> 0 | - | - |
| burst | 0 | 10.85 | 4.54 | -6.31 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 1 | 5.56 | 7.61 | 2.05 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 | 30.41 | 9.56 | -20.85 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 | 4.61 | 6.52 | 1.91 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 4 | 7.77 | 13.75 | 5.98 | done -> done | 3 -> 1 | 0 -> 0 | - | - |

## Aggregates

| metric | before | after | delta |
|---|---|---|---|
| latency_p50_s | 21.98 | 9.22 | -12.76 |
| latency_p95_s | 112.29 | 101.63 | -10.66 |
| latency_max_s | 133.61 | 147.72 | 14.11 |
| first_text_p50_s | - | - | - |
| first_text_p95_s | - | - | - |
| failure_rate | 0 | 0 | 0 |
| tool_calls_total | 40 | 41 | 1 |
| peer_asks_total | 4 | 4 | 0 |

- flags before: {"check:proposal_pending": 1}
- flags after: {"internal_names": 1}
- burst before: {"turns": 5, "failed": 0, "latency_max_s": 30.41, "latency_p50_s": 7.77}
- burst after: {"turns": 5, "failed": 0, "latency_max_s": 13.75, "latency_p50_s": 7.61}

## All stages per case (baseline / phase3 / phase5 / phase5b)

| case | turn | latency s (base / p3 / p5 / p5b) | tools | peers |
|---|---|---|---|---|
| simple | 0 | 13.67 / 10.45 / 7.71 / 15.46 | 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 |
| intent_day_summary | 0 | 12.6 / 8.42 / 78.68 / 7.26 | 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 |
| intent_active_issues | 0 | 14.64 / 12.48 / 83.82 / 6.25 | 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 |
| intent_order_plan | 0 | 10.47 / 9.39 / 112.29 / 12.29 | 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 |
| intent_stockout_risk | 0 | 40.14 / 36.72 / 42.6 / 8.19 | 2 / 2 / 1 / 1 | 1 / 1 / 0 / 0 |
| intent_expiring_items | 0 | 31.61 / 23.09 / 10.37 / 4.18 | 2 / 2 / 1 / 1 | 1 / 1 / 0 / 0 |
| intent_upcoming_deliveries | 0 | 5.36 / 5.25 / 46.72 / 4.18 | 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 |
| intent_staffing | 0 | 26.39 / 47.25 / 11.55 / 4.23 | 2 / 2 / 1 / 1 | 1 / 1 / 0 / 0 |
| intent_promo_list | 0 | 13.73 / 15.77 / 6.31 / 4.24 | 2 / 2 / 1 / 1 | 1 / 1 / 0 / 0 |
| intent_data_integrity | 0 | 12.65 / 25.29 / 22.82 / 4.18 | 2 / 2 / 1 / 1 | 1 / 1 / 0 / 0 |
| intent_transfer_options | 0 | 28.45 / 30.4 / 27.28 / 101.63 | 2 / 2 / 2 / 3 | 1 / 1 / 1 / 2 |
| specialist_past | 0 | 21.0 / 22.14 / 12.53 / 22.52 | 2 / 2 / 3 / 4 | 1 / 1 / 0 / 0 |
| specialist_supply | 0 | 4.25 / 5.38 / 7.33 / 18.41 | 1 / 1 / 2 / 2 | 0 / 0 / 0 / 0 |
| specialist_strategist | 0 | 18.94 / 17.93 / 9.42 / 11.37 | 2 / 2 / 4 / 4 | 1 / 1 / 0 / 0 |
| multi_specialist | 0 | 97.82 / 78.81 / 133.61 / 147.72 | 3 / 8 / 6 / 8 | 2 / 2 / 3 / 2 |
| proposal | 0 | 32.61 / 8.37 / 38.31 / 22.49 | 3 / 2 / 1 / 2 | 1 / 0 / 0 / 0 |
| unsupported | 0 | 11.58 / 5.29 / 11.52 / 8.29 | 2 / 1 / 2 / 1 | 1 / 0 / 0 / 0 |
| follow_up | 0 | 15.69 / 54.73 / 37.23 / 9.22 | 1 / 2 / 1 / 1 | 0 / 1 / 0 / 0 |
| follow_up | 1 | 14.58 / 15.72 / 39.39 / 18.45 | 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 |
| follow_up | 2 | 43.79 / 5.26 / 21.98 / 14.41 | 2 / 0 / 1 / 0 | 1 / 0 / 0 / 0 |
| burst | 0 | 22.71 / 17.28 / 10.85 / 4.54 | 2 / 2 / 1 / 1 | 1 / 1 / 0 / 0 |
| burst | 1 | 62.69 / 6.56 / 5.56 / 7.61 | 2 / 1 / 1 / 1 | 1 / 0 / 0 / 0 |
| burst | 2 | 4.69 / 5.6 / 30.41 / 9.56 | 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 |
| burst | 3 | 15.17 / 24.67 / 4.61 / 6.52 | 2 / 2 / 1 / 1 | 1 / 1 / 0 / 0 |
| burst | 4 | 41.52 / 26.55 / 7.77 / 13.75 | 2 / 2 / 3 / 1 | 1 / 1 / 0 / 0 |

first_text_s non-null turns: {'baseline': 0, 'phase3': 0, 'phase5': 0, 'phase5b': 0}

## Phase 5b routing (read from audit_turn_routes / audit_turn_intents / audit_turn_costs / glazed.turns)

Deployed: Agent-Core 0e4d480 (compose capped at AGENT_CORE_COMPOSE_MAX_TOKENS=4096 with reasoning effort low, follow-ups
not routed, labelled pass for requests to act), glazed c27dc4a (SSE open retried on 404). System One router jev-1.13.0.
`skip` = follow-up turn not routed (reason `follow_up`, runs the orchestrator with history).

| case | turn | decision | label | profile | confidence | reason | actor | on behalf of | plan used / reply | intent fallback | turn output tokens | latency s | first text s | rewritten |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | pass | none_of_these | glazed_orchestrator | 0.97 | escape | - | - | - | - | 1637 | 15.46 | - | - |
| intent_day_summary | 0 | intent | day_summary | glazed_present | 1.00 | - | peer-agent | manager-1 | t / compose | - | 366 | 7.26 | - | - |
| intent_active_issues | 0 | intent | active_issues | glazed_present | 1.00 | - | peer-agent | manager-1 | t / compose | - | 380 | 6.25 | - | - |
| intent_order_plan | 0 | intent | order_plan | glazed_supply | 1.00 | - | peer-agent | manager-1 | t / compose | - | 1879 | 12.29 | - | - |
| intent_stockout_risk | 0 | intent | stockout_risk | glazed_supply | 1.00 | - | peer-agent | manager-1 | t / compose | - | 913 | 8.19 | - | - |
| intent_expiring_items | 0 | intent | expiring_items | glazed_present | 1.00 | - | peer-agent | manager-1 | t / compose | - | 360 | 4.18 | - | - |
| intent_upcoming_deliveries | 0 | intent | upcoming_deliveries | glazed_supply | 1.00 | - | peer-agent | manager-1 | t / compose | - | 389 | 4.18 | - | - |
| intent_staffing | 0 | intent | staffing | glazed_strategist | 1.00 | - | peer-agent | manager-1 | t / compose | - | 304 | 4.23 | - | - |
| intent_promo_list | 0 | intent | promo_list | glazed_strategist | 1.00 | - | peer-agent | manager-1 | t / compose | - | 150 | 4.24 | - | - |
| intent_data_integrity | 0 | intent | data_integrity | glazed_auditor | 1.00 | - | peer-agent | manager-1 | t / compose | - | 352 | 4.18 | - | - |
| intent_transfer_options | 0 | pass | request_action | glazed_orchestrator | 0.38 | pass_route | - | - | - | - | - | 101.63 | - | - |
| specialist_past | 0 | route | past_experience | glazed_past | 0.99 | - | peer-agent | manager-1 | - | - | 1446 | 22.52 | - | - |
| specialist_supply | 0 | route | supply_analysis | glazed_supply | 0.99 | - | peer-agent | manager-1 | - | - | 1341 | 18.41 | - | - |
| specialist_strategist | 0 | route | strategy_flow | glazed_strategist | 0.54 | - | peer-agent | manager-1 | - | - | 1041 | 11.37 | - | - |
| multi_specialist | 0 | pass | none_of_these | glazed_orchestrator | 0.76 | escape | - | - | - | - | - | 147.72 | - | - |
| proposal | 0 | pass | request_action | glazed_orchestrator | 0.94 | pass_route | - | - | - | - | 2141 | 22.49 | - | - |
| unsupported | 0 | route | present_metrics | glazed_present | 0.93 | - | peer-agent | manager-1 | - | - | 415 | 8.29 | - | - |
| follow_up | 0 | intent | stockout_risk | glazed_supply | 1.00 | - | peer-agent | manager-1 | t / compose | - | 503 | 9.22 | - | - |
| follow_up | 1 | skip | - | glazed_orchestrator |  | follow_up | - | - | - | - | 936 | 18.45 | - | - |
| follow_up | 2 | skip | - | glazed_orchestrator |  | follow_up | - | - | - | - | 622 | 14.41 | - | - |
| burst | 0 | intent | day_summary | glazed_present | 1.00 | - | peer-agent | manager-1 | t / compose | - | 113 | 4.54 | - | - |
| burst | 1 | intent | active_issues | glazed_present | 1.00 | - | peer-agent | manager-1 | t / compose | - | 297 | 7.61 | - | - |
| burst | 2 | intent | upcoming_deliveries | glazed_supply | 1.00 | - | peer-agent | manager-1 | t / compose | - | 163 | 9.56 | - | - |
| burst | 3 | intent | promo_list | glazed_strategist | 1.00 | - | peer-agent | manager-1 | t / compose | - | 215 | 6.52 | - | - |
| burst | 4 | route | present_metrics | glazed_present | 0.94 | - | peer-agent | manager-1 | - | - | 1413 | 13.75 | - | - |

Decisions: {"pass": 4, "intent": 14, "route": 5, "skip": 2}
Backend quality-guard rewrites requested: 0 ; kept rewrite: 0
Intent fallbacks: none

Notes:
- Fixed: the 14 intent plans now compose 113-1879 output tokens (phase5: 1.8k-19.6k) and finish in 4-12 s (phase5: up to
  112 s); no plan fell back (no provider refusal of `reasoning_effort`). `proposal` now passes to the orchestrator
  (`pass_route`, request_action 0.94) and the pending-proposal check passes. Follow-ups 1-2 are not routed. Burst max 13.8 s
  (baseline 62.7 s). No backend quality-guard rewrite was needed in this run.
- Still slow (p95/max): `intent_transfer_options` (router below threshold, 0.38 -> orchestrator) asked two specialists one
  after the other this time (liaison 23 s, then present 40 s; 101.6 s total, earlier stages asked one), and
  `multi_specialist` (orchestrator: supply 44.5 s, then strategist 19.6 s, then 37 s of its own composing with five
  `propose_action` calls; 147.7 s). Both are orchestrator turns this deploy did not change: sequential peer asks plus model
  variance. `specialist_supply` routed directly but took 18.4 s (two tools, one model reply).
- first_text_s is still null on every turn. The backend now opens the stream (404s retried, then 200), but Core emits no
  `delta` events: `AGENT_CORE_STREAM_REPLIES` is not set for the core service (default off), and a routed turn runs under
  a peer identity, which `_reply_stream` never streams (`request.owner is not None`). Latencies remain polling latencies.
- The one `internal_names` flag (`specialist_supply`) is `su_meta`: two Spanish words joined with `_` (like `de_no`), likely a false positive.
- Single run per stage: LLM variance applies.
