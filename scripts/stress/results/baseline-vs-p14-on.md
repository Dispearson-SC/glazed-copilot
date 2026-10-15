# Stress battery compare: baseline -> p14-on

| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |
|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | 13.67 | 4.18 | -9.49 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 | 12.6 | 4.57 | -8.03 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 | 14.64 | 22.54 | 7.9 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 | 10.47 | 12.38 | 1.91 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_stockout_risk | 0 | 40.14 | 9.31 | -30.83 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_expiring_items | 0 | 31.61 | 4.14 | -27.47 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_upcoming_deliveries | 0 | 5.36 | 5.23 | -0.13 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 | 26.39 | 6.28 | -20.11 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_promo_list | 0 | 13.73 | 3.14 | -10.59 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_data_integrity | 0 | 12.65 | 4.15 | -8.5 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_transfer_options | 0 | 28.45 | 25.78 | -2.67 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 | 21 | 27.85 | 6.85 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_supply | 0 | 4.25 | 12.36 | 8.11 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| specialist_strategist | 0 | 18.94 | 11.41 | -7.53 | done -> done | 2 -> 4 | 1 -> 0 | - | - |
| multi_specialist | 0 | 97.82 | 31.03 | -66.79 | done -> done | 3 -> 3 | 2 -> 2 | - | - |
| proposal | 0 | 32.61 | 11.31 | -21.3 | done -> done | 3 -> 2 | 1 -> 0 | garbled | - |
| unsupported | 0 | 11.58 | 5.17 | -6.41 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| follow_up | 0 | 15.69 | 5.21 | -10.48 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 | 14.58 | 9.25 | -5.33 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 2 | 43.79 | 5.16 | -38.63 | done -> done | 2 -> 0 | 1 -> 0 | - | - |
| burst | 0 | 22.71 | 3.53 | -19.18 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 1 | 62.69 | 3.59 | -59.1 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 2 | 4.69 | 12.77 | 8.08 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 | 15.17 | 8.7 | -6.47 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 4 | 41.52 | 12.74 | -28.78 | done -> done | 2 -> 1 | 1 -> 0 | - | - |

## Aggregates

| metric | before | after | delta |
|---|---|---|---|
| latency_p50_s | 15.69 | 8.69 | -7 |
| latency_p95_s | 62.69 | 35.14 | -27.55 |
| latency_max_s | 97.82 | 63.84 | -33.98 |
| first_text_p50_s | - | 4.29 | - |
| first_text_p95_s | - | 23.05 | - |
| failure_rate | 0 | 0 | 0 |
| tool_calls_total | 43 | 97 | 54 |
| peer_asks_total | 17 | 14 | -3 |
| garbled_fragments_total | - | 7 | - |
| garbled_turns | - | 5 | - |

## Per path (median)

`composite`: the turns the fast path answered; `defer`: the turns every mode runs the same way (the true control: a change there is provider drift); `pass`: the turns `on` sends to the entry profile instead of the router's route (a change there is behaviour); `unknown`: no decision recorded.

| path | turns before / after | latency before s | latency after s | first text before s | first text after s |
|---|---|---|---|---|---|
| composite | 0 / 42 | - | 6.25 | - | 4.21 |
| defer (true control) | 0 / 12 | - | 10.88 | - | 5.09 |
| pass | 0 / 21 | - | 25.65 | - | 4.26 |
| unknown | 25 / 0 | 15.69 | - | - | - |

- flags before: {}
- flags after: {"garbled": 5, "internal_names": 1}
- burst before: {"turns": 5, "failed": 0, "latency_max_s": 62.69, "latency_p50_s": 22.71}
- burst after: {"turns": 15, "failed": 0, "latency_max_s": 18.96, "latency_p50_s": 8.69}
