# Stress battery compare: baseline -> phase5d

| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |
|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | 13.67 | 8.28 | -5.39 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 | 12.6 | 5.23 | -7.37 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 | 14.64 | 6.26 | -8.38 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 | 10.47 | 12.4 | 1.93 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_stockout_risk | 0 | 40.14 | 5.21 | -34.93 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_expiring_items | 0 | 31.61 | 3.22 | -28.39 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_upcoming_deliveries | 0 | 5.36 | 5.17 | -0.19 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 | 26.39 | 3.19 | -23.2 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_promo_list | 0 | 13.73 | 3.22 | -10.51 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_data_integrity | 0 | 12.65 | 4.31 | -8.34 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_transfer_options | 0 | 28.45 | 14.45 | -14 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 | 21 | 7.26 | -13.74 | done -> done | 2 -> 2 | 1 -> 0 | - | - |
| specialist_supply | 0 | 4.25 | 14.46 | 10.21 | done -> done | 1 -> 2 | 0 -> 0 | - | - |
| specialist_strategist | 0 | 18.94 | 7.26 | -11.68 | done -> done | 2 -> 4 | 1 -> 0 | - | - |
| multi_specialist | 0 | 97.82 | 32.04 | -65.78 | done -> done | 3 -> 8 | 2 -> 2 | - | - |
| proposal | 0 | 32.61 | 7.22 | -25.39 | done -> done | 3 -> 2 | 1 -> 0 | - | - |
| unsupported | 0 | 11.58 | 11.38 | -0.2 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| follow_up | 0 | 15.69 | 5.2 | -10.49 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 | 14.58 | 6.27 | -8.31 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 2 | 43.79 | 5.22 | -38.57 | done -> done | 2 -> 0 | 1 -> 0 | - | - |
| burst | 0 | 22.71 | 4.54 | -18.17 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 1 | 62.69 | 9.62 | -53.07 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 2 | 4.69 | 6.65 | 1.96 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 | 15.17 | 3.53 | -11.64 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 4 | 41.52 | 5.59 | -35.93 | done -> done | 2 -> 1 | 1 -> 0 | - | - |

## Aggregates

| metric | before | after | delta |
|---|---|---|---|
| latency_p50_s | 15.69 | 6.26 | -9.43 |
| latency_p95_s | 62.69 | 14.46 | -48.23 |
| latency_max_s | 97.82 | 32.04 | -65.78 |
| first_text_p50_s | - | 3.08 | - |
| first_text_p95_s | - | 12.53 | - |
| failure_rate | 0 | 0 | 0 |
| tool_calls_total | 43 | 38 | -5 |
| peer_asks_total | 17 | 3 | -14 |

- flags before: {}
- flags after: {}
- burst before: {"turns": 5, "failed": 0, "latency_max_s": 62.69, "latency_p50_s": 22.71}
- burst after: {"turns": 5, "failed": 0, "latency_max_s": 9.62, "latency_p50_s": 5.59}


## All stages per case (baseline / phase3 / phase5 / phase5b / phase5c / phase5d)

