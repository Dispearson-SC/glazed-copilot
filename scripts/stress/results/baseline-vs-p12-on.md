# Stress battery: baseline -> p12-on

- **baseline**: `baseline-20261014T205252Z.json`, the build before Phase 3 (no streaming, no routing).
- **p12-on**: `p12-on-20261015T060252Z.json`. Agent-Core `d81e8dc`, glazed `185a3b5`, `AGENT_CORE_FAST_PATH=on`,
  intent threshold 0.7, reply cache off. Store S001, 2026-07-19, 25 turns, sandbox cases, no decision approved.
- The garbled counts come from rescoring every stored reply with the P12 detector (`battery.garbled_fragments`).
  The baseline file came before the detector, so the runner compare below shows `-` for its counts.

Summary: p12-on has 0 failures, like baseline. Latency p50 went from 15.69 s to 12.42 s, p95 from 62.69 s to 38.15 s
and burst p50 from 22.71 s to 6.48 s. Peer asks went from 17 to 5. The cost is 6 garbled turns against 0.
Five of those six are glued digits on the orchestrator/specialist path. One is a full-width bracket in a composite
reply. Most of the gain came from Phase 5 (routing and streaming). Use the four-run tables in `p12-shadow-vs-on.md`
to see what P12 itself changed.

## Per case (latency / first text / tool calls / peer asks)

| case | turn | baseline s / first-text s / tools / peers | p12-on s / first-text s / tools / peers |
|---|---|---|---|
| simple | 0 | 13.67 / - / 1 / 0 | 16.57 / 2.32 / 1 / 0 |
| intent_day_summary | 0 | 12.6 / - / 1 / 0 | 21.68 / 1.91 / 3 / 0 |
| intent_active_issues | 0 | 14.64 / - / 1 / 0 | 23.55 / 3.69 / 1 / 0 |
| intent_order_plan | 0 | 10.47 / - / 1 / 0 | 13.43 / 2.8 / 1 / 0 |
| intent_stockout_risk | 0 | 40.14 / - / 2 / 1 | 10.37 / 6.65 / 1 / 0 |
| intent_expiring_items | 0 | 31.61 / - / 2 / 1 | 4.17 / 3.13 / 1 / 0 |
| intent_upcoming_deliveries | 0 | 5.36 / - / 1 / 0 | 6.23 / 4.98 / 1 / 0 |
| intent_staffing | 0 | 26.39 / - / 2 / 1 | 5.2 / 4.11 / 1 / 0 |
| intent_promo_list | 0 | 13.73 / - / 2 / 1 | 6.26 / 2.81 / 1 / 0 |
| intent_data_integrity | 0 | 12.65 / - / 2 / 1 | 5.2 / 3.52 / 1 / 0 |
| intent_transfer_options | 0 | 28.45 / - / 2 / 1 | 30.98 / 3.23 / 2 / 1 |
| specialist_past | 0 | 21 / - / 2 / 1 | 38.15 / 34.08 / 3 / 2 |
| specialist_supply | 0 | 4.25 / - / 1 / 0 | 26.82 / 16.88 / 2 / 0 |
| specialist_strategist | 0 | 18.94 / - / 2 / 1 | 15.39 / 11.75 / 4 / 0 |
| multi_specialist | 0 | 97.82 / - / 3 / 2 | 91.74 / 80.02 / 7 / 2 |
| proposal | 0 | 32.61 / - / 3 / 1 | 33.81 / 2.43 / 2 / 0 |
| unsupported | 0 | 11.58 / - / 2 / 1 | 5.24 / 3.62 / 1 / 0 |
| follow_up | 0 | 15.69 / - / 1 / 0 | 6.37 / 3.78 / 1 / 0 |
| follow_up | 1 | 14.58 / - / 1 / 0 | 26.83 / 14.47 / 1 / 0 |
| follow_up | 2 | 43.79 / - / 2 / 1 | 12.42 / 4.33 / 0 / 0 |
| burst | 0 | 22.71 / - / 2 / 1 | 6.48 / 6.03 / 1 / 0 |
| burst | 1 | 62.69 / - / 2 / 1 | 3.41 / 2.85 / 1 / 0 |
| burst | 2 | 4.69 / - / 1 / 0 | 9.56 / 8.22 / 1 / 0 |
| burst | 3 | 15.17 / - / 2 / 1 | 4.42 / 3.56 / 1 / 0 |
| burst | 4 | 41.52 / - / 2 / 1 | 24.85 / 19.7 / 1 / 0 |

