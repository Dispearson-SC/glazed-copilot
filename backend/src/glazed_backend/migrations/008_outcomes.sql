CREATE TABLE IF NOT EXISTS glazed.outcomes (
    decision_id text PRIMARY KEY, case_id text NOT NULL, store_id text NOT NULL, measured_as_of date NOT NULL,
    complete boolean NOT NULL, payload jsonb NOT NULL, created_at timestamptz NOT NULL);
CREATE INDEX IF NOT EXISTS outcomes_case ON glazed.outcomes (case_id);