| case | turn | latency s (base / p3 / p5 / p5b / p5c / p5d) | first text s (p5c / p5d) | tools (base / p3 / p5 / p5b / p5c / p5d) | peers (base / p3 / p5 / p5b / p5c / p5d) |
|---|---|---|---|---|---|
| simple | 0 | 13.67 / 10.45 / 7.71 / 15.46 / 17.51 / 8.28 | 2.83 / 4.55 | 1 / 1 / 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 / 0 / 0 |
| intent_day_summary | 0 | 12.6 / 8.42 / 78.68 / 7.26 / 4.24 / 5.23 | 2.93 / 3.01 | 1 / 1 / 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 / 0 / 0 |
| intent_active_issues | 0 | 14.64 / 12.48 / 83.82 / 6.25 / 10.31 / 6.26 | 5.09 / 3.02 | 1 / 1 / 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 / 0 / 0 |
| intent_order_plan | 0 | 10.47 / 9.39 / 112.29 / 12.29 / 18.53 / 12.4 | 5.83 / 4.59 | 1 / 1 / 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 / 0 / 0 |
| intent_stockout_risk | 0 | 40.14 / 36.72 / 42.6 / 8.19 / 7.23 / 5.21 | 5.75 / 4.42 | 2 / 2 / 1 / 1 / 1 / 1 | 1 / 1 / 0 / 0 / 0 / 0 |
| intent_expiring_items | 0 | 31.61 / 23.09 / 10.37 / 4.18 / 10.33 / 3.22 | 7.11 / 2.64 | 2 / 2 / 1 / 1 / 1 / 1 | 1 / 1 / 0 / 0 / 0 / 0 |
| intent_upcoming_deliveries | 0 | 5.36 / 5.25 / 46.72 / 4.18 / 6.26 / 5.17 | 3.71 / 4.16 | 1 / 1 / 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 / 0 / 0 |
| intent_staffing | 0 | 26.39 / 47.25 / 11.55 / 4.23 / 6.23 / 3.19 | 3.16 / 2.16 | 2 / 2 / 1 / 1 / 1 / 1 | 1 / 1 / 0 / 0 / 0 / 0 |
| intent_promo_list | 0 | 13.73 / 15.77 / 6.31 / 4.24 / 4.15 / 3.22 | 2.78 / 2.67 | 2 / 2 / 1 / 1 / 1 / 1 | 1 / 1 / 0 / 0 / 0 / 0 |
| intent_data_integrity | 0 | 12.65 / 25.29 / 22.82 / 4.18 / 7.27 / 4.31 | 5.14 / 2.96 | 2 / 2 / 1 / 1 / 1 / 1 | 1 / 1 / 0 / 0 / 0 / 0 |
| intent_transfer_options | 0 | 28.45 / 30.4 / 27.28 / 101.63 / 48.17 / 14.45 | - / 12.53 | 2 / 2 / 2 / 3 / 2 / 2 | 1 / 1 / 1 / 2 / 1 / 1 |
| specialist_past | 0 | 21.0 / 22.14 / 12.53 / 22.52 / 18.47 / 7.26 | 2.14 / 1.8 | 2 / 2 / 3 / 4 / 3 / 2 | 1 / 1 / 0 / 0 / 0 / 0 |
| specialist_supply | 0 | 4.25 / 5.38 / 7.33 / 18.41 / 23.68 / 14.46 | 12.73 / 1.78 | 1 / 1 / 2 / 2 / 2 / 2 | 0 / 0 / 0 / 0 / 0 / 0 |
| specialist_strategist | 0 | 18.94 / 17.93 / 9.42 / 11.37 / 17.47 / 7.26 | 2.36 / 2.15 | 2 / 2 / 4 / 4 / 4 / 4 | 1 / 1 / 0 / 0 / 0 / 0 |
| multi_specialist | 0 | 97.82 / 78.81 / 133.61 / 147.72 / 145.8 / 32.04 | - / 24.14 | 3 / 8 / 6 / 8 / 4 / 8 | 2 / 2 / 3 / 2 / 3 / 2 |
| proposal | 0 | 32.61 / 8.37 / 38.31 / 22.49 / 81.31 / 7.22 | 1.6 / 1.93 | 3 / 2 / 1 / 2 / 4 / 2 | 1 / 0 / 0 / 0 / 2 / 0 |
| unsupported | 0 | 11.58 / 5.29 / 11.52 / 8.29 / 15.41 / 11.38 | 7.24 / 6.64 | 2 / 1 / 2 / 1 / 1 / 1 | 1 / 0 / 0 / 0 / 0 / 0 |
| follow_up | 0 | 15.69 / 54.73 / 37.23 / 9.22 / 12.35 / 5.2 | 6.72 / 3.66 | 1 / 2 / 1 / 1 / 1 / 1 | 0 / 1 / 0 / 0 / 0 / 0 |
| follow_up | 1 | 14.58 / 15.72 / 39.39 / 18.45 / 19.51 / 6.27 | 14.97 / 3.65 | 1 / 1 / 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 / 0 / 0 |
| follow_up | 2 | 43.79 / 5.26 / 21.98 / 14.41 / 10.4 / 5.22 | 7.6 / 2.61 | 2 / 0 / 1 / 0 / 0 / 0 | 1 / 0 / 0 / 0 / 0 / 0 |
| burst | 0 | 22.71 / 17.28 / 10.85 / 4.54 / 6.55 / 4.54 | 5.34 / 3.08 | 2 / 2 / 1 / 1 / 1 / 1 | 1 / 1 / 0 / 0 / 0 / 0 |
| burst | 1 | 62.69 / 6.56 / 5.56 / 7.61 / 6.56 / 9.62 | 5.82 / 9.16 | 2 / 1 / 1 / 1 / 1 / 1 | 1 / 0 / 0 / 0 / 0 / 0 |
| burst | 2 | 4.69 / 5.6 / 30.41 / 9.56 / 5.48 / 6.65 | 5.01 / 5.68 | 1 / 1 / 1 / 1 / 1 / 1 | 0 / 0 / 0 / 0 / 0 / 0 |
| burst | 3 | 15.17 / 24.67 / 4.61 / 6.52 / 5.46 / 3.53 | 4.68 / 2.76 | 2 / 2 / 1 / 1 / 1 / 1 | 1 / 1 / 0 / 0 / 0 / 0 |
| burst | 4 | 41.52 / 26.55 / 7.77 / 13.75 / 28.89 / 5.59 | 19.52 / 3.46 | 2 / 2 / 3 / 1 / 2 / 1 | 1 / 1 / 0 / 0 / 0 / 0 |

