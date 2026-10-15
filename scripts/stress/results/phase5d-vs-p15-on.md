# Stress battery compare: phase5d -> p15-on

| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |
|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | 8.28 | 4.23 | -4.05 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 | 5.23 | 3.21 | -2.02 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 | 6.26 | 5.2 | -1.06 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 | 12.4 | 7.29 | -5.11 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_stockout_risk | 0 | 5.21 | 3.75 | -1.46 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_expiring_items | 0 | 3.22 | 3.21 | -0.01 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_upcoming_deliveries | 0 | 5.17 | 3.15 | -2.02 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 | 3.19 | 3.18 | -0.01 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_promo_list | 0 | 3.22 | 3.23 | 0.01 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_data_integrity | 0 | 4.31 | 2.19 | -2.12 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_transfer_options | 0 | 14.45 | 18.66 | 4.21 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 | 7.26 | 8.25 | 0.99 | done -> done | 2 -> 2 | 0 -> 0 | - | - |
| specialist_supply | 0 | 14.46 | 5.22 | -9.24 | done -> done | 2 -> 2 | 0 -> 0 | garbled | - |
| specialist_strategist | 0 | 7.26 | 10.34 | 3.08 | done -> done | 4 -> 5 | 0 -> 0 | - | - |
| multi_specialist | 0 | 32.04 | 21.64 | -10.4 | done -> done | 8 -> 3 | 2 -> 2 | garbled | - |
| proposal | 0 | 7.22 | 9.43 | 2.21 | done -> done | 2 -> 2 | 0 -> 0 | internal_names | - |
| unsupported | 0 | 11.38 | 5.21 | -6.17 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 0 | 5.2 | 4.18 | -1.02 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 | 6.27 | 9.28 | 3.01 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 2 | 5.22 | 4.17 | -1.05 | done -> done | 0 -> 0 | 0 -> 0 | - | - |
| burst | 0 | 4.54 | 3.42 | -1.12 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 1 | 9.62 | 3.41 | -6.21 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 | 6.65 | 4.42 | -2.23 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 | 3.53 | 3.43 | -0.1 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 4 | 5.59 | 5.45 | -0.14 | done -> done | 1 -> 1 | 0 -> 0 | - | - |

## Aggregates

| metric | before | after | delta |
|---|---|---|---|
| latency_p50_s | 6.26 | 4.53 | -1.73 |
| latency_p95_s | 14.46 | 18.66 | 4.2 |
| latency_max_s | 32.04 | 22.99 | -9.05 |
| first_text_p50_s | 3.08 | 2.93 | -0.15 |
| first_text_p95_s | 12.53 | 11.56 | -0.97 |
| failure_rate | 0 | 0 | 0 |
| tool_calls_total | 38 | 99 | 61 |
| peer_asks_total | 3 | 10 | 7 |
| garbled_fragments_total | - | 2 | - |
| garbled_turns | - | 2 | - |

## Per path (median)

`composite`: the turns the fast path answered; `defer`: the turns every mode runs the same way (the true control: a change there is provider drift); `pass`: the turns `on` sends to the entry profile instead of the router's route (a change there is behaviour); `unknown`: no decision recorded.

| path | turns before / after | latency before s | latency after s | first text before s | first text after s |
|---|---|---|---|---|---|
| composite | 0 / 42 | - | 3.71 | - | 2.83 |
| defer (true control) | 0 / 15 | - | 6.34 | - | 3.29 |
| pass | 0 / 18 | - | 7.39 | - | 2.92 |
| unknown | 25 / 0 | 6.26 | - | 3.08 | - |

- flags before: {}
- flags after: {"garbled": 2, "internal_names": 2}
- burst before: {"turns": 5, "failed": 0, "latency_max_s": 9.62, "latency_p50_s": 5.59}
- burst after: {"turns": 15, "failed": 0, "latency_max_s": 7.63, "latency_p50_s": 4.42}
