# Stress battery compare: p14-on -> p15-on

| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |
|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | 4.18 | 4.23 | 0.05 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 | 4.57 | 3.21 | -1.36 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 | 22.54 | 5.2 | -17.34 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 | 12.38 | 7.29 | -5.09 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_stockout_risk | 0 | 9.31 | 3.75 | -5.56 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_expiring_items | 0 | 4.14 | 3.21 | -0.93 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_upcoming_deliveries | 0 | 5.23 | 3.15 | -2.08 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 | 6.28 | 3.18 | -3.1 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_promo_list | 0 | 3.14 | 3.23 | 0.09 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_data_integrity | 0 | 4.15 | 2.19 | -1.96 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_transfer_options | 0 | 25.78 | 18.66 | -7.12 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 | 27.85 | 8.25 | -19.6 | done -> done | 2 -> 2 | 1 -> 0 | - | - |
| specialist_supply | 0 | 12.36 | 5.22 | -7.14 | done -> done | 1 -> 2 | 0 -> 0 | garbled | - |
| specialist_strategist | 0 | 11.41 | 10.34 | -1.07 | done -> done | 4 -> 5 | 0 -> 0 | - | - |
| multi_specialist | 0 | 31.03 | 21.64 | -9.39 | done -> done | 3 -> 3 | 2 -> 2 | garbled | - |
| proposal | 0 | 11.31 | 9.43 | -1.88 | done -> done | 2 -> 2 | 0 -> 0 | internal_names | garbled |
| unsupported | 0 | 5.17 | 5.21 | 0.04 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 0 | 5.21 | 4.18 | -1.03 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 | 9.25 | 9.28 | 0.03 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 2 | 5.16 | 4.17 | -0.99 | done -> done | 0 -> 0 | 0 -> 0 | - | - |
| burst | 0 | 3.53 | 3.42 | -0.11 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 1 | 3.59 | 3.41 | -0.18 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 | 12.77 | 4.42 | -8.35 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 | 8.7 | 3.43 | -5.27 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 4 | 12.74 | 5.45 | -7.29 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| simple | 0 r1 | 7.23 | 4.22 | -3.01 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 r1 | 4.22 | 4.15 | -0.07 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 r1 | 5.17 | 5.2 | 0.03 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 r1 | 9.31 | 7.44 | -1.87 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_stockout_risk | 0 r1 | 6.27 | 5.3 | -0.97 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_expiring_items | 0 r1 | 7.25 | 3.14 | -4.11 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_upcoming_deliveries | 0 r1 | 4.18 | 8.23 | 4.05 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 r1 | 5.19 | 3.19 | -2 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_promo_list | 0 r1 | 7.37 | 3.19 | -4.18 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_data_integrity | 0 r1 | 4.22 | 2.21 | -2.01 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_transfer_options | 0 r1 | 28.84 | 13.5 | -15.34 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 r1 | 29.85 | 7.33 | -22.52 | done -> done | 2 -> 2 | 1 -> 0 | - | - |
| specialist_supply | 0 r1 | 14.41 | 6.22 | -8.19 | done -> done | 2 -> 2 | 0 -> 0 | - | - |
| specialist_strategist | 0 r1 | 9.26 | 11.5 | 2.24 | done -> done | 3 -> 2 | 0 -> 1 | - | - |
| multi_specialist | 0 r1 | 63.84 | 21.74 | -42.1 | done -> done | 3 -> 3 | 2 -> 2 | - | - |
| proposal | 0 r1 | 25.65 | 7.32 | -18.33 | done -> done | 2 -> 2 | 0 -> 0 | - | - |
| unsupported | 0 r1 | 8.31 | 6.34 | -1.97 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 0 r1 | 7.31 | 5.29 | -2.02 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 r1 | 14.42 | 6.26 | -8.16 | done -> done | 1 -> 1 | 0 -> 0 | - | garbled |
| follow_up | 2 r1 | 7.52 | 4.18 | -3.34 | done -> done | 0 -> 0 | 0 -> 0 | - | garbled |
| burst | 0 r1 | 3.53 | 4.53 | 1 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 1 r1 | 5.55 | 4.48 | -1.07 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 r1 | 6.64 | 4.4 | -2.24 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 r1 | 8.69 | 4.43 | -4.26 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 4 r1 | 18.96 | 7.63 | -11.33 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| simple | 0 r2 | 5.2 | 4.21 | -0.99 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 r2 | 13.38 | 6.24 | -7.14 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 r2 | 9.29 | 5.23 | -4.06 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 r2 | 25.36 | 6.24 | -19.12 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_stockout_risk | 0 r2 | 8.37 | 4.18 | -4.19 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_expiring_items | 0 r2 | 6.3 | 3.16 | -3.14 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_upcoming_deliveries | 0 r2 | 6.23 | 3.14 | -3.09 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 r2 | 6.23 | 3.2 | -3.03 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_promo_list | 0 r2 | 5.22 | 3.23 | -1.99 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_data_integrity | 0 r2 | 8.3 | 3.12 | -5.18 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_transfer_options | 0 r2 | 25.8 | 15.49 | -10.31 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 r2 | 32.04 | 15.46 | -16.58 | done -> done | 3 -> 2 | 2 -> 0 | - | - |
| specialist_supply | 0 r2 | 10.29 | 4.2 | -6.09 | done -> done | 1 -> 2 | 0 -> 0 | - | - |
| specialist_strategist | 0 r2 | 52.32 | 8.32 | -44 | done -> done | 3 -> 5 | 0 -> 0 | - | - |
| multi_specialist | 0 r2 | 39.28 | 22.99 | -16.29 | done -> done | 3 -> 3 | 2 -> 2 | - | garbled |
| proposal | 0 r2 | 35.14 | 7.34 | -27.8 | done -> done | 3 -> 2 | 1 -> 0 | - | - |
| unsupported | 0 r2 | 10.35 | 4.26 | -6.09 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 0 r2 | 14.4 | 5.17 | -9.23 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 r2 | 15.35 | 6.22 | -9.13 | done -> done | 1 -> 1 | 0 -> 0 | - | garbled |
| follow_up | 2 r2 | 5.21 | 4.15 | -1.06 | done -> done | 0 -> 0 | 0 -> 0 | - | - |
| burst | 0 r2 | 5.57 | 4.66 | -0.91 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 1 r2 | 7.57 | 3.67 | -3.9 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 r2 | 10.66 | 3.66 | -7 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 r2 | 14.73 | 3.65 | -11.08 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 4 r2 | 9.67 | 5.67 | -4 | done -> done | 1 -> 1 | 0 -> 0 | - | - |

