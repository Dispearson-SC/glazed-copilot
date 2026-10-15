# Stress battery: phase5d -> p12-shadow -> p12-on (P12 fast path)

Runs (store S001, 2026-07-19, 25 turns each, sandbox cases, no decision approved):

| run | file | build | fast path |
|---|---|---|---|
| baseline | `baseline-20261014T205252Z.json` | before Phase 3 | - |
| phase5d | `phase5d-20261015T041910Z.json` | Agent-Core `92758eb`, glazed `3ea8eae` | absent |
| p12-shadow | `p12-shadow-20261015T055500Z.json` | Agent-Core `d81e8dc`, glazed `185a3b5` | `shadow` (today's path; verdict recorded) |
| p12-on | `p12-on-20261015T060252Z.json` | Agent-Core `d81e8dc`, glazed `185a3b5` | `on` (threshold 0.7, cache off) |

## Verdict: the live mode stays `shadow`

The rule for keeping `on`: 0 failures, quality no worse (garbled count, no dropped parts), and latency equal to or
better than p12-shadow. p12-on fails it:

- Failures: 0 in both. Pass.
- Latency: p50 11.32 -> 12.42 s, p95 33.37 -> 38.15 s, burst max 8.82 -> 24.85 s. Fail. First text p50 got
  better (5.10 -> 3.78 s), but first text p95 got worse (22.27 -> 34.08 s).
- Quality: garbled turns went 3 -> 6. Fragments went 30 -> 6, but 27 of the 30 in shadow are full-width punctuation
  in one multi_specialist reply. One combined question dropped a part on the composite path (see the ad-hoc section).
  Fail.

Context the aggregate hides:

- The 12 turns that ran as a composite in `on` got faster: median latency 7.50 -> 6.25 s, mean 8.45 -> 7.60 s,
  median first text 5.39 -> 3.73 s.
- The other 13 turns run the same code in both modes, yet they slowed from a median of 15.44 s to 24.85 s. That drift
  comes from the model provider between the two runs, not from the fast path. With one run per mode, the aggregate is
  dominated by that noise.
- The Jev route call grew from 1026 to 1694 input tokens on average and from 198 to 435 output tokens, but its
  median time went only 135 -> 144 ms. Shadow costs almost nothing in latency.
- The fast-path verdict is the same in shadow and on for all 25 turns. Only the intent list of follow_up[1] differs,
  and that turn passes anyway. So the System One decision is stable from run to run. Even the plain day_summary
  question ("Dame el resumen del día de hoy.") is `defer:no_intent` in both runs: the router label is day_summary,
  but the intent score stays under 0.7.
- phase5d -> p12-shadow is slower (p50 6.26 -> 11.32 s), although shadow runs phase5d's path plus a route call that
  is about 10 ms longer. This is the same provider drift, measured about 1.5 h apart.

What `on` needs first: better day_summary detection (in the battery, "¿Cómo voy hoy...?" falls under 0.7 or is left
out of the intent set), a composite compose that never answers a part as "no disponible" when that part was not
planned, and a repeat run of each mode (or an interleaved run) to separate provider drift from the fast path.

## Aggregates, four runs (garbled rescored with the P12 detector on every run)

| metric | baseline | phase5d | p12-shadow | p12-on |
|---|---|---|---|---|
| turns | 25 | 25 | 25 | 25 |
| latency p50 s | 15.69 | 6.26 | 11.32 | 12.42 |
| latency p95 s | 62.69 | 14.46 | 33.37 | 38.15 |
| latency max s | 97.82 | 32.04 | 81 | 91.74 |
| first text p50 s | - | 3.08 | 5.1 | 3.78 |
| first text p95 s | - | 12.53 | 22.27 | 34.08 |
| first text measured | 0 | 25 | 25 | 25 |
| failures | 0 | 0 | 0 | 0 |
| tool calls | 43 | 38 | 32 | 40 |
| peer asks | 17 | 3 | 3 | 5 |
| garbled fragments (P12 detector, rescored) | 0 | 5 | 30 | 6 |
| garbled turns (rescored) | 0 | 2 | 3 | 6 |
| burst p50 s | 22.71 | 5.59 | 5.72 | 6.48 |
| burst max s | 62.69 | 9.62 | 8.82 | 24.85 |
| burst failed | 0 | 0 | 0 | 0 |

## Per case (latency / first text / tool calls / peer asks)

| case | turn | baseline s / first-text s / tools / peers | phase5d s / first-text s / tools / peers | p12-shadow s / first-text s / tools / peers | p12-on s / first-text s / tools / peers |
|---|---|---|---|---|---|
| simple | 0 | 13.67 / - / 1 / 0 | 8.28 / 4.55 / 1 / 0 | 16.57 / 2.39 / 1 / 0 | 16.57 / 2.32 / 1 / 0 |
| intent_day_summary | 0 | 12.6 / - / 1 / 0 | 5.23 / 3.01 / 1 / 0 | 8.26 / 6.51 / 1 / 0 | 21.68 / 1.91 / 3 / 0 |
| intent_active_issues | 0 | 14.64 / - / 1 / 0 | 6.26 / 3.02 / 1 / 0 | 13.34 / 3.77 / 1 / 0 | 23.55 / 3.69 / 1 / 0 |
| intent_order_plan | 0 | 10.47 / - / 1 / 0 | 12.4 / 4.59 / 1 / 0 | 14.46 / 6.05 / 1 / 0 | 13.43 / 2.8 / 1 / 0 |
| intent_stockout_risk | 0 | 40.14 / - / 2 / 1 | 5.21 / 4.42 / 1 / 0 | 6.34 / 5.83 / 1 / 0 | 10.37 / 6.65 / 1 / 0 |
| intent_expiring_items | 0 | 31.61 / - / 2 / 1 | 3.22 / 2.64 / 1 / 0 | 4.17 / 2.74 / 1 / 0 | 4.17 / 3.13 / 1 / 0 |
| intent_upcoming_deliveries | 0 | 5.36 / - / 1 / 0 | 5.17 / 4.16 / 1 / 0 | 10.26 / 6.27 / 1 / 0 | 6.23 / 4.98 / 1 / 0 |
| intent_staffing | 0 | 26.39 / - / 2 / 1 | 3.19 / 2.16 / 1 / 0 | 14.34 / 12.22 / 1 / 0 | 5.2 / 4.11 / 1 / 0 |
| intent_promo_list | 0 | 13.73 / - / 2 / 1 | 3.22 / 2.67 / 1 / 0 | 11.32 / 10.53 / 1 / 0 | 6.26 / 2.81 / 1 / 0 |
| intent_data_integrity | 0 | 12.65 / - / 2 / 1 | 4.31 / 2.96 / 1 / 0 | 8.23 / 3.67 / 1 / 0 | 5.2 / 3.52 / 1 / 0 |
| intent_transfer_options | 0 | 28.45 / - / 2 / 1 | 14.45 / 12.53 / 2 / 1 | 33.37 / 29.31 / 2 / 1 | 30.98 / 3.23 / 2 / 1 |
| specialist_past | 0 | 21 / - / 2 / 1 | 7.26 / 1.8 / 2 / 0 | 12.36 / 9.37 / 3 / 0 | 38.15 / 34.08 / 3 / 2 |
| specialist_supply | 0 | 4.25 / - / 1 / 0 | 14.46 / 1.78 / 2 / 0 | 11.36 / 2.64 / 2 / 0 | 26.82 / 16.88 / 2 / 0 |
| specialist_strategist | 0 | 18.94 / - / 2 / 1 | 7.26 / 2.15 / 4 / 0 | 28.73 / 22.27 / 3 / 0 | 15.39 / 11.75 / 4 / 0 |
| multi_specialist | 0 | 97.82 / - / 3 / 2 | 32.04 / 24.14 / 8 / 2 | 81 / 2.67 / 3 / 2 | 91.74 / 80.02 / 7 / 2 |
| proposal | 0 | 32.61 / - / 3 / 1 | 7.22 / 1.93 / 2 / 0 | 18.41 / 3.84 / 2 / 0 | 33.81 / 2.43 / 2 / 0 |
| unsupported | 0 | 11.58 / - / 2 / 1 | 11.38 / 6.64 / 1 / 0 | 5.15 / 3.17 / 0 / 0 | 5.24 / 3.62 / 1 / 0 |
| follow_up | 0 | 15.69 / - / 1 / 0 | 5.2 / 3.66 / 1 / 0 | 9.49 / 5.84 / 1 / 0 | 6.37 / 3.78 / 1 / 0 |
| follow_up | 1 | 14.58 / - / 1 / 0 | 6.27 / 3.65 / 1 / 0 | 17.41 / 6.7 / 1 / 0 | 26.83 / 14.47 / 1 / 0 |
| follow_up | 2 | 43.79 / - / 2 / 1 | 5.22 / 2.61 / 0 / 0 | 15.44 / 4.57 / 0 / 0 | 12.42 / 4.33 / 0 / 0 |
| burst | 0 | 22.71 / - / 2 / 1 | 4.54 / 3.08 / 1 / 0 | 5.7 / 4.54 / 1 / 0 | 6.48 / 6.03 / 1 / 0 |
| burst | 1 | 62.69 / - / 2 / 1 | 9.62 / 9.16 / 1 / 0 | 5.69 / 4.95 / 1 / 0 | 3.41 / 2.85 / 1 / 0 |
| burst | 2 | 4.69 / - / 1 / 0 | 6.65 / 5.68 / 1 / 0 | 6.77 / 6.01 / 1 / 0 | 9.56 / 8.22 / 1 / 0 |
| burst | 3 | 15.17 / - / 2 / 1 | 3.53 / 2.76 / 1 / 0 | 5.72 / 4.27 / 1 / 0 | 4.42 / 3.56 / 1 / 0 |
| burst | 4 | 41.52 / - / 2 / 1 | 5.59 / 3.46 / 1 / 0 | 8.82 / 5.1 / 1 / 0 | 24.85 / 19.7 / 1 / 0 |

## Route and fast-path decision per turn

`fp=` is the fast-path verdict recorded in `audit_turn_routes` (shadow: what it WOULD have done; on: what ran).

| case | turn | phase5d | p12-shadow | p12-on | composite members (on) |
|---|---|---|---|---|---|
| simple | 0 | none_of_these | none_of_these / fp=defer:no_intent | none_of_these / fp=defer:no_intent | - |
| intent_day_summary | 0 | day_summary | day_summary / fp=defer:no_intent | day_summary / fp=defer:no_intent | - |
| intent_active_issues | 0 | active_issues | active_issues / fp=composite [active_issues] | active_issues / fp=composite [active_issues] | active_issues/composite |
| intent_order_plan | 0 | order_plan | order_plan / fp=pass:complex [order_plan] | order_plan / fp=pass:complex [order_plan] | - |
| intent_stockout_risk | 0 | stockout_risk | stockout_risk / fp=composite [stockout_risk] | stockout_risk / fp=composite [stockout_risk] | stockout_risk/composite |
| intent_expiring_items | 0 | expiring_items | expiring_items / fp=composite [expiring_items] | expiring_items / fp=composite [expiring_items] | expiring_items/composite |
| intent_upcoming_deliveries | 0 | upcoming_deliveries | upcoming_deliveries / fp=composite [upcoming_deliveries] | upcoming_deliveries / fp=composite [upcoming_deliveries] | upcoming_deliveries/composite |
| intent_staffing | 0 | staffing | staffing / fp=composite [staffing] | staffing / fp=composite [staffing] | staffing/composite |
| intent_promo_list | 0 | promo_list | promo_list / fp=composite [promo_list] | promo_list / fp=composite [promo_list] | promo_list/composite |
| intent_data_integrity | 0 | data_integrity | data_integrity / fp=composite [data_integrity] | data_integrity / fp=composite [data_integrity] | data_integrity/composite |
| intent_transfer_options | 0 | request_action | request_action / fp=pass:complex | request_action / fp=pass:complex | - |
| specialist_past | 0 | past_experience | past_experience / fp=pass:complex | past_experience / fp=pass:complex | - |
| specialist_supply | 0 | supply_analysis | supply_analysis / fp=defer:no_intent | supply_analysis / fp=defer:no_intent | - |
| specialist_strategist | 0 | strategy_flow | strategy_flow / fp=defer:no_intent | strategy_flow / fp=defer:no_intent | - |
| multi_specialist | 0 | none_of_these | none_of_these / fp=pass:complex [expiring_items,order_plan,stockout_risk] | none_of_these / fp=pass:complex [expiring_items,order_plan,stockout_risk] | - |
| proposal | 0 | request_action | request_action / fp=pass:action_request [order_plan,stockout_risk] | request_action / fp=pass:action_request [order_plan,stockout_risk] | - |
| unsupported | 0 | present_metrics | present_metrics / fp=defer:no_intent | present_metrics / fp=defer:no_intent | - |
| follow_up | 0 | stockout_risk | stockout_risk / fp=composite [stockout_risk] | stockout_risk / fp=composite [stockout_risk] | stockout_risk/composite |
| follow_up | 1 | - (follow_up) | stockout_risk (follow_up) / fp=pass:depends_on_history [active_issues] | stockout_risk (follow_up) / fp=pass:depends_on_history | - |
| follow_up | 2 | - (follow_up) | order_plan (follow_up) / fp=pass:depends_on_history [order_plan,upcoming_deliveries] | order_plan (follow_up) / fp=pass:depends_on_history [order_plan,upcoming_deliveries] | - |
| burst | 0 | day_summary | day_summary / fp=composite [day_summary] | day_summary / fp=composite [day_summary] | day_summary/composite |
| burst | 1 | active_issues | active_issues / fp=composite [active_issues] | active_issues / fp=composite [active_issues] | active_issues/composite |
| burst | 2 | upcoming_deliveries | upcoming_deliveries / fp=composite [upcoming_deliveries] | upcoming_deliveries / fp=composite [upcoming_deliveries] | upcoming_deliveries/composite |
| burst | 3 | promo_list | promo_list / fp=composite [promo_list] | promo_list / fp=composite [promo_list] | promo_list/composite |
| burst | 4 | present_metrics | present_metrics / fp=defer:no_intent | present_metrics / fp=defer:no_intent | - |

Fast-path verdict counts:

| verdict | p12-shadow | p12-on |
|---|---|---|
| composite | 12 | 12 |
| defer:no_intent | 6 | 6 |
| pass:action_request | 1 | 1 |
| pass:complex | 4 | 4 |
| pass:depends_on_history | 2 | 2 |

## Garbled fragments

| run | case | turn | fragments |
|---|---|---|---|
| phase5d | simple | 0 | `order` |
| phase5d | multi_specialist | 0 | `trusted`, `hoyusted`, `en1`, `，` |
| p12-shadow | specialist_supply | 0 | `el2026` |
| p12-shadow | multi_specialist | 0 | `，`, `，`, `、`, `。`, `：`, `，` (+21 more) |
| p12-shadow | proposal | 0 | `a8d5f01e08dc`, `en10` |
| p12-on | intent_stockout_risk | 0 | `）` |
| p12-on | specialist_past | 0 | `con58,90` |
| p12-on | specialist_supply | 0 | `con2.16` |
| p12-on | multi_specialist | 0 | `en28` |
| p12-on | follow_up | 1 | `el21.` |
| p12-on | follow_up | 2 | `el52` |

## Ad-hoc combined questions (fast path `on`, sandbox cases, read by hand)

| question | fast path | members / tools | latency s | first text s | every part answered? |
|---|---|---|---|---|---|
| ¿Cómo voy hoy y qué tengo que pedir? (smoke, 06:02) | composite | order_plan / get_order_plan | 9.50 | 6.60 | **No**: day_summary was not detected; the reply says "los datos disponibles no incluyen ventas ni Indicators de desempeño de hoy; no está disponible" and answers only the order |
| ¿Cómo voy hoy y qué tengo que pedir? (repeat, 06:10) | defer:no_intent (orchestrator) | get_snapshot | 28.72 | 3.76 | Yes: weekly sales/merma plus the order plan (orchestrator path) |
| ¿Qué alertas urgentes tengo y qué entregas llegan esta semana? (smoke) | composite | active_issues, upcoming_deliveries / get_issues, get_deliveries (10 ms apart) | 9.47 | 5.95 | Yes |
| ¿Qué se me caduca y qué entregas llegan esta semana? | composite | expiring_items, stockout_risk, upcoming_deliveries / get_expiring, get_inventory_status, get_deliveries | 12.38 | 7.61 | Yes (an extra stockout read the reply did not use) |
| Dame las alertas y el plan de personal | composite | active_issues, staffing / get_issues, get_staffing | 9.30 | 3.46 | Yes |
| ¿Qué promociones tengo activas y qué productos me voy a quedar sin inventario? | composite | promo_list, stockout_risk / get_promos, get_inventory_status | 11.38 | 8.91 | Yes |

The same question gave a different Jev verdict on two runs (order_plan near 0.69-0.75 against the 0.7 threshold;
day_summary at about 0.21). The known risk is real: when day_summary is missed, the composite drops that part. The
orchestrator path does not drop it.

Other quality notes from `on`: the composite stockout reply ends in `）》`, and the composite active_issues reply has a
glued `lasuya` that the detector does not catch.

## Runner compare output: phase5d -> p12-shadow

### Stress battery compare: phase5d -> p12-shadow

| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |
|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | 8.28 | 16.57 | 8.29 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 | 5.23 | 8.26 | 3.03 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_active_issues | 0 | 6.26 | 13.34 | 7.08 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 | 12.4 | 14.46 | 2.06 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_stockout_risk | 0 | 5.21 | 6.34 | 1.13 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_expiring_items | 0 | 3.22 | 4.17 | 0.95 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_upcoming_deliveries | 0 | 5.17 | 10.26 | 5.09 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 | 3.19 | 14.34 | 11.15 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_promo_list | 0 | 3.22 | 11.32 | 8.1 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_data_integrity | 0 | 4.31 | 8.23 | 3.92 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_transfer_options | 0 | 14.45 | 33.37 | 18.92 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 | 7.26 | 12.36 | 5.1 | done -> done | 2 -> 3 | 0 -> 0 | - | - |
| specialist_supply | 0 | 14.46 | 11.36 | -3.1 | done -> done | 2 -> 2 | 0 -> 0 | garbled | - |
| specialist_strategist | 0 | 7.26 | 28.73 | 21.47 | done -> done | 4 -> 3 | 0 -> 0 | - | - |
| multi_specialist | 0 | 32.04 | 81 | 48.96 | done -> done | 8 -> 3 | 2 -> 2 | garbled | - |
| proposal | 0 | 7.22 | 18.41 | 11.19 | done -> done | 2 -> 2 | 0 -> 0 | garbled | - |
| unsupported | 0 | 11.38 | 5.15 | -6.23 | done -> done | 1 -> 0 | 0 -> 0 | - | - |
| follow_up | 0 | 5.2 | 9.49 | 4.29 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 | 6.27 | 17.41 | 11.14 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 2 | 5.22 | 15.44 | 10.22 | done -> done | 0 -> 0 | 0 -> 0 | - | - |
| burst | 0 | 4.54 | 5.7 | 1.16 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 1 | 9.62 | 5.69 | -3.93 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 | 6.65 | 6.77 | 0.12 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 | 3.53 | 5.72 | 2.19 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 4 | 5.59 | 8.82 | 3.23 | done -> done | 1 -> 1 | 0 -> 0 | - | - |

## Aggregates

| metric | before | after | delta |
|---|---|---|---|
| latency_p50_s | 6.26 | 11.32 | 5.06 |
| latency_p95_s | 14.46 | 33.37 | 18.91 |
| latency_max_s | 32.04 | 81 | 48.96 |
| first_text_p50_s | 3.08 | 5.1 | 2.02 |
| first_text_p95_s | 12.53 | 22.27 | 9.74 |
| failure_rate | 0 | 0 | 0 |
| tool_calls_total | 38 | 32 | -6 |
| peer_asks_total | 3 | 3 | 0 |
| garbled_fragments_total | - | 30 | - |
| garbled_turns | - | 3 | - |

- flags before: {}
- flags after: {"garbled": 3}
- burst before: {"turns": 5, "failed": 0, "latency_max_s": 9.62, "latency_p50_s": 5.59}
- burst after: {"turns": 5, "failed": 0, "latency_max_s": 8.82, "latency_p50_s": 5.72}



## Runner compare output: p12-shadow -> p12-on

### Stress battery compare: p12-shadow -> p12-on

| case | turn | before s | after s | delta s | status | tool calls | peer asks | new flags | fixed flags |
|---|---|---|---|---|---|---|---|---|---|
| simple | 0 | 16.57 | 16.57 | 0 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_day_summary | 0 | 8.26 | 21.68 | 13.42 | done -> done | 1 -> 3 | 0 -> 0 | - | - |
| intent_active_issues | 0 | 13.34 | 23.55 | 10.21 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_order_plan | 0 | 14.46 | 13.43 | -1.03 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_stockout_risk | 0 | 6.34 | 10.37 | 4.03 | done -> done | 1 -> 1 | 0 -> 0 | garbled | - |
| intent_expiring_items | 0 | 4.17 | 4.17 | 0 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_upcoming_deliveries | 0 | 10.26 | 6.23 | -4.03 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_staffing | 0 | 14.34 | 5.2 | -9.14 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_promo_list | 0 | 11.32 | 6.26 | -5.06 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_data_integrity | 0 | 8.23 | 5.2 | -3.03 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| intent_transfer_options | 0 | 33.37 | 30.98 | -2.39 | done -> done | 2 -> 2 | 1 -> 1 | - | - |
| specialist_past | 0 | 12.36 | 38.15 | 25.79 | done -> done | 3 -> 3 | 0 -> 2 | garbled | - |
| specialist_supply | 0 | 11.36 | 26.82 | 15.46 | done -> done | 2 -> 2 | 0 -> 0 | - | - |
| specialist_strategist | 0 | 28.73 | 15.39 | -13.34 | done -> done | 3 -> 4 | 0 -> 0 | - | - |
| multi_specialist | 0 | 81 | 91.74 | 10.74 | done -> done | 3 -> 7 | 2 -> 2 | - | - |
| proposal | 0 | 18.41 | 33.81 | 15.4 | done -> done | 2 -> 2 | 0 -> 0 | - | garbled |
| unsupported | 0 | 5.15 | 5.24 | 0.09 | done -> done | 0 -> 1 | 0 -> 0 | non_spanish | - |
| follow_up | 0 | 9.49 | 6.37 | -3.12 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| follow_up | 1 | 17.41 | 26.83 | 9.42 | done -> done | 1 -> 1 | 0 -> 0 | garbled | - |
| follow_up | 2 | 15.44 | 12.42 | -3.02 | done -> done | 0 -> 0 | 0 -> 0 | garbled | - |
| burst | 0 | 5.7 | 6.48 | 0.78 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 1 | 5.69 | 3.41 | -2.28 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 2 | 6.77 | 9.56 | 2.79 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 3 | 5.72 | 4.42 | -1.3 | done -> done | 1 -> 1 | 0 -> 0 | - | - |
| burst | 4 | 8.82 | 24.85 | 16.03 | done -> done | 1 -> 1 | 0 -> 0 | - | - |

## Aggregates

| metric | before | after | delta |
|---|---|---|---|
| latency_p50_s | 11.32 | 12.42 | 1.1 |
| latency_p95_s | 33.37 | 38.15 | 4.78 |
| latency_max_s | 81 | 91.74 | 10.74 |
| first_text_p50_s | 5.1 | 3.78 | -1.32 |
| first_text_p95_s | 22.27 | 34.08 | 11.81 |
| failure_rate | 0 | 0 | 0 |
| tool_calls_total | 32 | 40 | 8 |
| peer_asks_total | 3 | 5 | 2 |
| garbled_fragments_total | 30 | 6 | -24 |
| garbled_turns | 3 | 6 | 3 |

- flags before: {"garbled": 3}
- flags after: {"garbled": 6, "non_spanish": 1}
- burst before: {"turns": 5, "failed": 0, "latency_max_s": 8.82, "latency_p50_s": 5.72}
- burst after: {"turns": 5, "failed": 0, "latency_max_s": 24.85, "latency_p50_s": 6.48}


