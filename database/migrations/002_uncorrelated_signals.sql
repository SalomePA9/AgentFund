-- ============================================================================
-- Migration 002: Uncorrelated Signals Tables
--
-- Adds tables to store macro indicators, insider transactions, short interest,
-- and the macro risk overlay state used by the cross-agent risk coordinator.
-- ============================================================================

-- ============================================================================
-- MACRO INDICATORS TABLE
-- Stores time series of macro data from FRED, VIX, etc.
-- ============================================================================
CREATE TABLE IF NOT EXISTS macro_indicators (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Indicator identity
    indicator_name TEXT NOT NULL,   -- 'credit_spread', 'yield_curve', 'vix', etc.
    source TEXT NOT NULL,           -- 'fred', 'yahoo_finance', etc.

    -- Values
    value DECIMAL(15, 6) NOT NULL,
    z_score DECIMAL(8, 4),
    percentile DECIMAL(6, 2),
    rate_of_change DECIMAL(8, 4),

    -- Metadata (source-specific details)
    metadata JSONB NOT NULL DEFAULT '{}',

    -- Timestamps
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_macro_indicators_name ON macro_indicators(indicator_name);
CREATE INDEX idx_macro_indicators_recorded ON macro_indicators(recorded_at DESC);
CREATE UNIQUE INDEX idx_macro_indicators_unique
    ON macro_indicators(indicator_name, DATE(recorded_at));

-- ============================================================================
-- INSIDER TRANSACTIONS TABLE
-- Stores aggregated insider activity per symbol per period
-- ============================================================================
CREATE TABLE IF NOT EXISTS insider_signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    symbol TEXT NOT NULL,

    -- Insider metrics
    buy_count INTEGER DEFAULT 0,
    sell_count INTEGER DEFAULT 0,
    filing_count INTEGER DEFAULT 0,
    buy_ratio DECIMAL(6, 4),
    cluster_score DECIMAL(6, 2),        -- 0-100 cluster strength
    net_sentiment DECIMAL(6, 2),        -- -100 to +100

    -- Lookback period used
    lookback_days INTEGER DEFAULT 90,

    -- Timestamps
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_insider_signals_symbol ON insider_signals(symbol);
CREATE INDEX idx_insider_signals_recorded ON insider_signals(recorded_at DESC);

-- ============================================================================
-- SHORT INTEREST TABLE
-- Stores short interest snapshots per symbol
-- ============================================================================
CREATE TABLE IF NOT EXISTS short_interest (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    symbol TEXT NOT NULL,

    -- Short interest metrics
    short_pct_float DECIMAL(8, 4),          -- % of float sold short
    shares_short BIGINT,
    short_ratio DECIMAL(8, 4),              -- days to cover
    short_interest_score DECIMAL(6, 2),     -- -100 to +100

    -- Timestamps
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_short_interest_symbol ON short_interest(symbol);
CREATE INDEX idx_short_interest_recorded ON short_interest(recorded_at DESC);

-- ============================================================================
-- MACRO RISK OVERLAY STATE TABLE
-- Stores the output of each overlay computation for audit/analysis
-- ============================================================================
CREATE TABLE IF NOT EXISTS macro_risk_overlay_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Overlay output
    risk_scale_factor DECIMAL(6, 4) NOT NULL,
    composite_risk_score DECIMAL(6, 2) NOT NULL,
    regime_label TEXT NOT NULL,

    -- Individual signal values
    credit_spread_signal DECIMAL(6, 2),
    vol_regime_signal DECIMAL(6, 2),
    yield_curve_signal DECIMAL(6, 2),
    seasonality_signal DECIMAL(6, 2),
    insider_breadth_signal DECIMAL(6, 2),

    -- Warnings
    warnings JSONB DEFAULT '[]',

    -- Timestamps
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_overlay_state_computed ON macro_risk_overlay_state(computed_at DESC);

-- ============================================================================
-- Add uncorrelated signal columns to stocks table
-- ============================================================================
ALTER TABLE stocks ADD COLUMN IF NOT EXISTS short_pct_float DECIMAL(8, 4);
ALTER TABLE stocks ADD COLUMN IF NOT EXISTS short_interest_score DECIMAL(6, 2);
ALTER TABLE stocks ADD COLUMN IF NOT EXISTS insider_net_sentiment DECIMAL(6, 2);
ALTER TABLE stocks ADD COLUMN IF NOT EXISTS insider_cluster_score DECIMAL(6, 2);
ALTER TABLE stocks ADD COLUMN IF NOT EXISTS accruals_quality_score DECIMAL(6, 2);
ALTER TABLE stocks ADD COLUMN IF NOT EXISTS earnings_revision_score DECIMAL(6, 2);

-- Indexes for the new stock-level signals
CREATE INDEX IF NOT EXISTS idx_stocks_short_interest ON stocks(short_interest_score DESC);
CREATE INDEX IF NOT EXISTS idx_stocks_insider_sentiment ON stocks(insider_net_sentiment DESC);

-- ============================================================================
-- RLS policies for new tables (public read, service write)
-- ============================================================================
ALTER TABLE macro_indicators ENABLE ROW LEVEL SECURITY;
ALTER TABLE insider_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE short_interest ENABLE ROW LEVEL SECURITY;
ALTER TABLE macro_risk_overlay_state ENABLE ROW LEVEL SECURITY;

CREATE POLICY macro_indicators_public_read ON macro_indicators FOR SELECT USING (true);
CREATE POLICY insider_signals_public_read ON insider_signals FOR SELECT USING (true);
CREATE POLICY short_interest_public_read ON short_interest FOR SELECT USING (true);
CREATE POLICY overlay_state_public_read ON macro_risk_overlay_state FOR SELECT USING (true);

CREATE POLICY service_role_macro ON macro_indicators FOR ALL TO service_role USING (true);
CREATE POLICY service_role_insider ON insider_signals FOR ALL TO service_role USING (true);
CREATE POLICY service_role_short ON short_interest FOR ALL TO service_role USING (true);
CREATE POLICY service_role_overlay ON macro_risk_overlay_state FOR ALL TO service_role USING (true);

SELECT 'Migration 002: Uncorrelated signals tables created successfully!' as status;
