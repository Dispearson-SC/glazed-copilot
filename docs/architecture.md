# Architecture (backend foundation)

## Hexagonal layout (`backend/src/glazed_backend`)
- `domain/`: Case, Proposal, Execution, Alert (state machine), BacktestRun, TraceEvent. No I/O.
- `application/`: use cases (StartCase, ForkCase, ListCases, AskAgent, GetDaySummary, AdvanceSimClock, ListAlerts, DecideProposal, RunBacktest, GetAgentTrace, SubmitProposal, RecordEvent).
- `ports/`: MetricsPort, CorePort, CaseRepository, AlertRepository, ProposalRepository, ExecutionRepository, BacktestRepository, TracePort, Clock.
- `metrics/` (glazed_metrics): pure package, no I/O, used by DuckDBMetrics behind MetricsPort. Details below.
- `adapters/driven/`: DuckDBMetrics, Postgres repositories (+ SQL migrations in `migrations/`), AgentCoreHttp, in-memory repositories.
- `adapters/driving/`: public API `/api/v1/*`, internal API `/internal/v1/*`, composition root (`app.py`).

Rule: every number comes from `MetricsPort`. The backend never asks an LLM for a number; the LLM only explains.

## Cases and sessions
A case = `{case_id, store_id, sim_today, mode live|sandbox|backtest, parent_case_id, core_conversation_id, title}`.
- Same case, same Agent-Core conversation: history is kept by the Core.
- New case, new conversation, isolated proposals/executions/backtests (all tagged `case_id`).
- Fork copies store, sim_today and decisions to a child case.
- Each alert opens its own case, idempotently per issue key.

## Backend to Agent-Core
`AgentCoreHttp` implements `CorePort` over the Core REST API:
- `POST /turns` body `{session_id, profile_id, text}` with headers `X-Subject-Id`, `X-Tenant-Id`, `X-Channel`, `X-Roles`; returns 202 `{turn_id}` + `Location`.
- `GET /turns/{id}` returns `{turn_id, status: running|waiting|finished, text}`.
- `GET /admin/conversations/{session_id}` (role `admin`) returns transcript `entries`.
Mapping: tenant = `store_id`; Core `session_id` = `core_conversation_id` = `case_id` (so a tool that knows its session id can send it as `X-Glazed-Case`). Agents never receive store or date as parameters.

## Internal API (agent tools to backend)
Headers: `X-Glazed-Case` (case id or core conversation id; unknown or missing is 400), `X-Glazed-Agent` (optional). The backend resolves `store_id` and `as_of` (= case `sim_today`) from the case. Reads: `GET /internal/v1/{kpis, day-summary, issues, inventory/projection, order-plan, suppliers/performance, promos/{id}/evaluation, history, compliance, experiences}` (`issues` returns operational issues by default; `kind=` filters by kind, `category=integrity` returns integrity issues only, `category=all` returns both ranked by `severity_usd` / `exposure_usd`). Other: `POST /internal/v1/promos/audit`, `POST /internal/v1/classify` (no case needed). Writes: `POST /internal/v1/proposals` (`{issue_id, option_id, rationale}`; action, params and tier are copied from the stored option, unknown option is 400), `POST /internal/v1/events`. All queries enforce `date <= as_of`.

## Public API
Fixed contract (see the ODD feature document): `/api/v1/` health, stores, cases (create/list/get/fork), `cases/{id}/messages` + `cases/{id}/turns/{turn}` (status pending|done|failed|waiting_approval, reply), day-summary, advance (`{sim_today, new_alerts}`), alerts (list, PATCH state), proposals (list, `POST /decision`), backtests, trace (ordered by `ts`), plus `GET cases/{id}/order-plan`, `GET cases/{id}/kpis` and `POST /proposals` (`{case_id, issue_id, option_id, rationale}`). Domain errors map to 400, not found 404, invalid alert transition 409, Agent-Core failure 502.

## glazed_metrics (`backend/src/glazed_backend/metrics/`)
Pure functions over rows (dataclasses in `types.py`). `DuckDBMetrics` loads one `StoreSnapshot` per (store, as_of) (history, POs, suppliers, calendar), all cut at `as_of`: received dates after `as_of` are unknown, in-transit orders arrive on their `expected_date`, never on the real receipt date. Only backtest outcome scoring reads past the decision day (never past `as_of`).

