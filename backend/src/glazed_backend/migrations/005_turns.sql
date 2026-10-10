CREATE TABLE IF NOT EXISTS glazed.turns (
    turn_id text PRIMARY KEY, case_id text NOT NULL, store_id text NOT NULL, ts timestamptz NOT NULL,
    user_text text NOT NULL, status text NOT NULL, reply text, error text, reply_meta jsonb);
CREATE INDEX IF NOT EXISTS turns_case_ts ON glazed.turns (case_id, ts);
