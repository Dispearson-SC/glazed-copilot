# Stress battery compare: p14-shadow -> p14-on

| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |
|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | 19.58 | 4.18 | -15.4 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 | 7.22 | 4.57 | -2.65 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 | 15.4 | 22.54 | 7.14 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 | 23.97 | 12.38 | -11.59 | done -> done | 1 -> 1 | 0 -> 0 | - | garbled |
| intent_stockout_risk | 0 | 6.26 | 9.31 | 3.05 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_expiring_items | 0 | 4.16 | 4.14 | -0.02 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_upcoming_deliveries | 0 | 6.27 | 5.23 | -1.04 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 | 3.18 | 6.28 | 3.1 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_promo_list | 0 | 5.24 | 3.14 | -2.1 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_data_integrity | 0 | 6.22 | 4.15 | -2.07 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_transfer_options | 0 | 67.81 | 25.78 | -42.03 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 | 11.35 | 27.85 | 16.5 | done -> done | 2 -> 2 | 0 -> 1 | - | garbled |
| specialist_supply | 0 | 11.38 | 12.36 | 0.98 | done -> done | 2 -> 1 | 0 -> 0 | - | - |
| specialist_strategist | 0 | 6.26 | 11.41 | 5.15 | done -> done | 2 -> 4 | 0 -> 0 | - | - |
| multi_specialist | 0 | 33.98 | 31.03 | -2.95 | done -> done | 3 -> 3 | 2 -> 2 | - | garbled |
| proposal | 0 | 8.31 | 11.31 | 3 | done -> done | 2 -> 2 | 0 -> 0 | - | - |
| unsupported | 0 | 7.38 | 5.17 | -2.21 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 0 | 7.25 | 5.21 | -2.04 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 | 12.31 | 9.25 | -3.06 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 2 | 5.18 | 5.16 | -0.02 | done -> done | 0 -> 0 | 0 -> 0 | - | - |
| burst | 0 | 4.37 | 3.53 | -0.84 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 1 | 5.45 | 3.59 | -1.86 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 | 8.48 | 12.77 | 4.29 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 | 4.44 | 8.7 | 4.26 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 4 | 12.64 | 12.74 | 0.1 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| simple | 0 r1 | 10.53 | 7.23 | -3.3 | done -> done | 1 -> 1 | 0 -> 0 | - | garbled |
| intent_day_summary | 0 r1 | 5.27 | 4.22 | -1.05 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 r1 | 12.26 | 5.17 | -7.09 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 r1 | 17.41 | 9.31 | -8.1 | done -> done | 1 -> 1 | 0 -> 0 | - | garbled |
| intent_stockout_risk | 0 r1 | 7.22 | 6.27 | -0.95 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_expiring_items | 0 r1 | 7.3 | 7.25 | -0.05 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_upcoming_deliveries | 0 r1 | 6.25 | 4.18 | -2.07 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 r1 | 5.22 | 5.19 | -0.03 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_promo_list | 0 r1 | 4.18 | 7.37 | 3.19 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_data_integrity | 0 r1 | 6.22 | 4.22 | -2 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_transfer_options | 0 r1 | 27.8 | 28.84 | 1.04 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 r1 | 14.4 | 29.85 | 15.45 | done -> done | 3 -> 2 | 0 -> 1 | - | garbled |
| specialist_supply | 0 r1 | 13.39 | 14.41 | 1.02 | done -> done | 2 -> 2 | 0 -> 0 | - | - |
| specialist_strategist | 0 r1 | 15.36 | 9.26 | -6.1 | done -> done | 4 -> 3 | 0 -> 0 | - | - |
| multi_specialist | 0 r1 | 63.49 | 63.84 | 0.35 | done -> done | 6 -> 3 | 2 -> 2 | - | - |
| proposal | 0 r1 | 18.4 | 25.65 | 7.25 | done -> done | 2 -> 2 | 0 -> 0 | - | - |
| unsupported | 0 r1 | 13.43 | 8.31 | -5.12 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 0 r1 | 8.27 | 7.31 | -0.96 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 r1 | 16.37 | 14.42 | -1.95 | done -> done | 1 -> 1 | 0 -> 0 | garbled | - |
| follow_up | 2 r1 | 7.28 | 7.52 | 0.24 | done -> done | 0 -> 0 | 0 -> 0 | - | - |
| burst | 0 r1 | 13.6 | 3.53 | -10.07 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 1 r1 | 5.41 | 5.55 | 0.14 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 r1 | 8.52 | 6.64 | -1.88 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 r1 | 6.51 | 8.69 | 2.18 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 4 r1 | 11.61 | 18.96 | 7.35 | done -> done | 1 -> 1 | 0 -> 0 | internal_names | - |
| simple | 0 r2 | 21.6 | 5.2 | -16.4 | done -> done | 1 -> 1 | 0 -> 0 | - | garbled |
| intent_day_summary | 0 r2 | 6.39 | 13.38 | 6.99 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 r2 | 16.4 | 9.29 | -7.11 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 r2 | 27.38 | 25.36 | -2.02 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_stockout_risk | 0 r2 | 19.41 | 8.37 | -11.04 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_expiring_items | 0 r2 | 15.34 | 6.3 | -9.04 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_upcoming_deliveries | 0 r2 | 7.23 | 6.23 | -1 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 r2 | 6.27 | 6.23 | -0.04 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_promo_list | 0 r2 | 3.17 | 5.22 | 2.05 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_data_integrity | 0 r2 | 7.28 | 8.3 | 1.02 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_transfer_options | 0 r2 | 30.82 | 25.8 | -5.02 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 r2 | 18.62 | 32.04 | 13.42 | done -> done | 2 -> 3 | 0 -> 2 | - | garbled |
| specialist_supply | 0 r2 | 9.33 | 10.29 | 0.96 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| specialist_strategist | 0 r2 | 14.38 | 52.32 | 37.94 | done -> done | 5 -> 3 | 0 -> 0 | - | - |
| multi_specialist | 0 r2 | 29.97 | 39.28 | 9.31 | done -> done | 6 -> 3 | 2 -> 2 | garbled | - |
| proposal | 0 r2 | 9.31 | 35.14 | 25.83 | done -> done | 2 -> 3 | 0 -> 1 | - | garbled |
| unsupported | 0 r2 | 5.34 | 10.35 | 5.01 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 0 r2 | 7.26 | 14.4 | 7.14 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 r2 | 6.21 | 15.35 | 9.14 | done -> done | 1 -> 1 | 0 -> 0 | garbled | - |
| follow_up | 2 r2 | 7.25 | 5.21 | -2.04 | done -> done | 0 -> 0 | 0 -> 0 | - | - |
| burst | 0 r2 | 4.36 | 5.57 | 1.21 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 1 r2 | 5.43 | 7.57 | 2.14 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 r2 | 7.49 | 10.66 | 3.17 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 r2 | 4.33 | 14.73 | 10.4 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 4 r2 | 8.5 | 9.67 | 1.17 | done -> done | 1 -> 1 | 0 -> 0 | - | - |

