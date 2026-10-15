# Stress battery compare: phase5d -> p14-on

| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |
|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | 8.28 | 4.18 | -4.1 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 | 5.23 | 4.57 | -0.66 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 | 6.26 | 22.54 | 16.28 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 | 12.4 | 12.38 | -0.02 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_stockout_risk | 0 | 5.21 | 9.31 | 4.1 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_expiring_items | 0 | 3.22 | 4.14 | 0.92 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_upcoming_deliveries | 0 | 5.17 | 5.23 | 0.06 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 | 3.19 | 6.28 | 3.09 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_promo_list | 0 | 3.22 | 3.14 | -0.08 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_data_integrity | 0 | 4.31 | 4.15 | -0.16 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_transfer_options | 0 | 14.45 | 25.78 | 11.33 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 | 7.26 | 27.85 | 20.59 | done -> done | 2 -> 2 | 0 -> 1 | - | - |
| specialist_supply | 0 | 14.46 | 12.36 | -2.1 | done -> done | 2 -> 1 | 0 -> 0 | - | - |
| specialist_strategist | 0 | 7.26 | 11.41 | 4.15 | done -> done | 4 -> 4 | 0 -> 0 | - | - |
| multi_specialist | 0 | 32.04 | 31.03 | -1.01 | done -> done | 8 -> 3 | 2 -> 2 | - | - |
| proposal | 0 | 7.22 | 11.31 | 4.09 | done -> done | 2 -> 2 | 0 -> 0 | garbled | - |
| unsupported | 0 | 11.38 | 5.17 | -6.21 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 0 | 5.2 | 5.21 | 0.01 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 | 6.27 | 9.25 | 2.98 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 2 | 5.22 | 5.16 | -0.06 | done -> done | 0 -> 0 | 0 -> 0 | - | - |
| burst | 0 | 4.54 | 3.53 | -1.01 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 1 | 9.62 | 3.59 | -6.03 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 | 6.65 | 12.77 | 6.12 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 | 3.53 | 8.7 | 5.17 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 4 | 5.59 | 12.74 | 7.15 | done -> done | 1 -> 1 | 0 -> 0 | - | - |

## Aggregates

| metric | before | after | delta |
|---|---|---|---|
| latency_p50_s | 6.26 | 8.69 | 2.43 |
| latency_p95_s | 14.46 | 35.14 | 20.68 |
| latency_max_s | 32.04 | 63.84 | 31.8 |
| first_text_p50_s | 3.08 | 4.29 | 1.21 |
| first_text_p95_s | 12.53 | 23.05 | 10.52 |
| failure_rate | 0 | 0 | 0 |
| tool_calls_total | 38 | 97 | 59 |
| peer_asks_total | 3 | 14 | 11 |
| garbled_fragments_total | - | 7 | - |
| garbled_turns | - | 5 | - |

## Per path (median)

`composite`: the turns the fast path answered; `defer`: the turns every mode runs the same way (the true control: a change there is provider drift); `pass`: the turns `on` sends to the entry profile instead of the router's route (a change there is behaviour); `unknown`: no decision recorded.

| path | turns before / after | latency before s | latency after s | first text before s | first text after s |
|---|---|---|---|---|---|
| composite | 0 / 42 | - | 6.25 | - | 4.21 |
| defer (true control) | 0 / 12 | - | 10.88 | - | 5.09 |
| pass | 0 / 21 | - | 25.65 | - | 4.26 |
| unknown | 25 / 0 | 6.26 | - | 3.08 | - |

- flags before: {}
- flags after: {"garbled": 5, "internal_names": 1}
- burst before: {"turns": 5, "failed": 0, "latency_max_s": 9.62, "latency_p50_s": 5.59}
- burst after: {"turns": 15, "failed": 0, "latency_max_s": 18.96, "latency_p50_s": 8.69}
