-- Migration 006: Add retention policy for macro_risk_overlay_state
--
-- The overlay state table is insert-only (one row per nightly computation).
-- Without cleanup it grows unboundedly.  This migration:
-- 1. Deletes rows older than 90 days (keeps ~3 months of audit history)
-- 2. Adds an index on computed_at to make date-range queries efficient
-- 3. Documents that the nightly job or a pg_cron task should run the
--    DELETE periodically (e.g. weekly).

-- Step 1: Purge old rows (idempotent — safe to re-run)
DELETE FROM macro_risk_overlay_state
WHERE computed_at < NOW() - INTERVAL '90 days';

-- Step 2: Index for efficient date-range queries and future cleanup
CREATE INDEX IF NOT EXISTS idx_overlay_state_computed_at
    ON macro_risk_overlay_state (computed_at);

-- Step 3: Optional — if pg_cron is available, schedule weekly cleanup.
-- Uncomment the lines below after enabling pg_cron on the database:
--
-- SELECT cron.schedule(
--     'overlay-state-retention',
--     '0 3 * * 0',   -- every Sunday at 03:00 UTC
--     $$DELETE FROM macro_risk_overlay_state WHERE computed_at < NOW() - INTERVAL '90 days'$$
-- );