| Module | Method |
|---|---|
| `service_level` | CR = Cu/(Cu+Co), Cu = price - cost, Co = cost (salvage 0). Clamped to 0.05-0.99. Sensitivity 0.60 / 0.74 / 0.85 exposed on every plan line. |
| `demand` | Censored demand: on days with stockout_hours > 0, demand = sold / (1 - hours/open_hours), capped at the p90 of uncensored same-weekday days. Weekday mean/sd over 56 days (pooled 28 days if < 3 samples); sd floor = half the Poisson sd. |
| `policy` | Shelf life <= 1: newsvendor quantile of next-day demand. 2-14 days: order-up-to = CR quantile of demand until the next delivery (supplier `delivery_days`, capped by shelf life) minus usable stock minus in-transit. Non-perishable: (s,S), service max(CR, 0.95), lead time nearly deterministic with a +1 day shift at p_late = 1 - on_time_rate. Demand over a horizon is Normal (means and variances add). Case rounding picks floor or ceil by expected overage/underage cost. |
| `inventory` | Usable stock: closing stock assigned FIFO to the newest receipts, sold oldest-first at expected demand; units whose lot expires first are not usable. |
| `plan` | Plan line: projected stockout date, order deadline (latest order day whose delivery with lead p90 lands by the stockout), stockout risk with/without order (late delivery mixture), expected waste and lost sales {low,mid,high} (demand at P25/P50/P75), received-to-sold and qty delta vs the typical historical order, min order value as a warning only (quantity is never inflated). |
| `losses` | lost_sales_usd {low, mid, high} = stockout_hours x uncensored same-weekday units per open hour x price; low = partial-day stockouts only; high uses the P75 rate. |
| `options` / `issues` | Issues stockout_risk, overstock_waste, expiring, late_delivery with at most 4 options plus `do_nothing` from the closed action list. `option_id` = sha256(issue_id, action_type, params)[:12]. Net, cost and loss impact come from the same loss model. `do_nothing` carries the cost of inaction. |
| `replay`, `confidence` | Confidence = share of replays (28 days before as_of, decision at t, outcome in t+1..t+3 <= as_of) with net > 0, per kind x action_type, with n_backtest. Effect under the noise floor ($1) caps the score at 0.3. |
| `tiers` | N0 / N1 / N2 / N3 computed in code with `tier_reasons` (see below). |
| `backtest` | Per SKU and day: policy supply = service-level quantile of that day's demand using data up to (day - lead time), vs the day's actual supply. |

Tiers: N0 when do_nothing wins (net <= 0) or net is under the noise floor. N1 only if score >= 0.85, n_backtest >= 30, net > 0, cost <= store threshold (`Config.store_threshold_usd`, default $150), action in {place_order, adjust_order_qty} within +-15% of the plan (minimum one case) and a clear margin over the second option. N3 for transfer_stock, shift_staff_hours, large promos, or options whose net differs by under 10%. Otherwise N2. `markdown_end_of_day` is capped at N2 and carries `data_caveat: "assumed elasticity"`.

Known limits (stated, not hidden):
- Normal approximation of demand over a horizon; small samples (8 same-weekday days).
- FIFO lot ages are inferred from received_qty; no lot-level data.
- Confidence is a raw replay share, not isotonic-calibrated. `markdown_end_of_day`, `run_promo`, `transfer_stock`, `shift_staff_hours` and `late_delivery` options are uncalibrated (n_backtest 0, score 0.3). `transfer_stock`, `run_promo` and `shift_staff_hours` are classified by the tier rules but not generated yet.
- Replays use a 3-day outcome window and the rule, not the manager's actual decision; the data is synthetic and does not respond to our decisions.
- Late-order arrival is modelled as 1/2/3 days from today. Store closures are known only up to as_of. Delivery cadence for "Weekly" suppliers comes from their 7-day lead time.
- The backtest assumes supply hits the target exactly (no case rounding, no minimum order value); it is labelled `backtest` and is an estimate, not a guarantee.
- Served issues are remembered in memory per (case, issue); after a restart the option is found in the alert's stored issue or recomputed deterministically at the case date.


## Wave 6 detectors, Sentinel and Jev

### More detectors (all produce Wave 5 issues with deterministic options)
| Kind (alert) | Rule | Options |
|---|---|---|
| `inflated_order` (5) | max(plan qty, typical order) minus the unrounded optimum >= half a case AND the SKU's waste rate at the store (expired / received, 56 days) > 25%. Any store, not only kiosks. | `adjust_order_qty` to the optimum (or `skip_order` when the optimum is 0), `adjust_order_qty` with `pattern: alternate_days` (only for shelf life >= 2; values per day over the 2-day cycle), `do_nothing` (cost = expected waste). Uncalibrated, so tier N2. |
| `misleading_promo` (7) | A promotion running or starting within 7 days is audited with `metrics/promo_audit.py`: block when the mean uplift of similar finished promos (same department, discount within 5 points) is under the noise floor OR their margin effect is negative. | `do_nothing` (block; always recommended, never published silently) and `run_promo` with the best earlier promo (`promo_ref`). |
| `calendar_uplift` (19) | School break or holiday within sim_today+7 whose effect (daily units on event days vs ordinary days) is >= 5% in a store x department; skipped when the last 14 days already carry the event. Effect per cell uses n event days; below 20 it is blended `n/20` store + rest format x department and says so in `data_caveats`. | `adjust_order_qty` with `params.effects[]` per department, `do_nothing` (cost = expected lost sales). Assumes 70% of the extra units sell (40-100% range). |
| `sku_key_mismatch`, `orphan_sku` (9) | On the raw layer (`GLAZED_RAW_PATH`, mounted at `/raw`): raw sales SKUs missing from the raw master. Normalising the key (upper-case, no dash/space) that matches the master is a mismatch (SKU-100040 -> SKU100040, ~$407k); no match is a real orphan (SKU-7xxxxx, 400 rows, ~$19k). Cut at as_of. Mismatches under $10k are summarised in one evidence line. Without the raw layer only the dq_log row count (SD03) is reported. | `data_fix_task` (tier N2, never automatic) and `do_nothing`. Marked `category: integrity`, `integrity: true`; `severity_usd` is 0 (sales exposure is in `exposure_usd`) so they do not crowd out operational alerts. |

