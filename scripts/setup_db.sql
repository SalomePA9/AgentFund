-- ============================================
-- AgentFund Database Schema
-- PostgreSQL / Supabase
-- ============================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- USERS
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT,

    -- Capital management
    total_capital DECIMAL(15,2) DEFAULT 0,
    allocated_capital DECIMAL(15,2) DEFAULT 0,

    -- Settings (stored as JSONB)
    settings JSONB DEFAULT '{
        "timezone": "America/New_York",
        "report_time": "07:00",
        "email_reports": true,
        "email_alerts": true
    }'::jsonb,

    -- Broker connection (encrypted)
    alpaca_api_key TEXT,
    alpaca_api_secret TEXT,
    alpaca_paper_mode BOOLEAN DEFAULT true,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- AGENTS
-- ============================================
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Identity
    name TEXT NOT NULL,
    persona TEXT NOT NULL DEFAULT 'analytical'
        CHECK (persona IN ('analytical', 'aggressive', 'conservative', 'teacher', 'concise')),

    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused', 'stopped', 'completed')),

    -- Strategy Configuration
    strategy_type TEXT NOT NULL
        CHECK (strategy_type IN ('momentum', 'quality_value', 'quality_momentum', 'dividend_growth', 'custom')),

    strategy_params JSONB NOT NULL DEFAULT '{
        "momentum_lookback_days": 180,
        "min_market_cap": 1000000000,
        "sectors": "all",
        "exclude_tickers": [],
        "max_positions": 10,
        "sentiment_weight": 0.3,
        "rebalance_frequency": "weekly"
    }'::jsonb,

    -- Risk Configuration
    risk_params JSONB NOT NULL DEFAULT '{
        "stop_loss_type": "ma_200",
        "stop_loss_percentage": 0.10,
        "max_position_size_pct": 0.15,
        "min_risk_reward_ratio": 2.0,
        "max_sector_concentration": 0.50
    }'::jsonb,

    -- Capital Allocation
    allocated_capital DECIMAL(15,2) NOT NULL,
    cash_balance DECIMAL(15,2) NOT NULL,

    -- Time Horizon
    time_horizon_days INTEGER NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,

    -- Performance Cache (updated daily)
    total_value DECIMAL(15,2),
    total_return_pct DECIMAL(8,4),
    daily_return_pct DECIMAL(8,4),
    sharpe_ratio DECIMAL(8,4),
    max_drawdown_pct DECIMAL(8,4),
    win_rate_pct DECIMAL(8,4),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agents_user_id ON agents(user_id);
CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_agents_strategy_type ON agents(strategy_type);

CREATE TRIGGER update_agents_updated_at
    BEFORE UPDATE ON agents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- POSITIONS
-- ============================================
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,

    ticker TEXT NOT NULL,

    -- Entry
    entry_price DECIMAL(12,4) NOT NULL,
    entry_date DATE NOT NULL,
    shares DECIMAL(12,6) NOT NULL,
    entry_rationale TEXT,

    -- Targets
    target_price DECIMAL(12,4),
    stop_loss_price DECIMAL(12,4),

    -- Current State (updated daily)
    current_price DECIMAL(12,4),
    current_value DECIMAL(15,2),
    unrealized_pnl DECIMAL(15,2),
    unrealized_pnl_pct DECIMAL(8,4),

    -- Status
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'closed_target', 'closed_stop', 'closed_manual', 'closed_horizon')),

    -- Exit (populated when closed)
    exit_price DECIMAL(12,4),
    exit_date DATE,
    exit_rationale TEXT,
    realized_pnl DECIMAL(15,2),
    realized_pnl_pct DECIMAL(8,4),

    -- Alpaca order tracking
    entry_order_id TEXT,
    exit_order_id TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_positions_agent_id ON positions(agent_id);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_ticker ON positions(ticker);

CREATE TRIGGER update_positions_updated_at
    BEFORE UPDATE ON positions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- AGENT ACTIVITY LOG
-- ============================================
CREATE TABLE IF NOT EXISTS agent_activity (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,

    activity_type TEXT NOT NULL
        CHECK (activity_type IN (
            'buy', 'sell', 'stop_hit', 'target_hit', 'rebalance', 'alert',
            'strategy_change', 'capital_change', 'paused', 'resumed'
        )),

    ticker TEXT,

    details JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_activity_agent_id ON agent_activity(agent_id);
CREATE INDEX idx_activity_created_at ON agent_activity(created_at DESC);
CREATE INDEX idx_activity_type ON agent_activity(activity_type);

-- ============================================
-- DAILY REPORTS
-- ============================================
CREATE TABLE IF NOT EXISTS daily_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,

    report_date DATE NOT NULL,
    report_content TEXT NOT NULL,

    -- Snapshot at time of report
    performance_snapshot JSONB NOT NULL,
    positions_snapshot JSONB NOT NULL,
    actions_taken JSONB DEFAULT '[]'::jsonb,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(agent_id, report_date)
);

