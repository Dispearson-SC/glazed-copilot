# Stress battery compare: phase3 -> phase5

| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |
|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | 10.45 | 7.71 | -2.74 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 | 8.42 | 78.68 | 70.26 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 | 12.48 | 83.82 | 71.34 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 | 9.39 | 112.29 | 102.9 | done -> done | 1 -> 1 | 0 -> 0 | - | internal_names |
| intent_stockout_risk | 0 | 36.72 | 42.6 | 5.88 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_expiring_items | 0 | 23.09 | 10.37 | -12.72 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_upcoming_deliveries | 0 | 5.25 | 46.72 | 41.47 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 | 47.25 | 11.55 | -35.7 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_promo_list | 0 | 15.77 | 6.31 | -9.46 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_data_integrity | 0 | 25.29 | 22.82 | -2.47 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_transfer_options | 0 | 30.4 | 27.28 | -3.12 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 | 22.14 | 12.53 | -9.61 | done -> done | 2 -> 3 | 1 -> 0 | - | - |
| specialist_supply | 0 | 5.38 | 7.33 | 1.95 | done -> done | 1 -> 2 | 0 -> 0 | - | - |
| specialist_strategist | 0 | 17.93 | 9.42 | -8.51 | done -> done | 2 -> 4 | 1 -> 0 | - | - |
| multi_specialist | 0 | 78.81 | 133.61 | 54.8 | done -> done | 8 -> 6 | 2 -> 3 | - | - |
| proposal | 0 | 8.37 | 38.31 | 29.94 | done -> done | 2 -> 1 | 0 -> 0 | check:proposal_pending | - |
| unsupported | 0 | 5.29 | 11.52 | 6.23 | done -> done | 1 -> 2 | 0 -> 0 | - | - |
| follow_up | 0 | 54.73 | 37.23 | -17.5 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| follow_up | 1 | 15.72 | 39.39 | 23.67 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 2 | 5.26 | 21.98 | 16.72 | done -> done | 0 -> 1 | 0 -> 0 | - | untraceable_numbers |
| burst | 0 | 17.28 | 10.85 | -6.43 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 1 | 6.56 | 5.56 | -1 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 | 5.6 | 30.41 | 24.81 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 | 24.67 | 4.61 | -20.06 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 4 | 26.55 | 7.77 | -18.78 | done -> done | 2 -> 3 | 1 -> 0 | - | - |

## Aggregates

| metric | before | after | delta |
|---|---|---|---|
| latency_p50_s | 15.77 | 21.98 | 6.21 |
| latency_p95_s | 54.73 | 112.29 | 57.56 |
| latency_max_s | 78.81 | 133.61 | 54.8 |
| first_text_p50_s | - | - | - |
| first_text_p95_s | - | - | - |
| failure_rate | 0 | 0 | 0 |
| tool_calls_total | 44 | 40 | -4 |
| peer_asks_total | 14 | 4 | -10 |

- flags before: {"internal_names": 1, "untraceable_numbers": 1}
- flags after: {"check:proposal_pending": 1}
- burst before: {"turns": 5, "failed": 0, "latency_max_s": 26.55, "latency_p50_s": 17.28}
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
