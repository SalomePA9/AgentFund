-- Migration 003: Remove unused stock-level signal columns
--
-- accruals_quality_score and earnings_revision_score were added in
-- migration 002 but are never populated by any job. These signals are
-- computed on-the-fly by the strategy layer during execution and don't
-- need persistent storage on the stocks table.
--
-- The other stock-level columns (short_pct_float, short_interest_score,
-- insider_net_sentiment, insider_cluster_score) ARE populated by the
-- macro_data_job and should be retained.

ALTER TABLE stocks DROP COLUMN IF EXISTS accruals_quality_score;
ALTER TABLE stocks DROP COLUMN IF EXISTS earnings_revision_score;
