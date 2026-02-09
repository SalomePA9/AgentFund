-- Migration 005: Fix unique constraints for PostgREST upsert compatibility
--
-- PostgREST's on_conflict parameter only accepts column names, not
-- expression-based indexes like DATE(recorded_at).  Migrations 002 and 004
-- created expression-based unique indexes that PostgREST cannot target,
-- causing all upsert calls in macro_data_job.py to silently fail.
--
-- This migration:
--   1. Drops the expression-based indexes
--   2. Deduplicates existing rows (keeping the most recently recorded row)
--   3. Adds simple column-based unique constraints
--
-- The application upserts on indicator_name (macro_indicators) and symbol
-- (insider_signals, short_interest), keeping only the latest snapshot per
-- key.  Historical time-series are retained in the upstream sources (FRED,
-- SEC EDGAR, yfinance) and do not need to be stored row-per-day here.

-- -----------------------------------------------------------------------
-- 1. Drop expression-based indexes that PostgREST cannot target
-- -----------------------------------------------------------------------
DROP INDEX IF EXISTS idx_macro_indicators_unique;    -- from migration 002
DROP INDEX IF EXISTS uq_insider_signals_symbol_date; -- from migration 004
DROP INDEX IF EXISTS uq_short_interest_symbol_date;  -- from migration 004

-- -----------------------------------------------------------------------
-- 2. Deduplicate existing rows — keep the most recently recorded row
-- -----------------------------------------------------------------------

-- macro_indicators: keep latest recorded_at per indicator_name
DELETE FROM macro_indicators a USING macro_indicators b
WHERE a.indicator_name = b.indicator_name
  AND a.recorded_at < b.recorded_at;

-- Break recorded_at ties by created_at
DELETE FROM macro_indicators a USING macro_indicators b
WHERE a.indicator_name = b.indicator_name
  AND a.recorded_at = b.recorded_at
  AND a.created_at < b.created_at;

-- insider_signals: keep latest recorded_at per symbol
DELETE FROM insider_signals a USING insider_signals b
WHERE a.symbol = b.symbol
  AND a.recorded_at < b.recorded_at;

DELETE FROM insider_signals a USING insider_signals b
WHERE a.symbol = b.symbol
  AND a.recorded_at = b.recorded_at
  AND a.created_at < b.created_at;

-- short_interest: keep latest recorded_at per symbol
DELETE FROM short_interest a USING short_interest b
WHERE a.symbol = b.symbol
  AND a.recorded_at < b.recorded_at;

DELETE FROM short_interest a USING short_interest b
WHERE a.symbol = b.symbol
  AND a.recorded_at = b.recorded_at
  AND a.created_at < b.created_at;

-- -----------------------------------------------------------------------
-- 3. Add column-based unique constraints (PostgREST-compatible)
-- -----------------------------------------------------------------------
ALTER TABLE macro_indicators
    ADD CONSTRAINT uq_macro_indicators_name UNIQUE (indicator_name);

ALTER TABLE insider_signals
    ADD CONSTRAINT uq_insider_signals_symbol UNIQUE (symbol);

ALTER TABLE short_interest
    ADD CONSTRAINT uq_short_interest_symbol UNIQUE (symbol);
