# Stress battery compare: p13-on -> p14-on

| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |
|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | 4.19 | 4.18 | -0.01 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 | 6.26 | 4.57 | -1.69 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 | 5.19 | 22.54 | 17.35 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 | 15.58 | 12.38 | -3.2 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_stockout_risk | 0 | 9.33 | 9.31 | -0.02 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_expiring_items | 0 | 4.22 | 4.14 | -0.08 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_upcoming_deliveries | 0 | 5.19 | 5.23 | 0.04 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 | 25.78 | 6.28 | -19.5 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_promo_list | 0 | 3.17 | 3.14 | -0.03 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_data_integrity | 0 | 37 | 4.15 | -32.85 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_transfer_options | 0 | 40.05 | 25.78 | -14.27 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 | 32.02 | 27.85 | -4.17 | done -> done | 2 -> 2 | 1 -> 1 | - | garbled |
| specialist_supply | 0 | 7.28 | 12.36 | 5.08 | done -> done | 2 -> 1 | 0 -> 0 | - | - |
| specialist_strategist | 0 | 20.7 | 11.41 | -9.29 | done -> done | 2 -> 4 | 1 -> 0 | - | - |
| multi_specialist | 0 | 44.25 | 31.03 | -13.22 | done -> done | 3 -> 3 | 2 -> 2 | - | garbled |
| proposal | 0 | 12.36 | 11.31 | -1.05 | done -> done | 2 -> 2 | 0 -> 0 | garbled | - |
| unsupported | 0 | 14.32 | 5.17 | -9.15 | done -> done | 0 -> 1 | 0 -> 0 | - | - |
| follow_up | 0 | 7.26 | 5.21 | -2.05 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 | 19.52 | 9.25 | -10.27 | done -> done | 1 -> 1 | 0 -> 0 | - | garbled |
| follow_up | 2 | 9.39 | 5.16 | -4.23 | done -> done | 0 -> 0 | 0 -> 0 | - | - |
| burst | 0 | 8.72 | 3.53 | -5.19 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 1 | 6.74 | 3.59 | -3.15 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 | 5.69 | 12.77 | 7.08 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 | 7.76 | 8.7 | 0.94 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 4 | 11.8 | 12.74 | 0.94 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| simple | 0 r1 | 5.19 | 7.23 | 2.04 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 r1 | 5.23 | 4.22 | -1.01 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 r1 | 49.23 | 5.17 | -44.06 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 r1 | 15.37 | 9.31 | -6.06 | done -> done | 1 -> 1 | 0 -> 0 | - | garbled |
| intent_stockout_risk | 0 r1 | 11.29 | 6.27 | -5.02 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_expiring_items | 0 r1 | 10.28 | 7.25 | -3.03 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_upcoming_deliveries | 0 r1 | 8.31 | 4.18 | -4.13 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 r1 | 35.04 | 5.19 | -29.85 | done -> done | 2 -> 1 | 1 -> 0 | - | garbled |
| intent_promo_list | 0 r1 | 4.17 | 7.37 | 3.2 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_data_integrity | 0 r1 | 23.64 | 4.22 | -19.42 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_transfer_options | 0 r1 | 17.57 | 28.84 | 11.27 | done -> done | 2 -> 2 | 1 -> 1 | - | garbled |
| specialist_past | 0 r1 | 26.7 | 29.85 | 3.15 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_supply | 0 r1 | 16.62 | 14.41 | -2.21 | done -> done | 2 -> 2 | 0 -> 0 | - | - |
| specialist_strategist | 0 r1 | 10.34 | 9.26 | -1.08 | done -> done | 3 -> 3 | 0 -> 0 | - | garbled |
| multi_specialist | 0 r1 | 51.56 | 63.84 | 12.28 | done -> done | 3 -> 3 | 2 -> 2 | - | - |
| proposal | 0 r1 | 8.3 | 25.65 | 17.35 | done -> done | 2 -> 2 | 0 -> 0 | - | - |
| unsupported | 0 r1 | 10.33 | 8.31 | -2.02 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 0 r1 | 8.47 | 7.31 | -1.16 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 r1 | 9.32 | 14.42 | 5.1 | done -> done | 1 -> 1 | 0 -> 0 | garbled | - |
| follow_up | 2 r1 | 8.27 | 7.52 | -0.75 | done -> done | 0 -> 0 | 0 -> 0 | garbled | - |
| burst | 0 r1 | 6.61 | 3.53 | -3.08 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 1 r1 | 5.56 | 5.55 | -0.01 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 r1 | 6.55 | 6.64 | 0.09 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 r1 | 6.61 | 8.69 | 2.08 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 4 r1 | 10.66 | 18.96 | 8.3 | done -> done | 1 -> 1 | 0 -> 0 | internal_names | - |
| simple | 0 r2 | 7.35 | 5.2 | -2.15 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 r2 | 6.24 | 13.38 | 7.14 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 r2 | 19.53 | 9.29 | -10.24 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 r2 | 12.49 | 25.36 | 12.87 | done -> done | 1 -> 1 | 0 -> 0 | - | garbled |
| intent_stockout_risk | 0 r2 | 11.3 | 8.37 | -2.93 | done -> done | 1 -> 1 | 0 -> 0 | - | garbled |
| intent_expiring_items | 0 r2 | 3.13 | 6.3 | 3.17 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_upcoming_deliveries | 0 r2 | 6.23 | 6.23 | 0 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 r2 | 17.55 | 6.23 | -11.32 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_promo_list | 0 r2 | 11.32 | 5.22 | -6.1 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_data_integrity | 0 r2 | 37.09 | 8.3 | -28.79 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_transfer_options | 0 r2 | 29.84 | 25.8 | -4.04 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 r2 | 24.74 | 32.04 | 7.3 | done -> done | 2 -> 3 | 1 -> 2 | - | - |
| specialist_supply | 0 r2 | 13.38 | 10.29 | -3.09 | done -> done | 2 -> 1 | 0 -> 0 | - | - |
| specialist_strategist | 0 r2 | 7.3 | 52.32 | 45.02 | done -> done | 4 -> 3 | 0 -> 0 | - | garbled |
| multi_specialist | 0 r2 | 34.13 | 39.28 | 5.15 | done -> done | 3 -> 3 | 2 -> 2 | garbled | - |
| proposal | 0 r2 | 11.37 | 35.14 | 23.77 | done -> done | 2 -> 3 | 0 -> 1 | - | - |
| unsupported | 0 r2 | 8.29 | 10.35 | 2.06 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 0 r2 | 13.37 | 14.4 | 1.03 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 r2 | 15.39 | 15.35 | -0.04 | done -> done | 1 -> 1 | 0 -> 0 | garbled | - |
| follow_up | 2 r2 | 11.37 | 5.21 | -6.16 | done -> done | 0 -> 0 | 0 -> 0 | - | garbled |
| burst | 0 r2 | 5.42 | 5.57 | 0.15 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 1 r2 | 4.38 | 7.57 | 3.19 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 r2 | 5.43 | 10.66 | 5.23 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 r2 | 4.38 | 14.73 | 10.35 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 4 r2 | 15.63 | 9.67 | -5.96 | done -> done | 1 -> 1 | 0 -> 0 | - | - |

