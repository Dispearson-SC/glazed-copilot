ALTER TABLE glazed.proposals ADD COLUMN IF NOT EXISTS idempotency_key text;
CREATE UNIQUE INDEX IF NOT EXISTS proposals_case_idempotency_key
    ON glazed.proposals (case_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
