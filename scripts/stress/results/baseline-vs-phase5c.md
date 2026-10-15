# Stress battery compare: baseline -> phase5c

| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |
|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | 13.67 | 17.51 | 3.84 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 | 12.6 | 4.24 | -8.36 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 | 14.64 | 10.31 | -4.33 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 | 10.47 | 18.53 | 8.06 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_stockout_risk | 0 | 40.14 | 7.23 | -32.91 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_expiring_items | 0 | 31.61 | 10.33 | -21.28 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_upcoming_deliveries | 0 | 5.36 | 6.26 | 0.9 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 | 26.39 | 6.23 | -20.16 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_promo_list | 0 | 13.73 | 4.15 | -9.58 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_data_integrity | 0 | 12.65 | 7.27 | -5.38 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_transfer_options | 0 | 28.45 | 48.17 | 19.72 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 | 21 | 18.47 | -2.53 | done -> done | 2 -> 3 | 1 -> 0 | - | - |
| specialist_supply | 0 | 4.25 | 23.68 | 19.43 | done -> done | 1 -> 2 | 0 -> 0 | - | - |
| specialist_strategist | 0 | 18.94 | 17.47 | -1.47 | done -> done | 2 -> 4 | 1 -> 0 | - | - |
| multi_specialist | 0 | 97.82 | 145.8 | 47.98 | done -> done | 3 -> 4 | 2 -> 3 | - | - |
| proposal | 0 | 32.61 | 81.31 | 48.7 | done -> done | 3 -> 4 | 1 -> 2 | - | - |
| unsupported | 0 | 11.58 | 15.41 | 3.83 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| follow_up | 0 | 15.69 | 12.35 | -3.34 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 | 14.58 | 19.51 | 4.93 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 2 | 43.79 | 10.4 | -33.39 | done -> done | 2 -> 0 | 1 -> 0 | - | - |
| burst | 0 | 22.71 | 6.55 | -16.16 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 1 | 62.69 | 6.56 | -56.13 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 2 | 4.69 | 5.48 | 0.79 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 | 15.17 | 5.46 | -9.71 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 4 | 41.52 | 28.89 | -12.63 | done -> done | 2 -> 2 | 1 -> 0 | - | - |

## Aggregates

| metric | before | after | delta |
|---|---|---|---|
| latency_p50_s | 15.69 | 10.4 | -5.29 |
| latency_p95_s | 62.69 | 81.31 | 18.62 |
| latency_max_s | 97.82 | 145.8 | 47.98 |
| first_text_p50_s | - | 5.14 | - |
| first_text_p95_s | - | 14.97 | - |
| failure_rate | 0 | 0 | 0 |
| tool_calls_total | 43 | 38 | -5 |
| peer_asks_total | 17 | 6 | -11 |

- flags before: {}
- flags after: {}
- burst before: {"turns": 5, "failed": 0, "latency_max_s": 62.69, "latency_p50_s": 22.71}
- burst after: {"turns": 5, "failed": 0, "latency_max_s": 28.89, "latency_p50_s": 6.55}

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