## Aggregates per stage

| metric | base | p3 | p5 | p5b | p5c | p5d |
|---|---|---|---|---|---|---|
| latency_p50_s | 15.69 | 15.77 | 21.98 | 9.22 | 10.4 | 6.26 |
| latency_p95_s | 62.69 | 54.73 | 112.29 | 101.63 | 81.31 | 14.46 |
| latency_max_s | 97.82 | 78.81 | 133.61 | 147.72 | 145.8 | 32.04 |
| first_text_p50_s | - | - | - | - | 5.14 | 3.08 |
| first_text_p95_s | - | - | - | - | 14.97 | 12.53 |
| failure_rate | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| tool_calls_total | 43 | 44 | 40 | 41 | 38 | 38 |
| peer_asks_total | 17 | 14 | 4 | 4 | 6 | 3 |
| burst | {"turns": 5, "failed": 0, "latency_max_s": 62.69, "latency_p50_s": 22.71} | {"turns": 5, "failed": 0, "latency_max_s": 26.55, "latency_p50_s": 17.28} | {"turns": 5, "failed": 0, "latency_max_s": 30.41, "latency_p50_s": 7.77} | {"turns": 5, "failed": 0, "latency_max_s": 13.75, "latency_p50_s": 7.61} | {"turns": 5, "failed": 0, "latency_max_s": 28.89, "latency_p50_s": 6.55} | {"turns": 5, "failed": 0, "latency_max_s": 9.62, "latency_p50_s": 5.59} |
| flag_counts | {} | {"internal_names": 1, "untraceable_numbers": 1} | {"check:proposal_pending": 1} | {"internal_names": 1} | {} | {} |

Notes:
- Deployed for phase5d: Agent-Core 92758eb (profile `model_settings.reasoning_effort: low` for every glazed role, the
  person's resumed turn streamed to the event feed, orchestrator `peers.visibility: full` capped at 4000 chars instead of
  a summary model call; DBOS pin unchanged at agent-core-turns.12, no drain) and glazed 3ea8eae (backend SSE open retry
  window about 3 s).
- Against the baseline: p50 15.7 -> 6.3 s, p95 62.7 -> 14.5 s, max 97.8 -> 32.0 s, burst p50 22.7 -> 5.6 s, no failures,
  no quality flags. Every case is faster than the baseline except three: `intent_order_plan` (10.5 -> 12.4 s, intent plan with a
  2.4k-token compose), `specialist_supply` (4.3 -> 14.5 s; routed specialist now, the baseline answered with one tool and
  no ask) and `burst[2]` (4.7 -> 6.7 s).
- Single run per stage: LLM variance applies.
