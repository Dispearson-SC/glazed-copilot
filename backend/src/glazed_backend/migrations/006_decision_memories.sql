CREATE TABLE IF NOT EXISTS glazed.decision_memories (
    memory_id text PRIMARY KEY, store_id text NOT NULL, case_id text NOT NULL, decision_id text NOT NULL,
    category text NOT NULL, text text NOT NULL, reason_category text, action_type text, sku text,
    created_at timestamptz NOT NULL, reason text NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS decision_memories_store ON glazed.decision_memories (store_id, created_at);
