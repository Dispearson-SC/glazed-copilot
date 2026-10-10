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
Headers: `X-Glazed-Case` (case id or core conversation id; unknown or missing is 400), `X-Glazed-Agent` (optional). The backend resolves `store_id` and `as_of` (= case `sim_today`) from the case. Reads: `GET /internal/v1/{kpis, day-summary, issues, inventory/projection, order-plan, suppliers/performance, promos/{id}/evaluation, history}`. Writes: `POST /internal/v1/proposals` (`{issue_id, option_id, rationale}`; action, params and tier are copied from the stored option, unknown option is 400), `POST /internal/v1/events`. All queries enforce `date <= as_of`.

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