## Aggregates (garbled rescored with the P12 detector on every run)

| metric | baseline | p12-on |
|---|---|---|
| turns | 25 | 25 |
| latency p50 s | 15.69 | 12.42 |
| latency p95 s | 62.69 | 38.15 |
| latency max s | 97.82 | 91.74 |
| first text p50 s | - | 3.78 |
| first text p95 s | - | 34.08 |
| first text measured | 0 | 25 |
| failures | 0 | 0 |
| tool calls | 43 | 40 |
| peer asks | 17 | 5 |
| garbled fragments (P12 detector, rescored) | 0 | 6 |
| garbled turns (rescored) | 0 | 6 |
| burst p50 s | 22.71 | 6.48 |
| burst max s | 62.69 | 24.85 |
| burst failed | 0 | 0 |

## Garbled fragments

| run | case | turn | fragments |
|---|---|---|---|
| p12-on | intent_stockout_risk | 0 | `）` |
| p12-on | specialist_past | 0 | `con58,90` |
| p12-on | specialist_supply | 0 | `con2.16` |
| p12-on | multi_specialist | 0 | `en28` |
| p12-on | follow_up | 1 | `el21.` |
| p12-on | follow_up | 2 | `el52` |

## Route and fast-path decision (p12-on; baseline predates the route audit)

| case | turn | p12-on | composite members (on) |
|---|---|---|---|
| simple | 0 | none_of_these / fp=defer:no_intent | - |
| intent_day_summary | 0 | day_summary / fp=defer:no_intent | - |
| intent_active_issues | 0 | active_issues / fp=composite [active_issues] | active_issues/composite |
| intent_order_plan | 0 | order_plan / fp=pass:complex [order_plan] | - |
| intent_stockout_risk | 0 | stockout_risk / fp=composite [stockout_risk] | stockout_risk/composite |
| intent_expiring_items | 0 | expiring_items / fp=composite [expiring_items] | expiring_items/composite |
| intent_upcoming_deliveries | 0 | upcoming_deliveries / fp=composite [upcoming_deliveries] | upcoming_deliveries/composite |
| intent_staffing | 0 | staffing / fp=composite [staffing] | staffing/composite |
| intent_promo_list | 0 | promo_list / fp=composite [promo_list] | promo_list/composite |
| intent_data_integrity | 0 | data_integrity / fp=composite [data_integrity] | data_integrity/composite |
| intent_transfer_options | 0 | request_action / fp=pass:complex | - |
| specialist_past | 0 | past_experience / fp=pass:complex | - |
| specialist_supply | 0 | supply_analysis / fp=defer:no_intent | - |
| specialist_strategist | 0 | strategy_flow / fp=defer:no_intent | - |
| multi_specialist | 0 | none_of_these / fp=pass:complex [expiring_items,order_plan,stockout_risk] | - |
| proposal | 0 | request_action / fp=pass:action_request [order_plan,stockout_risk] | - |
| unsupported | 0 | present_metrics / fp=defer:no_intent | - |
| follow_up | 0 | stockout_risk / fp=composite [stockout_risk] | stockout_risk/composite |
| follow_up | 1 | stockout_risk (follow_up) / fp=pass:depends_on_history | - |
| follow_up | 2 | order_plan (follow_up) / fp=pass:depends_on_history [order_plan,upcoming_deliveries] | - |
| burst | 0 | day_summary / fp=composite [day_summary] | day_summary/composite |
| burst | 1 | active_issues / fp=composite [active_issues] | active_issues/composite |
| burst | 2 | upcoming_deliveries / fp=composite [upcoming_deliveries] | upcoming_deliveries/composite |
| burst | 3 | promo_list / fp=composite [promo_list] | promo_list/composite |
| burst | 4 | present_metrics / fp=defer:no_intent | - |