CREATE INDEX idx_reports_agent_date ON daily_reports(agent_id, report_date DESC);

-- ============================================
-- AGENT CHAT HISTORY
-- ============================================
CREATE TABLE IF NOT EXISTS agent_chats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,

    role TEXT NOT NULL CHECK (role IN ('user', 'agent')),
    message TEXT NOT NULL,

    -- Optional context used for response
    context_used JSONB,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chats_agent_id ON agent_chats(agent_id);
CREATE INDEX idx_chats_created_at ON agent_chats(created_at DESC);

-- ============================================
-- MARKET DATA CACHE (STOCKS)
-- ============================================
CREATE TABLE IF NOT EXISTS stocks (
    ticker TEXT PRIMARY KEY,
    name TEXT,
    sector TEXT,
    industry TEXT,
    market_cap BIGINT,

    -- Prices
    price DECIMAL(12,4),
    price_change_1d DECIMAL(8,4),
    price_change_1w DECIMAL(8,4),
    price_change_1m DECIMAL(8,4),
    ma_30 DECIMAL(12,4),
    ma_100 DECIMAL(12,4),
    ma_200 DECIMAL(12,4),
    atr DECIMAL(12,4),

    -- Factor Scores (0-100 percentile)
    momentum_score DECIMAL(5,2),
    value_score DECIMAL(5,2),
    quality_score DECIMAL(5,2),
    composite_score DECIMAL(5,2),

    -- Fundamentals
    pe_ratio DECIMAL(10,2),
    pb_ratio DECIMAL(10,2),
    roe DECIMAL(8,4),
    profit_margin DECIMAL(8,4),
    debt_to_equity DECIMAL(10,2),
    dividend_yield DECIMAL(8,4),
    payout_ratio DECIMAL(8,4),

    -- Sentiment
    news_sentiment DECIMAL(6,2),
    social_sentiment DECIMAL(6,2),
    sentiment_velocity DECIMAL(6,2),
    combined_sentiment DECIMAL(6,2),

    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_stocks_sector ON stocks(sector);
CREATE INDEX idx_stocks_market_cap ON stocks(market_cap DESC);
CREATE INDEX idx_stocks_momentum ON stocks(momentum_score DESC);
CREATE INDEX idx_stocks_value ON stocks(value_score DESC);
CREATE INDEX idx_stocks_quality ON stocks(quality_score DESC);
CREATE INDEX idx_stocks_composite ON stocks(composite_score DESC);

-- ============================================
-- SENTIMENT HISTORY (for trending)
-- ============================================
CREATE TABLE IF NOT EXISTS sentiment_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker TEXT NOT NULL,

    source TEXT NOT NULL CHECK (source IN ('news', 'stocktwits', 'reddit', 'combined')),
    score DECIMAL(6,2),
    mention_count INTEGER,

    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sentiment_ticker_date ON sentiment_history(ticker, recorded_at DESC);

-- ============================================
-- PRICE HISTORY (for charts/backtesting)
-- ============================================
CREATE TABLE IF NOT EXISTS price_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    open DECIMAL(12,4),
    high DECIMAL(12,4),
    low DECIMAL(12,4),
    close DECIMAL(12,4),
    volume BIGINT,
    adjusted_close DECIMAL(12,4),

    UNIQUE(ticker, date)
);

CREATE INDEX idx_price_history_ticker_date ON price_history(ticker, date DESC);

