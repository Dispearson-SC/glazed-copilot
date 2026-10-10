CREATE TABLE IF NOT EXISTS glazed.users (
    user_id text PRIMARY KEY, email text NOT NULL UNIQUE, name text NOT NULL,
    role text NOT NULL CHECK (role IN ('admin', 'manager')), store_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    password_hash text NOT NULL, active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL);
ALTER TABLE glazed.proposals ADD COLUMN IF NOT EXISTS decided_by text;