Promo audit source: the Datos baseline (`Dataset/analisis_estado.md` section 3, chain-wide DiD uplift and margin effect with an assumed cost) joined to the `promotions` table, embedded in `metrics/promo_audit.py`. PR013 never ran, so its drift is the placebo (noise floor +-10 points). Chain-wide margin effects are split evenly over the stores for the per-store figure (stated in the issue). Only promos finished by as_of count (no look-ahead). `POST /internal/v1/promos/audit {department, discount_pct}` returns `{verdict: block|allow|insufficient_evidence, recommendation, similar[], alternative, reasons[], noise_floor_pct}`; each similar promo also carries this store's naive pre/post `store_evaluation`.

### History with decisions
`GET /internal/v1/history` adds `decision_log`: this case's proposals (`scope: case`) and, for a live case, earlier live decisions of the same store (`scope: store`; sandbox/backtest cases never leak and decisions dated after the case clock are hidden). Each entry has status, reason, rationale, executions (status, source) and `outcome` (observed vs simulated, label `backtest`) once the horizon passed. `GET /internal/v1/experiences` returns `ref` (a promo id for seeded baselines) and `verify` (`evaluate_promo` for refs, `history` for decision ids) so the Past agent re-checks a memory before citing a number.

### Minimal Sentinel (`application/sentinel.py`, `metrics/sentinel.py`)
- A proposal records `decision_as_of` and `expected {net_usd_low, mid, high, cost_usd}` in `params` (copied from the option by the backend).
- Compliance per approved decision: `execution_status` executed / not_executed / partial from the executions table (operational > demo_injected > simulated, latest wins; no record = not_executed). After `decision_as_of + 3 days` the observed outcome (judged against the simulated range widened by max($1, 25% of the mid)) is measured by `MetricsPort.observed_outcome` (replay of the calibration rule, label `backtest`; only order-quantity actions are measurable) and diagnosed: `not_executed` | `within_range` | `external_event` (a registered event overlaps the horizon) | `forecast_error`. The supplier-deviation branch of section 15.3 is not implemented.
- `GET /internal/v1/compliance[?decision_id=]` and `GET /api/v1/cases/{id}/compliance`.
- `POST /api/v1/cases/{id}/inject` `{execution: {proposal_id, status: not_executed|partial, detail?}}` (source `demo_injected`) or `{event: {type: bloqueo|clima_extremo|evento_local|cierre|falla_proveedor|otro, date_from, date_to?, note?}}` (stored as a trace event with `source: demo_injected`).
- `advance` also runs the check over the store's approved decisions (same mode); a non-executed or deviating one raises an alert of `kind: compliance_deviation`, `alert_type: 21`, issue id `<store>|compliance|<decision_id>`, once.

### Jev classification (`ports/classifier.py`, `adapters/driven/classifiers.py`)
`POST /internal/v1/classify {kind: rejection_reason | deviation_cause, text}` -> `{label, confidence, model, calibrated, adapter}` (+ `warning` when an earlier adapter failed). Chain: `BackboardSystemOne` (Backboard `llm_provider="typesafe"`, `model_name="jev-1.13.0"`, a `choice` System One question over the label set; calibrated true) then `LLMFallback` (MiniMax, OpenAI-compatible chat completions, strict JSON, calibrated false; `MINIMAX_API_KEY`, optional `MINIMAX_API_BASE`, `MINIMAX_CLASSIFIER_MODEL`); `KeywordClassifier` is the test fake. Labels outside the set or confidence under 0.4 become the escape label (`needs_review` / `no_match`); with no adapter configured every answer is the escape label. Jev's confidence only measures text-to-label fit; it is not the statistical confidence of a recommendation and not a safety barrier. `DecideProposal` classifies a rejection reason and stores `reason_category` / `reason_confidence` on the proposal (migration 003) and `Reason category: ... (confidence ...)` in the Backboard memory text; a classifier failure never blocks the decision.

Action types gained `data_fix_task`. Known limits: the calendar effect is not isolated from season or weather; alternate-days and calendar values are model assumptions; the promo baseline is a fixed reference, not recomputed by the backend.

Turn polling: `GET /api/v1/cases/{id}/turns/{turn}` stays `pending` with `still_running: true` once `GLAZED_TURN_TIMEOUT_S` (default 600) passes while Agent-Core still reports the turn running/waiting/started; `failed` only on a Core failure or an unknown Core status. Finished replies are sanitized of stray non-Latin tokens (CJK, Cyrillic, Arabic...); when something was removed the payload carries `sanitized: true` and `sanitized_fragments`.
