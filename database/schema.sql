-- AgentFund Database Schema
-- Run this in Supabase SQL Editor (SQL Editor → New Query → Paste → Run)

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- USERS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT,

    -- Capital tracking
    total_capital DECIMAL(15, 2) DEFAULT 0,
    allocated_capital DECIMAL(15, 2) DEFAULT 0,

    -- Alpaca integration (encrypted)
    alpaca_api_key TEXT,
    alpaca_api_secret TEXT,
    alpaca_paper_mode BOOLEAN DEFAULT TRUE,

    -- Preferences
    timezone TEXT DEFAULT 'America/New_York',
    notification_email BOOLEAN DEFAULT TRUE,
    notification_daily_report BOOLEAN DEFAULT TRUE,
    notification_alerts BOOLEAN DEFAULT TRUE,
    report_delivery_time TIME DEFAULT '08:00:00',

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

-- ============================================================================
-- AGENTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Identity
    name TEXT NOT NULL,
    persona TEXT NOT NULL DEFAULT 'analytical',
    status TEXT NOT NULL DEFAULT 'active', -- active, paused, stopped, completed

    -- Strategy configuration
    strategy_type TEXT NOT NULL,
    strategy_params JSONB NOT NULL DEFAULT '{}',
    risk_params JSONB NOT NULL DEFAULT '{}',

    -- Capital allocation
    allocated_capital DECIMAL(15, 2) NOT NULL,
    cash_balance DECIMAL(15, 2) NOT NULL,

    -- Time horizon
    time_horizon_days INTEGER NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,

    -- Performance metrics (updated by engine)
    total_value DECIMAL(15, 2),
    total_return_pct DECIMAL(8, 4) DEFAULT 0,
    daily_return_pct DECIMAL(8, 4) DEFAULT 0,
    sharpe_ratio DECIMAL(8, 4),
    max_drawdown_pct DECIMAL(8, 4),
    win_rate_pct DECIMAL(8, 4),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agents_user_id ON agents(user_id);
CREATE INDEX idx_agents_status ON agents(status);

-- ============================================================================
-- POSITIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,

    -- Position details
    ticker TEXT NOT NULL,
    shares DECIMAL(15, 6) NOT NULL,
    entry_price DECIMAL(15, 4) NOT NULL,
    entry_date DATE NOT NULL,
    entry_rationale TEXT,

    -- Targets and stops
    target_price DECIMAL(15, 4),
    stop_loss_price DECIMAL(15, 4),

    -- Current state (updated by engine)
    current_price DECIMAL(15, 4),
    current_value DECIMAL(15, 2),
    unrealized_pnl DECIMAL(15, 2),
    unrealized_pnl_pct DECIMAL(8, 4),

    -- Status
    status TEXT NOT NULL DEFAULT 'open', -- open, closed

    -- Exit details (populated when closed)
    exit_price DECIMAL(15, 4),
    exit_date DATE,
    exit_rationale TEXT,
    realized_pnl DECIMAL(15, 2),
    realized_pnl_pct DECIMAL(8, 4),

    -- Alpaca order IDs
    entry_order_id TEXT,
    exit_order_id TEXT,
    stop_order_id TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_positions_agent_id ON positions(agent_id);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_ticker ON positions(ticker);

-- ============================================================================
-- AGENT ACTIVITY TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_activity (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,

    -- Activity details
    activity_type TEXT NOT NULL, -- buy, sell, stop_hit, target_hit, rebalance, paused, resumed, etc.
    ticker TEXT,
    details JSONB NOT NULL DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agent_activity_agent_id ON agent_activity(agent_id);
CREATE INDEX idx_agent_activity_type ON agent_activity(activity_type);
CREATE INDEX idx_agent_activity_created_at ON agent_activity(created_at DESC);

-- ============================================================================
-- AGENT REPORTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,

    -- Report content
    report_type TEXT NOT NULL DEFAULT 'daily', -- daily, weekly, monthly
    report_date DATE NOT NULL,
    content TEXT NOT NULL,

    -- Performance snapshot at time of report
    total_value DECIMAL(15, 2),
    daily_return_pct DECIMAL(8, 4),
    total_return_pct DECIMAL(8, 4),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agent_reports_agent_id ON agent_reports(agent_id);
CREATE INDEX idx_agent_reports_date ON agent_reports(report_date DESC);
CREATE UNIQUE INDEX idx_agent_reports_unique ON agent_reports(agent_id, report_type, report_date);

-- ============================================================================
-- CHAT HISTORY TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS chat_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,

    -- Message details
    role TEXT NOT NULL, -- user, assistant
    content TEXT NOT NULL,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chat_history_agent_id ON chat_history(agent_id);
CREATE INDEX idx_chat_history_created_at ON chat_history(created_at DESC);

-- ============================================================================
-- STOCKS TABLE (Market Data)
-- ============================================================================
CREATE TABLE IF NOT EXISTS stocks (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    sector TEXT,
    industry TEXT,

    -- Price data
    price DECIMAL(15, 4),
    change_percent DECIMAL(8, 4),
    market_cap BIGINT,

    -- Fundamentals
    pe_ratio DECIMAL(10, 4),
    pb_ratio DECIMAL(10, 4),
    eps DECIMAL(10, 4),
    beta DECIMAL(8, 4),
    dividend_yield DECIMAL(8, 6),

    -- Quality metrics
    roe DECIMAL(8, 4),
    profit_margin DECIMAL(8, 4),
    debt_to_equity DECIMAL(8, 4),

    -- Momentum metrics
    momentum_6m DECIMAL(8, 4),
    momentum_12m DECIMAL(8, 4),

    -- Dividend
    dividend_growth_5y DECIMAL(8, 4),

    -- Technical indicators
    ma_30 DECIMAL(15, 4),
    ma_100 DECIMAL(15, 4),
    ma_200 DECIMAL(15, 4),
    atr DECIMAL(15, 6),
    high_52w DECIMAL(15, 4),
    low_52w DECIMAL(15, 4),

    -- Volume
    avg_volume BIGINT,
    volume BIGINT,

    -- Factor scores (0-100)
    momentum_score DECIMAL(6, 2),
    value_score DECIMAL(6, 2),
    quality_score DECIMAL(6, 2),
    dividend_score DECIMAL(6, 2),
    volatility_score DECIMAL(6, 2),
    composite_score DECIMAL(6, 2),

    -- Sentiment scores (-100 to +100)
    news_sentiment DECIMAL(6, 2),
    social_sentiment DECIMAL(6, 2),
    combined_sentiment DECIMAL(6, 2),
    sentiment_velocity DECIMAL(6, 2),

    -- Timestamps
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    scores_updated_at TIMESTAMPTZ
);

CREATE INDEX idx_stocks_sector ON stocks(sector);
CREATE INDEX idx_stocks_market_cap ON stocks(market_cap DESC);
CREATE INDEX idx_stocks_momentum_score ON stocks(momentum_score DESC);
CREATE INDEX idx_stocks_value_score ON stocks(value_score DESC);
CREATE INDEX idx_stocks_quality_score ON stocks(quality_score DESC);
CREATE INDEX idx_stocks_composite_score ON stocks(composite_score DESC);

-- ============================================================================
-- PRICE HISTORY TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS price_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    date DATE NOT NULL,
    price DECIMAL(15, 4) NOT NULL,

    -- OHLCV (optional, for detailed history)
    open_price DECIMAL(15, 4),
    high_price DECIMAL(15, 4),
    low_price DECIMAL(15, 4),
    volume BIGINT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(symbol, date)
);

