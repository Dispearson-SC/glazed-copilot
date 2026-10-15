# Stress battery compare: baseline -> phase5

| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |
|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | 13.67 | 7.71 | -5.96 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 | 12.6 | 78.68 | 66.08 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 | 14.64 | 83.82 | 69.18 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 | 10.47 | 112.29 | 101.82 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_stockout_risk | 0 | 40.14 | 42.6 | 2.46 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_expiring_items | 0 | 31.61 | 10.37 | -21.24 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_upcoming_deliveries | 0 | 5.36 | 46.72 | 41.36 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 | 26.39 | 11.55 | -14.84 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_promo_list | 0 | 13.73 | 6.31 | -7.42 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_data_integrity | 0 | 12.65 | 22.82 | 10.17 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_transfer_options | 0 | 28.45 | 27.28 | -1.17 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 | 21 | 12.53 | -8.47 | done -> done | 2 -> 3 | 1 -> 0 | - | - |
| specialist_supply | 0 | 4.25 | 7.33 | 3.08 | done -> done | 1 -> 2 | 0 -> 0 | - | - |
| specialist_strategist | 0 | 18.94 | 9.42 | -9.52 | done -> done | 2 -> 4 | 1 -> 0 | - | - |
| multi_specialist | 0 | 97.82 | 133.61 | 35.79 | done -> done | 3 -> 6 | 2 -> 3 | - | - |
| proposal | 0 | 32.61 | 38.31 | 5.7 | done -> done | 3 -> 1 | 1 -> 0 | check:proposal_pending | - |
| unsupported | 0 | 11.58 | 11.52 | -0.06 | done -> done | 2 -> 2 | 1 -> 0 | - | - |
| follow_up | 0 | 15.69 | 37.23 | 21.54 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 | 14.58 | 39.39 | 24.81 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 2 | 43.79 | 21.98 | -21.81 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 0 | 22.71 | 10.85 | -11.86 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 1 | 62.69 | 5.56 | -57.13 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 2 | 4.69 | 30.41 | 25.72 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 | 15.17 | 4.61 | -10.56 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 4 | 41.52 | 7.77 | -33.75 | done -> done | 2 -> 3 | 1 -> 0 | - | - |

## Aggregates

| metric | before | after | delta |
|---|---|---|---|
| latency_p50_s | 15.69 | 21.98 | 6.29 |
| latency_p95_s | 62.69 | 112.29 | 49.6 |
| latency_max_s | 97.82 | 133.61 | 35.79 |
| first_text_p50_s | - | - | - |
| first_text_p95_s | - | - | - |
| failure_rate | 0 | 0 | 0 |
| tool_calls_total | 43 | 40 | -3 |
| peer_asks_total | 17 | 4 | -13 |

- flags before: {}
- flags after: {"check:proposal_pending": 1}
- burst before: {"turns": 5, "failed": 0, "latency_max_s": 62.69, "latency_p50_s": 22.71}
- burst after: {"turns": 5, "failed": 0, "latency_max_s": 30.41, "latency_p50_s": 7.77}

## Phase 5 routing (read from audit_turn_routes / audit_turn_intents / audit_turn_costs)

System One router: model jev-1.13.0 on every decision. Delegated turns ran as actor `peer-agent` on behalf of `manager-1`.
Totals over the 25 battery turns: 17 intent plans (layer B), 5 routed to one specialist (layer A), 3 passed to the orchestrator.
Two further Core turns were backend quality-guard rewrites (intent_order_plan, follow_up 2); both passed.

| case | turn | decision | label | profile | confidence | actor | on behalf of | reply mode | turn output tokens | rewritten |
|---|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | pass | none_of_these | glazed_orchestrator | 0.99 | - | - | - | 767 | False |
| intent_day_summary | 0 | intent | day_summary | glazed_present | 1.00 | peer-agent | manager-1 | compose | 16465 | False |
| intent_active_issues | 0 | intent | active_issues | glazed_present | 1.00 | peer-agent | manager-1 | compose | 16611 | False |
| intent_order_plan | 0 | intent | order_plan | glazed_supply | 1.00 | peer-agent | manager-1 | compose | 19586 | True |
| intent_stockout_risk | 0 | intent | stockout_risk | glazed_supply | 1.00 | peer-agent | manager-1 | compose | 7910 | False |
| intent_expiring_items | 0 | intent | expiring_items | glazed_present | 1.00 | peer-agent | manager-1 | compose | 2907 | False |
| intent_upcoming_deliveries | 0 | intent | upcoming_deliveries | glazed_supply | 1.00 | peer-agent | manager-1 | compose | 10587 | False |
| intent_staffing | 0 | intent | staffing | glazed_strategist | 1.00 | peer-agent | manager-1 | compose | 1804 | False |
| intent_promo_list | 0 | intent | promo_list | glazed_strategist | 1.00 | peer-agent | manager-1 | compose | 742 | False |
| intent_data_integrity | 0 | intent | data_integrity | glazed_auditor | 1.00 | peer-agent | manager-1 | compose | 4405 | False |
| intent_transfer_options | 0 | pass | none_of_these | glazed_orchestrator | 0.39 | - | - | - | - | False |
| specialist_past | 0 | route | past_experience | glazed_past | 1.00 | peer-agent | manager-1 | - | 1449 | False |
| specialist_supply | 0 | route | supply_analysis | glazed_supply | 1.00 | peer-agent | manager-1 | - | 1293 | False |
| specialist_strategist | 0 | route | strategy_flow | glazed_strategist | 0.64 | peer-agent | manager-1 | - | 1349 | False |
| multi_specialist | 0 | pass | none_of_these | glazed_orchestrator | 0.80 | - | - | - | - | False |
| proposal | 0 | intent | order_plan | glazed_supply | 0.74 | peer-agent | manager-1 | compose | 6904 | False |
| unsupported | 0 | route | present_metrics | glazed_present | 0.93 | peer-agent | manager-1 | - | 1494 | False |
| follow_up | 0 | intent | stockout_risk | glazed_supply | 1.00 | peer-agent | manager-1 | compose | 7933 | False |
| follow_up | 1 | intent | active_issues | glazed_present | 0.59 | peer-agent | manager-1 | compose | 7587 | False |
| follow_up | 2 | intent | order_plan | glazed_supply | 0.94 | peer-agent | manager-1 | compose | 1874 | True |
| burst | 0 | intent | day_summary | glazed_present | 1.00 | peer-agent | manager-1 | compose | 1400 | False |
| burst | 1 | intent | active_issues | glazed_present | 1.00 | peer-agent | manager-1 | compose | 514 | False |
| burst | 2 | intent | upcoming_deliveries | glazed_supply | 1.00 | peer-agent | manager-1 | compose | 4220 | False |
| burst | 3 | intent | promo_list | glazed_strategist | 1.00 | peer-agent | manager-1 | compose | 336 | False |
| burst | 4 | route | present_metrics | glazed_present | 0.93 | peer-agent | manager-1 | - | 788 | False |

Notes:
- first_text_s is null on every turn: the backend opens `GET /turns/{id}/events` right after `POST /turns`, before Core has
  written the turn row, gets 404 and falls back to polling (one attempt per turn). Latencies are therefore polling latencies.
- Slow intent plans track the compose call's output tokens (16-20k tokens -> 78-112 s); short ones (<2k tokens) take 5-12 s.
- `proposal` was classified as intent `order_plan` (0.74, a read-only plan), so no proposal was created (check failed).
- Single run per stage: LLM variance applies.
