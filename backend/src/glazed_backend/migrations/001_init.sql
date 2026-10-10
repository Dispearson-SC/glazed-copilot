CREATE SCHEMA IF NOT EXISTS glazed;

CREATE TABLE IF NOT EXISTS glazed.cases (
    case_id text PRIMARY KEY, store_id text NOT NULL, sim_today date NOT NULL, mode text NOT NULL,
    parent_case_id text, core_conversation_id text, title text NOT NULL, created_at timestamptz NOT NULL,
    issue_key text);
CREATE INDEX IF NOT EXISTS cases_store ON glazed.cases (store_id);
CREATE INDEX IF NOT EXISTS cases_issue ON glazed.cases (issue_key);
CREATE INDEX IF NOT EXISTS cases_conv ON glazed.cases (core_conversation_id);

CREATE TABLE IF NOT EXISTS glazed.alerts (
    alert_id text PRIMARY KEY, alert_type int NOT NULL, store_id text NOT NULL, case_id text NOT NULL,
    severity_usd double precision NOT NULL, state text NOT NULL, issue jsonb NOT NULL,
    issue_key text NOT NULL UNIQUE, as_of date NOT NULL, created_at timestamptz NOT NULL);
CREATE INDEX IF NOT EXISTS alerts_store ON glazed.alerts (store_id, state);

CREATE TABLE IF NOT EXISTS glazed.proposals (
    proposal_id text PRIMARY KEY, case_id text NOT NULL, store_id text NOT NULL, issue_id text NOT NULL,
    action_type text NOT NULL, params jsonb NOT NULL, tier text NOT NULL, rationale text NOT NULL,
    status text NOT NULL, reason text NOT NULL, agent_id text NOT NULL, created_at timestamptz NOT NULL);
CREATE INDEX IF NOT EXISTS proposals_case ON glazed.proposals (case_id);

CREATE TABLE IF NOT EXISTS glazed.executions (
    execution_id text PRIMARY KEY, proposal_id text NOT NULL, case_id text NOT NULL, source text NOT NULL,
    status text NOT NULL, detail text NOT NULL, executed_at timestamptz NOT NULL);
CREATE INDEX IF NOT EXISTS executions_case ON glazed.executions (case_id);

CREATE TABLE IF NOT EXISTS glazed.backtests (
    run_id text PRIMARY KEY, case_id text NOT NULL, store_id text NOT NULL, period_from date NOT NULL,
    period_to date NOT NULL, policy text NOT NULL, results jsonb NOT NULL, created_at timestamptz NOT NULL,
    label text NOT NULL);

CREATE TABLE IF NOT EXISTS glazed.trace_events (
    event_id text PRIMARY KEY, case_id text NOT NULL, store_id text NOT NULL, ts timestamptz NOT NULL,
    from_agent text NOT NULL, to_agent text NOT NULL, kind text NOT NULL, payload jsonb NOT NULL);
CREATE INDEX IF NOT EXISTS trace_case ON glazed.trace_events (case_id, ts);
CREATE INDEX IF NOT EXISTS trace_store ON glazed.trace_events (store_id, ts);