## Aggregates

| metric | before | after | delta |
|---|---|---|---|
| latency_p50_s | 8.69 | 4.53 | -4.16 |
| latency_p95_s | 35.14 | 18.66 | -16.48 |
| latency_max_s | 63.84 | 22.99 | -40.85 |
| first_text_p50_s | 4.29 | 2.93 | -1.36 |
| first_text_p95_s | 23.05 | 11.56 | -11.49 |
| failure_rate | 0 | 0 | 0 |
| tool_calls_total | 97 | 99 | 2 |
| peer_asks_total | 14 | 10 | -4 |
| garbled_fragments_total | 7 | 2 | -5 |
| garbled_turns | 5 | 2 | -3 |

## Per path (median)

`composite`: the turns the fast path answered; `defer`: the turns every mode runs the same way (the true control: a change there is provider drift); `pass`: the turns `on` sends to the entry profile instead of the router's route (a change there is behaviour); `unknown`: no decision recorded.

| path | turns before / after | latency before s | latency after s | first text before s | first text after s |
|---|---|---|---|---|---|
| composite | 42 / 42 | 6.25 | 3.71 | 4.21 | 2.83 |
| defer (true control) | 12 / 15 | 10.88 | 6.34 | 5.09 | 3.29 |
| pass | 21 / 18 | 25.65 | 7.39 | 4.26 | 2.92 |
| unknown | 0 / 0 | - | - | - | - |

- flags before: {"garbled": 5, "internal_names": 1}
- flags after: {"garbled": 2, "internal_names": 2}
- burst before: {"turns": 15, "failed": 0, "latency_max_s": 18.96, "latency_p50_s": 8.69}
- burst after: {"turns": 15, "failed": 0, "latency_max_s": 7.63, "latency_p50_s": 4.42}