## Aggregates

| metric | before | after | delta |
|---|---|---|---|
| latency_p50_s | 8.27 | 8.69 | 0.42 |
| latency_p95_s | 30.82 | 35.14 | 4.32 |
| latency_max_s | 67.81 | 63.84 | -3.97 |
| first_text_p50_s | 4.53 | 4.29 | -0.24 |
| first_text_p95_s | 23.11 | 23.05 | -0.06 |
| failure_rate | 0 | 0 | 0 |
| tool_calls_total | 104 | 97 | -7 |
| peer_asks_total | 9 | 14 | 5 |
| garbled_fragments_total | 16 | 7 | -9 |
| garbled_turns | 11 | 5 | -6 |

## Per path (median)

`composite`: the turns the fast path answered; `defer`: the turns every mode runs the same way (the true control: a change there is provider drift); `pass`: the turns `on` sends to the entry profile instead of the router's route (a change there is behaviour); `unknown`: no decision recorded.

| path | turns before / after | latency before s | latency after s | first text before s | first text after s |
|---|---|---|---|---|---|
| composite | 42 / 42 | 6.45 | 6.25 | 4.5 | 4.21 |
| defer (true control) | 12 / 12 | 11.5 | 10.88 | 3.95 | 5.09 |
| pass | 21 / 21 | 17.41 | 25.65 | 5.31 | 4.26 |
| unknown | 0 / 0 | - | - | - | - |

- flags before: {"garbled": 11}
- flags after: {"garbled": 5, "internal_names": 1}
- burst before: {"turns": 15, "failed": 0, "latency_max_s": 13.6, "latency_p50_s": 6.51}
- burst after: {"turns": 15, "failed": 0, "latency_max_s": 18.96, "latency_p50_s": 8.69}