## Runner compare output (`run.py compare`)

### Stress battery compare: baseline -> p12-on

| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |
|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | 13.67 | 16.57 | 2.9 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 | 12.6 | 21.68 | 9.08 | done -> done | 1 -> 3 | 0 -> 0 | - | - |
| intent_active_issues | 0 | 14.64 | 23.55 | 8.91 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 | 10.47 | 13.43 | 2.96 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_stockout_risk | 0 | 40.14 | 10.37 | -29.77 | done -> done | 2 -> 1 | 1 -> 0 | garbled | - |
| intent_expiring_items | 0 | 31.61 | 4.17 | -27.44 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_upcoming_deliveries | 0 | 5.36 | 6.23 | 0.87 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 | 26.39 | 5.2 | -21.19 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_promo_list | 0 | 13.73 | 6.26 | -7.47 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_data_integrity | 0 | 12.65 | 5.2 | -7.45 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| intent_transfer_options | 0 | 28.45 | 30.98 | 2.53 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 | 21 | 38.15 | 17.15 | done -> done | 2 -> 3 | 1 -> 2 | garbled | - |
| specialist_supply | 0 | 4.25 | 26.82 | 22.57 | done -> done | 1 -> 2 | 0 -> 0 | garbled | - |
| specialist_strategist | 0 | 18.94 | 15.39 | -3.55 | done -> done | 2 -> 4 | 1 -> 0 | - | - |
| multi_specialist | 0 | 97.82 | 91.74 | -6.08 | done -> done | 3 -> 7 | 2 -> 2 | garbled | - |
| proposal | 0 | 32.61 | 33.81 | 1.2 | done -> done | 3 -> 2 | 1 -> 0 | - | - |
| unsupported | 0 | 11.58 | 5.24 | -6.34 | done -> done | 2 -> 1 | 1 -> 0 | non_spanish | - |
| follow_up | 0 | 15.69 | 6.37 | -9.32 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 | 14.58 | 26.83 | 12.25 | done -> done | 1 -> 1 | 0 -> 0 | garbled | - |
| follow_up | 2 | 43.79 | 12.42 | -31.37 | done -> done | 2 -> 0 | 1 -> 0 | garbled | - |
| burst | 0 | 22.71 | 6.48 | -16.23 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 1 | 62.69 | 3.41 | -59.28 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 2 | 4.69 | 9.56 | 4.87 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 | 15.17 | 4.42 | -10.75 | done -> done | 2 -> 1 | 1 -> 0 | - | - |
| burst | 4 | 41.52 | 24.85 | -16.67 | done -> done | 2 -> 1 | 1 -> 0 | - | - |

## Aggregates

| metric | before | after | delta |
|---|---|---|---|
| latency_p50_s | 15.69 | 12.42 | -3.27 |
| latency_p95_s | 62.69 | 38.15 | -24.54 |
| latency_max_s | 97.82 | 91.74 | -6.08 |
| first_text_p50_s | - | 3.78 | - |
| first_text_p95_s | - | 34.08 | - |
| failure_rate | 0 | 0 | 0 |
| tool_calls_total | 43 | 40 | -3 |
| peer_asks_total | 17 | 5 | -12 |
| garbled_fragments_total | - | 6 | - |
| garbled_turns | - | 6 | - |

- flags before: {}
- flags after: {"garbled": 6, "non_spanish": 1}
- burst before: {"turns": 5, "failed": 0, "latency_max_s": 62.69, "latency_p50_s": 22.71}
- burst after: {"turns": 5, "failed": 0, "latency_max_s": 24.85, "latency_p50_s": 6.48}


