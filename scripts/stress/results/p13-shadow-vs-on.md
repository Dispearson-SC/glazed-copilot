# Stress battery compare: p13-shadow -> p13-on

| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |
|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | 8.3 | 4.19 | -4.11 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 | 4.22 | 6.26 | 2.04 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 | 4.25 | 5.19 | 0.94 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 | 10.4 | 15.58 | 5.18 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_stockout_risk | 0 | 6.24 | 9.33 | 3.09 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_expiring_items | 0 | 5.17 | 4.22 | -0.95 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_upcoming_deliveries | 0 | 5.23 | 5.19 | -0.04 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 | 3.24 | 25.78 | 22.54 | done -> done | 1 -> 2 | 0 -> 1 | - | - |
| intent_promo_list | 0 | 3.2 | 3.17 | -0.03 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_data_integrity | 0 | 19.61 | 37 | 17.39 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| intent_transfer_options | 0 | 17.48 | 40.05 | 22.57 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 | 14.38 | 32.02 | 17.64 | done -> done | 2 -> 2 | 0 -> 1 | - | - |
| specialist_supply | 0 | 9.29 | 7.28 | -2.01 | done -> done | 2 -> 2 | 0 -> 0 | - | - |
| specialist_strategist | 0 | 12.4 | 20.7 | 8.3 | done -> done | 5 -> 2 | 0 -> 1 | - | - |
| multi_specialist | 0 | 30.86 | 44.25 | 13.39 | done -> done | 3 -> 3 | 2 -> 2 | garbled | - |
| proposal | 0 | 8.24 | 12.36 | 4.12 | done -> done | 2 -> 2 | 0 -> 0 | - | - |
| unsupported | 0 | 7.4 | 14.32 | 6.92 | done -> done | 1 -> 0 | 0 -> 0 | - | - |
| follow_up | 0 | 7.26 | 7.26 | 0 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 | 25.58 | 19.52 | -6.06 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 2 | 6.21 | 9.39 | 3.18 | done -> done | 0 -> 0 | 0 -> 0 | - | - |
| burst | 0 | 8.51 | 8.72 | 0.21 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 1 | 4.34 | 6.74 | 2.4 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 | 11.55 | 5.69 | -5.86 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 | 4.42 | 7.76 | 3.34 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 4 | 8.53 | 11.8 | 3.27 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| simple | 0 r1 | 10.51 | 5.19 | -5.32 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 r1 | 5.27 | 5.23 | -0.04 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 r1 | 10.32 | 49.23 | 38.91 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 r1 | 9.37 | 15.37 | 6 | done -> done | 1 -> 1 | 0 -> 0 | garbled | - |
| intent_stockout_risk | 0 r1 | 6.25 | 11.29 | 5.04 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_expiring_items | 0 r1 | 7.26 | 10.28 | 3.02 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_upcoming_deliveries | 0 r1 | 6.23 | 8.31 | 2.08 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 r1 | 20.49 | 35.04 | 14.55 | done -> done | 1 -> 2 | 0 -> 1 | garbled | - |
| intent_promo_list | 0 r1 | 3.15 | 4.17 | 1.02 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_data_integrity | 0 r1 | 5.23 | 23.64 | 18.41 | done -> done | 1 -> 2 | 0 -> 1 | - | - |
| intent_transfer_options | 0 r1 | 53.49 | 17.57 | -35.92 | done -> done | 2 -> 2 | 1 -> 1 | garbled | - |
| specialist_past | 0 r1 | 12.34 | 26.7 | 14.36 | done -> done | 3 -> 2 | 0 -> 1 | - | - |
| specialist_supply | 0 r1 | 5.17 | 16.62 | 11.45 | done -> done | 2 -> 2 | 0 -> 0 | - | - |
| specialist_strategist | 0 r1 | 6.26 | 10.34 | 4.08 | done -> done | 3 -> 3 | 0 -> 0 | garbled | - |
| multi_specialist | 0 r1 | 29.9 | 51.56 | 21.66 | done -> done | 6 -> 3 | 2 -> 2 | - | - |
| proposal | 0 r1 | 9.26 | 8.3 | -0.96 | done -> done | 2 -> 2 | 0 -> 0 | - | - |
| unsupported | 0 r1 | 8.21 | 10.33 | 2.12 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 0 r1 | 10.31 | 8.47 | -1.84 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 r1 | 10.26 | 9.32 | -0.94 | done -> done | 1 -> 1 | 0 -> 0 | - | garbled, internal_names |
| follow_up | 2 r1 | 5.16 | 8.27 | 3.11 | done -> done | 0 -> 0 | 0 -> 0 | - | - |
| burst | 0 r1 | 4.43 | 6.61 | 2.18 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 1 r1 | 5.48 | 5.56 | 0.08 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 r1 | 12.66 | 6.55 | -6.11 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 r1 | 6.51 | 6.61 | 0.1 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 4 r1 | 6.54 | 10.66 | 4.12 | done -> done | 1 -> 1 | 0 -> 0 | - | garbled |
| simple | 0 r2 | 12.31 | 7.35 | -4.96 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 r2 | 6.24 | 6.24 | 0 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 r2 | 7.24 | 19.53 | 12.29 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 r2 | 13.39 | 12.49 | -0.9 | done -> done | 1 -> 1 | 0 -> 0 | garbled | - |
| intent_stockout_risk | 0 r2 | 6.28 | 11.3 | 5.02 | done -> done | 1 -> 1 | 0 -> 0 | garbled | internal_names |
| intent_expiring_items | 0 r2 | 5.18 | 3.13 | -2.05 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_upcoming_deliveries | 0 r2 | 6.23 | 6.23 | 0 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 r2 | 4.19 | 17.55 | 13.36 | done -> done | 1 -> 2 | 0 -> 1 | - | - |
| intent_promo_list | 0 r2 | 6.24 | 11.32 | 5.08 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_data_integrity | 0 r2 | 8.21 | 37.09 | 28.88 | done -> done | 1 -> 2 | 0 -> 1 | - | - |
| intent_transfer_options | 0 r2 | 35.86 | 29.84 | -6.02 | done -> done | 2 -> 2 | 1 -> 1 | - | garbled |
| specialist_past | 0 r2 | 14.41 | 24.74 | 10.33 | done -> done | 3 -> 2 | 0 -> 1 | - | - |
| specialist_supply | 0 r2 | 6.26 | 13.38 | 7.12 | done -> done | 2 -> 2 | 0 -> 0 | - | - |
| specialist_strategist | 0 r2 | 25.78 | 7.3 | -18.48 | done -> done | 2 -> 4 | 1 -> 0 | garbled | internal_names |
| multi_specialist | 0 r2 | 35.2 | 34.13 | -1.07 | done -> done | 7 -> 3 | 2 -> 2 | - | - |
| proposal | 0 r2 | 11.37 | 11.37 | 0 | done -> done | 2 -> 2 | 0 -> 0 | - | garbled, internal_names |
| unsupported | 0 r2 | 8.25 | 8.29 | 0.04 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 0 r2 | 6.21 | 13.37 | 7.16 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 r2 | 9.29 | 15.39 | 6.1 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 2 r2 | 5.23 | 11.37 | 6.14 | done -> done | 0 -> 0 | 0 -> 0 | - | - |
| burst | 0 r2 | 4.48 | 5.42 | 0.94 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 1 r2 | 5.51 | 4.38 | -1.13 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 r2 | 10.66 | 5.43 | -5.23 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 r2 | 7.48 | 4.38 | -3.1 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 4 r2 | 10.67 | 15.63 | 4.96 | done -> done | 1 -> 1 | 0 -> 0 | - | - |

