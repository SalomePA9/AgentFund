-- Migration 004: Add unique constraints to prevent duplicate rows
--
-- insider_signals and short_interest tables use INSERT without unique
-- constraints, so duplicate rows accumulate on each job rerun.
-- Adding a unique constraint on (symbol, DATE(recorded_at)) allows
-- at most one record per symbol per day.

-- Deduplicate existing rows before adding constraints
DELETE FROM insider_signals a USING insider_signals b
WHERE a.id > b.id
  AND a.symbol = b.symbol
  AND DATE(a.recorded_at) = DATE(b.recorded_at);

DELETE FROM short_interest a USING short_interest b
WHERE a.id > b.id
  AND a.symbol = b.symbol
  AND DATE(a.recorded_at) = DATE(b.recorded_at);

-- Add unique indexes (used as ON CONFLICT targets)
CREATE UNIQUE INDEX IF NOT EXISTS uq_insider_signals_symbol_date
    ON insider_signals (symbol, (DATE(recorded_at)));

CREATE UNIQUE INDEX IF NOT EXISTS uq_short_interest_symbol_date
    ON short_interest (symbol, (DATE(recorded_at)));
