# Stress battery compare: baseline -> phase3

| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |
|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | 13.67 | 10.45 | -3.22 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 | 12.6 | 8.42 | -4.18 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 | 14.64 | 12.48 | -2.16 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 | 10.47 | 9.39 | -1.08 | done -> done | 1 -> 1 | 0 -> 0 | internal_names | - |
| intent_stockout_risk | 0 | 40.14 | 36.72 | -3.42 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| intent_expiring_items | 0 | 31.61 | 23.09 | -8.52 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| intent_upcoming_deliveries | 0 | 5.36 | 5.25 | -0.11 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 | 26.39 | 47.25 | 20.86 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| intent_promo_list | 0 | 13.73 | 15.77 | 2.04 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| intent_data_integrity | 0 | 12.65 | 25.29 | 12.64 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| intent_transfer_options | 0 | 28.45 | 30.4 | 1.95 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 | 21 | 22.14 | 1.14 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_supply | 0 | 4.25 | 5.38 | 1.13 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| specialist_strategist | 0 | 18.94 | 17.93 | -1.01 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| multi_specialist | 0 | 97.82 | 78.81 | -19.01 | done -> done | 3 -> 8 | 2 -> 2 | - | - |
| proposal | 0 | 32.61 | 8.37 | -24.24 | done -> done | 3 -> 2 | 1 -> 0 | - | - |
| unsupported | 0 | 11.58 | 5.29 | -6.29 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| follow_up | 0 | 15.69 | 54.73 | 39.04 | done -> done | 1 -> 2 | 0 -> 1 | - | - |
| follow_up | 1 | 14.58 | 15.72 | 1.14 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 2 | 43.79 | 5.26 | -38.53 | done -> done | 2 -> 0 | 1 -> 0 | untraceable_numbers | - |
| burst | 0 | 22.71 | 17.28 | -5.43 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| burst | 1 | 62.69 | 6.56 | -56.13 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 2 | 4.69 | 5.6 | 0.91 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 | 15.17 | 24.67 | 9.5 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| burst | 4 | 41.52 | 26.55 | -14.97 | done -> done | 2 -> 2 | 1 -> 1 | - | - |

## Aggregates

| metric | before | after | delta |
|---|---|---|---|
| latency_p50_s | 15.69 | 15.77 | 0.08 |
| latency_p95_s | 62.69 | 54.73 | -7.96 |
| latency_max_s | 97.82 | 78.81 | -19.01 |
| failure_rate | 0 | 0 | 0 |
| tool_calls_total | 43 | 44 | 1 |
| peer_asks_total | 17 | 14 | -3 |

- flags before: {}
- flags after: {"internal_names": 1, "untraceable_numbers": 1}
- burst before: {"turns": 5, "failed": 0, "latency_max_s": 62.69, "latency_p50_s": 22.71}
- burst after: {"turns": 5, "failed": 0, "latency_max_s": 26.55, "latency_p50_s": 17.28}
