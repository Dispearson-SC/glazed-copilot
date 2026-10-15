# Stress battery compare: baseline -> p13-on

| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |
|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | 13.67 | 4.19 | -9.48 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 | 12.6 | 6.26 | -6.34 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 | 14.64 | 5.19 | -9.45 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 | 10.47 | 15.58 | 5.11 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_stockout_risk | 0 | 40.14 | 9.33 | -30.81 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_expiring_items | 0 | 31.61 | 4.22 | -27.39 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_upcoming_deliveries | 0 | 5.36 | 5.19 | -0.17 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 | 26.39 | 25.78 | -0.61 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| intent_promo_list | 0 | 13.73 | 3.17 | -10.56 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_data_integrity | 0 | 12.65 | 37 | 24.35 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| intent_transfer_options | 0 | 28.45 | 40.05 | 11.6 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 | 21 | 32.02 | 11.02 | done -> done | 2 -> 2 | 1 -> 1 | garbled | - |
| specialist_supply | 0 | 4.25 | 7.28 | 3.03 | done -> done | 1 -> 2 | 0 -> 0 | - | - |
| specialist_strategist | 0 | 18.94 | 20.7 | 1.76 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| multi_specialist | 0 | 97.82 | 44.25 | -53.57 | done -> done | 3 -> 3 | 2 -> 2 | garbled | - |
| proposal | 0 | 32.61 | 12.36 | -20.25 | done -> done | 3 -> 2 | 1 -> 0 | - | - |
| unsupported | 0 | 11.58 | 14.32 | 2.74 | done -> done | 2 -> 0 | 1 -> 0 | - | - |
| follow_up | 0 | 15.69 | 7.26 | -8.43 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 | 14.58 | 19.52 | 4.94 | done -> done | 1 -> 1 | 0 -> 0 | garbled | - |
| follow_up | 2 | 43.79 | 9.39 | -34.4 | done -> done | 2 -> 0 | 1 -> 0 | - | - |
| burst | 0 | 22.71 | 8.72 | -13.99 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 1 | 62.69 | 6.74 | -55.95 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 2 | 4.69 | 5.69 | 1 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 | 15.17 | 7.76 | -7.41 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 4 | 41.52 | 11.8 | -29.72 | done -> done | 2 -> 1 | 1 -> 0 | - | - |

## Aggregates

| metric | before | after | delta |
|---|---|---|---|
| latency_p50_s | 15.69 | 10.33 | -5.36 |
| latency_p95_s | 62.69 | 40.05 | -22.64 |
| latency_max_s | 97.82 | 51.56 | -46.26 |
| first_text_p50_s | - | 4.86 | - |
| first_text_p95_s | - | 31.26 | - |
| failure_rate | 0 | 0 | 0 |
| tool_calls_total | 43 | 101 | 58 |
| peer_asks_total | 17 | 19 | 2 |
| garbled_fragments_total | - | 16 | - |
| garbled_turns | - | 11 | - |

## Per path (median)

`composite`: the turns the fast path answered; `other`: the turns every mode runs the same way (a change there is provider drift); `unknown`: no decision recorded.

| path | turns before / after | latency before s | latency after s | first text before s | first text after s |
|---|---|---|---|---|---|
| composite | 0 / 34 | - | 6.25 | - | 4.54 |
| other | 0 / 41 | - | 15.63 | - | 5.63 |
| unknown | 25 / 0 | 15.69 | - | - | - |

- flags before: {}
- flags after: {"garbled": 11}
- burst before: {"turns": 5, "failed": 0, "latency_max_s": 62.69, "latency_p50_s": 22.71}
- burst after: {"turns": 15, "failed": 0, "latency_max_s": 15.63, "latency_p50_s": 6.61}