## Aggregates

| metric | before | after | delta |
|---|---|---|---|
| latency_p50_s | 7.48 | 10.33 | 2.85 |
| latency_p95_s | 30.86 | 40.05 | 9.19 |
| latency_max_s | 53.49 | 51.56 | -1.93 |
| first_text_p50_s | 4.35 | 4.86 | 0.51 |
| first_text_p95_s | 25.79 | 31.26 | 5.47 |
| failure_rate | 0 | 0 | 0 |
| tool_calls_total | 107 | 101 | -6 |
| peer_asks_total | 11 | 19 | 8 |
| garbled_fragments_total | 31 | 16 | -15 |
| garbled_turns | 7 | 11 | 4 |

## Per path (median)

`composite`: the turns the fast path answered; `other`: the turns every mode runs the same way (a change there is provider drift); `unknown`: no decision recorded.

| path | turns before / after | latency before s | latency after s | first text before s | first text after s |
|---|---|---|---|---|---|
| composite | 34 / 34 | 6.24 | 6.25 | 3.98 | 4.54 |
| other | 41 / 41 | 9.29 | 15.63 | 4.61 | 5.63 |
| unknown | 0 / 0 | - | - | - | - |

- flags before: {"garbled": 7, "internal_names": 4}
- flags after: {"garbled": 11}
- burst before: {"turns": 15, "failed": 0, "latency_max_s": 12.66, "latency_p50_s": 6.54}
- burst after: {"turns": 15, "failed": 0, "latency_max_s": 15.63, "latency_p50_s": 6.61}

## Per verdict (median, P13 operator analysis)

The `other` bucket mixes two kinds of turns. `defer:*` turns run the same code in both modes (the true control);
`pass:*` turns do NOT: in `on` a pass runs the orchestrator instead of the route or intent plan Jev chose, so their
change is behaviour, not drift.

| verdict | shadow turns | shadow latency s | shadow first text s | shadow garbled | on turns | on latency s | on first text s | on garbled |
|---|---|---|---|---|---|---|---|---|
| composite | 34 | 6.24 | 3.98 | 0 | 34 | 6.25 | 4.54 | 1 |
| defer (true control) | 13 | 8.25 | 4.42 | 1 | 12 | 11.23 | 5.25 | 2 |
| pass:uncovered | 7 | 5.23 | 3.96 | 0 | 8 | 30.41 | 11.52 | 1 |
| pass:other | 21 | 12.34 | 4.81 | 6 | 21 | 15.58 | 5.07 | 7 |

- Composite stayed flat (6.24 -> 6.25 s) while the control drifted +36% (8.25 -> 11.23 s): relative gain, but not lower.
- `pass:uncovered` regressed 5.2 -> 30.4 s: `intent_staffing`, `intent_data_integrity` and two `intent_active_issues`
  turns are detected as asking more than their intent, so `on` sends them to the orchestrator (0 -> 3 peer asks)
  instead of the single-intent plan shadow runs.
- Garbled turns 7 -> 11 (fragments 31 -> 16): mostly glued numbers (`en14`, `el10`) on orchestrator turns and one
  composite with English `will`.

## Decision

Live mode left in `shadow`: p13-on had 0 failures and the ad-hoc combined questions were answered fully, but the
composite median was not lower than shadow and garbled turns rose (7 -> 11). Next: let `pass:uncovered` keep the
route/intent plan when one intent covers the main request, and re-run the interleaved battery.