## Aggregates

| metric | before | after | delta |
|---|---|---|---|
| latency_p50_s | 10.33 | 8.69 | -1.64 |
| latency_p95_s | 40.05 | 35.14 | -4.91 |
| latency_max_s | 51.56 | 63.84 | 12.28 |
| first_text_p50_s | 4.86 | 4.29 | -0.57 |
| first_text_p95_s | 31.26 | 23.05 | -8.21 |
| failure_rate | 0 | 0 | 0 |
| tool_calls_total | 101 | 97 | -4 |
| peer_asks_total | 19 | 14 | -5 |
| garbled_fragments_total | 16 | 7 | -9 |
| garbled_turns | 11 | 5 | -6 |

## Per path (median)

`composite`: the turns the fast path answered; `defer`: the turns every mode runs the same way (the true control: a change there is provider drift); `pass`: the turns `on` sends to the entry profile instead of the router's route (a change there is behaviour); `unknown`: no decision recorded.

| path | turns before / after | latency before s | latency after s | first text before s | first text after s |
|---|---|---|---|---|---|
| composite | 34 / 42 | 6.25 | 6.25 | 4.54 | 4.21 |
| defer (true control) | 12 / 12 | 11.23 | 10.88 | 5.25 | 5.09 |
| pass | 29 / 21 | 19.53 | 25.65 | 7.67 | 4.26 |
| unknown | 0 / 0 | - | - | - | - |

- flags before: {"garbled": 11}
- flags after: {"garbled": 5, "internal_names": 1}
- burst before: {"turns": 15, "failed": 0, "latency_max_s": 15.63, "latency_p50_s": 6.61}
- burst after: {"turns": 15, "failed": 0, "latency_max_s": 18.96, "latency_p50_s": 8.69}
