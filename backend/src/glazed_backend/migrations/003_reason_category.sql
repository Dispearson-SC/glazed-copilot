ALTER TABLE glazed.proposals ADD COLUMN IF NOT EXISTS reason_category text;
ALTER TABLE glazed.proposals ADD COLUMN IF NOT EXISTS reason_confidence double precision;
