# Architecture (backend foundation)

## Hexagonal layout (`backend/src/glazed_backend`)
- `domain/`: Case, Proposal, Execution, Alert (state machine), BacktestRun, TraceEvent. No I/O.
- `application/`: use cases (StartCase, ForkCase, ListCases, AskAgent, GetDaySummary, AdvanceSimClock, ListAlerts, DecideProposal, RunBacktest, GetAgentTrace, SubmitProposal, RecordEvent).
- `ports/`: MetricsPort, CorePort, CaseRepository, AlertRepository, ProposalRepository, ExecutionRepository, BacktestRepository, TracePort, Clock.
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
Headers: `X-Glazed-Case` (case id or core conversation id; unknown or missing is 400), `X-Glazed-Agent` (optional). The backend resolves `store_id` and `as_of` (= case `sim_today`) from the case. Reads: `GET /internal/v1/{kpis, day-summary, issues, inventory/projection, order-plan, suppliers/performance, promos/{id}/evaluation, history}`. Writes: `POST /internal/v1/proposals`, `POST /internal/v1/events`. All queries enforce `date <= as_of`.

## Public API
Fixed contract (see the ODD feature document): `/api/v1/` health, stores, cases (create/list/get/fork), `cases/{id}/messages` + `cases/{id}/turns/{turn}` (status pending|done|failed|waiting_approval, reply), day-summary, advance (`{sim_today, new_alerts}`), alerts (list, PATCH state), proposals (list, `POST /decision`), backtests, trace (ordered by `ts`). Domain errors map to 400, not found 404, invalid alert transition 409, Agent-Core failure 502.
