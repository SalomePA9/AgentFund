/**
 * TypeScript type definitions for AgentFund
 */

// ============================================
// User Types
// ============================================

export interface User {
  id: string;
  email: string;
  total_capital: number;
  allocated_capital: number;
  settings: UserSettings;
  created_at: string;
  updated_at: string;
}

export interface UserSettings {
  timezone: string;
  report_time: string;
  email_reports: boolean;
  email_alerts: boolean;
}

// ============================================
// Agent Types
// ============================================

export type AgentStatus = 'active' | 'paused' | 'stopped' | 'completed';

export type StrategyType =
  | 'momentum'
  | 'quality_value'
  | 'quality_momentum'
  | 'dividend_growth'
  | 'trend_following'
  | 'short_term_reversal'
  | 'statistical_arbitrage'
  | 'volatility_premium';

export type Persona =
  | 'analytical'
  | 'aggressive'
  | 'conservative'
  | 'teacher'
  | 'concise';

export interface StrategyParams {
  momentum_lookback_days: number;
  min_market_cap: number;
  sectors: string | string[];
  exclude_tickers: string[];
  max_positions: number;
  sentiment_weight: number;
  rebalance_frequency: string;
}

export interface RiskParams {
  stop_loss_type: string;
  stop_loss_percentage: number;
  max_position_size_pct: number;
  min_risk_reward_ratio: number;
  max_sector_concentration: number;
}

export interface Agent {
  id: string;
  user_id: string;
  name: string;
  persona: Persona;
  status: AgentStatus;
  strategy_type: StrategyType;
  strategy_params: StrategyParams;
  risk_params: RiskParams;
  allocated_capital: number;
  cash_balance: number;
  time_horizon_days: number;
  start_date: string;
  end_date: string;
  total_value: number | null;
  total_return_pct: number | null;
  daily_return_pct: number | null;
  sharpe_ratio: number | null;
  max_drawdown_pct: number | null;
  win_rate_pct: number | null;
  created_at: string;
  updated_at: string;
}

export interface AgentCreate {
  name: string;
  persona: Persona;
  strategy_type: StrategyType;
  strategy_params?: Partial<StrategyParams>;
  risk_params?: Partial<RiskParams>;
  allocated_capital: number;
  time_horizon_days: number;
}

// ============================================
// Position Types
// ============================================

export type PositionStatus =
  | 'open'
  | 'closed_target'
  | 'closed_stop'
  | 'closed_manual'
  | 'closed_horizon';

export interface Position {
  id: string;
  agent_id: string;
  ticker: string;
  entry_price: number;
  entry_date: string;
  shares: number;
  entry_rationale: string | null;
  target_price: number | null;
  stop_loss_price: number | null;
  current_price: number | null;
  current_value: number | null;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
  status: PositionStatus;
  exit_price: number | null;
  exit_date: string | null;
  exit_rationale: string | null;
  realized_pnl: number | null;
  realized_pnl_pct: number | null;
  created_at: string;
  updated_at: string;
}

// ============================================
// Activity Types
// ============================================

export type ActivityType =
  | 'buy'
  | 'sell'
  | 'stop_hit'
  | 'target_hit'
  | 'rebalance'
  | 'alert'
  | 'strategy_change'
  | 'capital_change'
  | 'paused'
  | 'resumed';

export interface Activity {
  id: string;
  agent_id: string;
  activity_type: ActivityType;
  ticker: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

// ============================================
// Report Types
// ============================================

export interface DailyReport {
  id: string;
  agent_id: string;
  report_date: string;
  report_content: string;
  performance_snapshot: PerformanceSnapshot;
  positions_snapshot: PositionSnapshot[];
  actions_taken: ActionTaken[];
  created_at: string;
}

export interface PerformanceSnapshot {
  total_value: number;
  daily_return: number;
  daily_return_pct: number;
  total_return_pct: number;
  vs_benchmark: number;
  sharpe_ratio: number | null;
  max_drawdown: number | null;
}

export interface PositionSnapshot {
  ticker: string;
  entry_price: number;
  current_price: number;
  shares: number;
  return_pct: number;
  status: string;
}

export interface ActionTaken {
  type: string;
  ticker: string;
  price: number;
  shares?: number;
  reason?: string;
  pnl?: number;
}

// ============================================
// Chat Types
// ============================================

export interface ChatMessage {
  id: string;
  agent_id: string;
  role: 'user' | 'agent';
  message: string;
  context_used?: Record<string, unknown>;
  created_at: string;
}

// ============================================
// Market Data Types
// ============================================

export interface Stock {
  ticker: string;
  name: string | null;
  sector: string | null;
  industry: string | null;
  market_cap: number | null;
  price: number | null;
  ma_30: number | null;
  ma_100: number | null;
  ma_200: number | null;
  momentum_score: number | null;
  value_score: number | null;
  quality_score: number | null;
  composite_score: number | null;
  pe_ratio: number | null;
  dividend_yield: number | null;
  news_sentiment: number | null;
  social_sentiment: number | null;
  combined_sentiment: number | null;
  updated_at: string | null;
}

// ============================================
// Broker Types
// ============================================

export interface BrokerStatus {
  connected: boolean;
  paper_mode: boolean | null;
  account_id: string | null;
  status: string | null;
  portfolio_value: number | null;
  cash: number | null;
  buying_power: number | null;
}

// ============================================
// API Response Types
// ============================================

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  per_page: number;
}

export interface ApiError {
  detail: string;
}