-- ============================================
-- USER WATCHLISTS (optional feature)
-- ============================================
CREATE TABLE IF NOT EXISTS watchlists (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    name TEXT NOT NULL,
    tickers TEXT[] NOT NULL DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_watchlists_user_id ON watchlists(user_id);

CREATE TRIGGER update_watchlists_updated_at
    BEFORE UPDATE ON watchlists
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_activity ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_chats ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlists ENABLE ROW LEVEL SECURITY;

-- Users can only see their own data
CREATE POLICY "Users can view own profile"
    ON users FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
    ON users FOR UPDATE
    USING (auth.uid() = id);

-- Agents policies
CREATE POLICY "Users can view own agents"
    ON agents FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "Users can create own agents"
    ON agents FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update own agents"
    ON agents FOR UPDATE
    USING (user_id = auth.uid());

CREATE POLICY "Users can delete own agents"
    ON agents FOR DELETE
    USING (user_id = auth.uid());

-- Positions policies (through agent ownership)
CREATE POLICY "Users can view positions of own agents"
    ON positions FOR SELECT
    USING (agent_id IN (SELECT id FROM agents WHERE user_id = auth.uid()));

CREATE POLICY "Users can manage positions of own agents"
    ON positions FOR ALL
    USING (agent_id IN (SELECT id FROM agents WHERE user_id = auth.uid()));

-- Activity policies
CREATE POLICY "Users can view activity of own agents"
    ON agent_activity FOR SELECT
    USING (agent_id IN (SELECT id FROM agents WHERE user_id = auth.uid()));

-- Reports policies
CREATE POLICY "Users can view reports of own agents"
    ON daily_reports FOR SELECT
    USING (agent_id IN (SELECT id FROM agents WHERE user_id = auth.uid()));

-- Chat policies
CREATE POLICY "Users can manage chats of own agents"
    ON agent_chats FOR ALL
    USING (agent_id IN (SELECT id FROM agents WHERE user_id = auth.uid()));

-- Watchlists policies
CREATE POLICY "Users can manage own watchlists"
    ON watchlists FOR ALL
    USING (user_id = auth.uid());

-- Stocks table is public (read-only for authenticated users)
-- No RLS needed, but we can add a policy for authenticated access
ALTER TABLE stocks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can view stocks"
    ON stocks FOR SELECT
    TO authenticated
    USING (true);

-- Sentiment history is public read
ALTER TABLE sentiment_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can view sentiment"
    ON sentiment_history FOR SELECT
    TO authenticated
    USING (true);

-- Price history is public read
ALTER TABLE price_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can view prices"
    ON price_history FOR SELECT
    TO authenticated
    USING (true);

-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Function to calculate agent portfolio value
CREATE OR REPLACE FUNCTION calculate_agent_portfolio_value(p_agent_id UUID)
RETURNS DECIMAL(15,2) AS $$
DECLARE
    v_cash DECIMAL(15,2);
    v_positions_value DECIMAL(15,2);
BEGIN
    -- Get cash balance
    SELECT cash_balance INTO v_cash
    FROM agents WHERE id = p_agent_id;

    -- Get sum of open positions
    SELECT COALESCE(SUM(current_value), 0) INTO v_positions_value
    FROM positions
    WHERE agent_id = p_agent_id AND status = 'open';

    RETURN v_cash + v_positions_value;
END;
$$ LANGUAGE plpgsql;

-- Function to get agent win rate
CREATE OR REPLACE FUNCTION calculate_agent_win_rate(p_agent_id UUID)
RETURNS DECIMAL(8,4) AS $$
DECLARE
    v_total INTEGER;
    v_wins INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_total
    FROM positions
    WHERE agent_id = p_agent_id AND status != 'open';

    IF v_total = 0 THEN
        RETURN 0;
    END IF;

    SELECT COUNT(*) INTO v_wins
    FROM positions
    WHERE agent_id = p_agent_id
      AND status != 'open'
      AND realized_pnl > 0;

    RETURN (v_wins::DECIMAL / v_total) * 100;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- SEED DATA (Stock Universe)
-- ============================================

-- This would be populated by the nightly job
-- Example insert for testing:
-- INSERT INTO stocks (ticker, name, sector, market_cap, price)
-- VALUES ('AAPL', 'Apple Inc.', 'Technology', 2800000000000, 185.50);

COMMENT ON TABLE users IS 'User accounts with broker connection info';
COMMENT ON TABLE agents IS 'Trading agents with strategy and risk configuration';
COMMENT ON TABLE positions IS 'Individual stock positions held by agents';
COMMENT ON TABLE agent_activity IS 'Activity log for all agent actions';
COMMENT ON TABLE daily_reports IS 'LLM-generated daily reports for each agent';
COMMENT ON TABLE agent_chats IS 'Chat history between users and their agents';
COMMENT ON TABLE stocks IS 'Market data cache with factor scores and sentiment';
COMMENT ON TABLE sentiment_history IS 'Historical sentiment data for trending analysis';
COMMENT ON TABLE price_history IS 'Historical price data for charting and backtesting';
COMMENT ON TABLE watchlists IS 'User-created stock watchlists';
