ALTER TABLE glazed.cases ADD COLUMN IF NOT EXISTS archived boolean NOT NULL DEFAULT false;
ALTER TABLE glazed.decision_memories ADD COLUMN IF NOT EXISTS sim_date date;
