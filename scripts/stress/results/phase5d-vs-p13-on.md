# Stress battery compare: phase5d -> p13-on

| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |
|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | 8.28 | 4.19 | -4.09 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 | 5.23 | 6.26 | 1.03 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 | 6.26 | 5.19 | -1.07 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 | 12.4 | 15.58 | 3.18 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_stockout_risk | 0 | 5.21 | 9.33 | 4.12 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_expiring_items | 0 | 3.22 | 4.22 | 1 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_upcoming_deliveries | 0 | 5.17 | 5.19 | 0.02 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 | 3.19 | 25.78 | 22.59 | done -> done | 1 -> 2 | 0 -> 1 | - | - |
| intent_promo_list | 0 | 3.22 | 3.17 | -0.05 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_data_integrity | 0 | 4.31 | 37 | 32.69 | done -> done | 1 -> 2 | 0 -> 1 | - | - |
| intent_transfer_options | 0 | 14.45 | 40.05 | 25.6 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 | 7.26 | 32.02 | 24.76 | done -> done | 2 -> 2 | 0 -> 1 | garbled | - |
| specialist_supply | 0 | 14.46 | 7.28 | -7.18 | done -> done | 2 -> 2 | 0 -> 0 | - | - |
| specialist_strategist | 0 | 7.26 | 20.7 | 13.44 | done -> done | 4 -> 2 | 0 -> 1 | - | - |
| multi_specialist | 0 | 32.04 | 44.25 | 12.21 | done -> done | 8 -> 3 | 2 -> 2 | garbled | - |
| proposal | 0 | 7.22 | 12.36 | 5.14 | done -> done | 2 -> 2 | 0 -> 0 | - | - |
| unsupported | 0 | 11.38 | 14.32 | 2.94 | done -> done | 1 -> 0 | 0 -> 0 | - | - |
| follow_up | 0 | 5.2 | 7.26 | 2.06 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 | 6.27 | 19.52 | 13.25 | done -> done | 1 -> 1 | 0 -> 0 | garbled | - |
| follow_up | 2 | 5.22 | 9.39 | 4.17 | done -> done | 0 -> 0 | 0 -> 0 | - | - |
| burst | 0 | 4.54 | 8.72 | 4.18 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 1 | 9.62 | 6.74 | -2.88 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 | 6.65 | 5.69 | -0.96 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 | 3.53 | 7.76 | 4.23 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 4 | 5.59 | 11.8 | 6.21 | done -> done | 1 -> 1 | 0 -> 0 | - | - |

## Aggregates

| metric | before | after | delta |
|---|---|---|---|
| latency_p50_s | 6.26 | 10.33 | 4.07 |
| latency_p95_s | 14.46 | 40.05 | 25.59 |
| latency_max_s | 32.04 | 51.56 | 19.52 |
| first_text_p50_s | 3.08 | 4.86 | 1.78 |
| first_text_p95_s | 12.53 | 31.26 | 18.73 |
| failure_rate | 0 | 0 | 0 |
| tool_calls_total | 38 | 101 | 63 |
| peer_asks_total | 3 | 19 | 16 |
| garbled_fragments_total | - | 16 | - |
| garbled_turns | - | 11 | - |

## Per path (median)

`composite`: the turns the fast path answered; `other`: the turns every mode runs the same way (a change there is provider drift); `unknown`: no decision recorded.

| path | turns before / after | latency before s | latency after s | first text before s | first text after s |
|---|---|---|---|---|---|
| composite | 0 / 34 | - | 6.25 | - | 4.54 |
| other | 0 / 41 | - | 15.63 | - | 5.63 |
| unknown | 25 / 0 | 6.26 | - | 3.08 | - |

- flags before: {}
- flags after: {"garbled": 11}
- burst before: {"turns": 5, "failed": 0, "latency_max_s": 9.62, "latency_p50_s": 5.59}
- burst after: {"turns": 15, "failed": 0, "latency_max_s": 15.63, "latency_p50_s": 6.61}