CREATE INDEX idx_price_history_symbol ON price_history(symbol);
CREATE INDEX idx_price_history_date ON price_history(date DESC);

-- ============================================================================
-- SENTIMENT HISTORY TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS sentiment_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,

    -- Sentiment scores
    news_sentiment DECIMAL(6, 2),
    social_sentiment DECIMAL(6, 2),
    combined_sentiment DECIMAL(6, 2),

    -- Source details
    news_count INTEGER DEFAULT 0,
    social_count INTEGER DEFAULT 0,

    -- Timestamps
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sentiment_history_symbol ON sentiment_history(symbol);
CREATE INDEX idx_sentiment_history_recorded_at ON sentiment_history(recorded_at DESC);

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================

-- Enable RLS on user-owned tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_activity ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_history ENABLE ROW LEVEL SECURITY;

-- Users can only see their own data
CREATE POLICY users_own_data ON users
    FOR ALL USING (id = auth.uid());

CREATE POLICY agents_own_data ON agents
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY positions_own_data ON positions
    FOR ALL USING (agent_id IN (SELECT id FROM agents WHERE user_id = auth.uid()));

CREATE POLICY activity_own_data ON agent_activity
    FOR ALL USING (agent_id IN (SELECT id FROM agents WHERE user_id = auth.uid()));

CREATE POLICY reports_own_data ON agent_reports
    FOR ALL USING (agent_id IN (SELECT id FROM agents WHERE user_id = auth.uid()));

CREATE POLICY chat_own_data ON chat_history
    FOR ALL USING (agent_id IN (SELECT id FROM agents WHERE user_id = auth.uid()));

-- Stocks and price history are public read
ALTER TABLE stocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE sentiment_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY stocks_public_read ON stocks FOR SELECT USING (true);
CREATE POLICY price_history_public_read ON price_history FOR SELECT USING (true);
CREATE POLICY sentiment_history_public_read ON sentiment_history FOR SELECT USING (true);

-- Service role can do anything (for backend operations)
CREATE POLICY service_role_all ON users FOR ALL TO service_role USING (true);
CREATE POLICY service_role_agents ON agents FOR ALL TO service_role USING (true);
CREATE POLICY service_role_positions ON positions FOR ALL TO service_role USING (true);
CREATE POLICY service_role_activity ON agent_activity FOR ALL TO service_role USING (true);
CREATE POLICY service_role_reports ON agent_reports FOR ALL TO service_role USING (true);
CREATE POLICY service_role_chat ON chat_history FOR ALL TO service_role USING (true);
CREATE POLICY service_role_stocks ON stocks FOR ALL TO service_role USING (true);
CREATE POLICY service_role_prices ON price_history FOR ALL TO service_role USING (true);
CREATE POLICY service_role_sentiment ON sentiment_history FOR ALL TO service_role USING (true);

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to tables
CREATE TRIGGER users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER agents_updated_at BEFORE UPDATE ON agents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER positions_updated_at BEFORE UPDATE ON positions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================================
-- INITIAL DATA (Optional test user)
-- ============================================================================

-- Uncomment to create a test user (password: test123)
-- INSERT INTO users (email, password_hash, name, total_capital)
-- VALUES (
--     'test@agentfund.ai',
--     '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYWWQEuWJKfG',
--     'Test User',
--     100000.00
-- );

SELECT 'Schema created successfully!' as status;
