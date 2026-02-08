# Fund-Level Strategy Integration Plan

## Current State Assessment

### What Exists Today
The platform runs **autonomous trading agents** that each operate independently:

- **Per-agent risk management** (`backend/core/strategies/base.py:443-527`): position size caps, sector concentration limits, leverage scaling, ATR-based stops/targets, correlation filtering within a single agent's portfolio
- **Per-agent circuit breaker** (`backend/core/engine.py:730-787`): halts trading when an individual agent hits its `max_drawdown_limit` (default 20%)
- **Capital isolation** (`backend/api/agents.py`): each agent gets `allocated_capital` from the user's `total_capital`, preventing over-allocation
- **Independent execution** (`backend/jobs/strategy_execution_job.py:846-911`): agents are iterated sequentially — each generates positions, executes orders, and syncs state without awareness of other agents

### What's Missing
There is **no fund-level coordination layer**. Each agent is a silo:
- No cross-agent correlation tracking
- No fund-level VAR or risk budget system
- No strategy classification beyond the agent's `strategy_type` label
- No centralized risk overlay that can intervene across agents
- No fund-wide stress testing
- No liquidity risk assessment
- No mechanical drawdown rules at the fund level
- No risk-adjusted incentive/scoring system

---

## Architecture Principle: The Fund Overlay

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER                                      │
│              (total_capital, preferences)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│                  ┌─────────────────────┐                         │
│                  │    FUND OVERLAY     │  ◄── NEW LAYER           │
│                  │  (Risk Committee)   │                          │
│                  └────────┬────────────┘                         │
│                           │                                       │
│          ┌────────────────┼────────────────┐                     │
│          │                │                │                      │
│    ┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐              │
│    │  Agent A   │   │  Agent B   │   │  Agent C   │              │
│    │ Momentum   │   │ Stat Arb   │   │ Vol Prem   │              │
│    │ (autonomous│   │ (autonomous│   │ (autonomous│              │
│    │  signals)  │   │  signals)  │   │  signals)  │              │
│    └────────────┘   └────────────┘   └────────────┘              │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Core principle**: Agents remain autonomous signal generators and portfolio constructors. The Fund Overlay sits *above* them and can constrain, scale, override, or hedge — but never replaces their decision-making. This is exactly how multi-PM hedge funds operate: traders have autonomy within bounds.

---

## Implementation Plan

### Phase 1: Foundation — Risk Budgets & Strategy Classification

#### 1A. Risk Budget System (Strategy Item #1)

**Problem**: Today, agents get capital but no risk budget. Two agents can both be "profitable" while one dominates fund risk.

**New files:**
- `backend/core/fund/risk_budget.py` — Risk budget computation and enforcement

**Database changes** (`database/schema.sql`):
```sql
-- Add to agents table
ALTER TABLE agents ADD COLUMN risk_budget_pct DECIMAL(8,4) DEFAULT 0.25;  -- max % of fund VAR
ALTER TABLE agents ADD COLUMN max_daily_drawdown_pct DECIMAL(8,4) DEFAULT 0.03;  -- 3% daily
ALTER TABLE agents ADD COLUMN max_monthly_drawdown_pct DECIMAL(8,4) DEFAULT 0.08; -- 8% monthly
ALTER TABLE agents ADD COLUMN gross_exposure_cap DECIMAL(8,4) DEFAULT 1.0;
ALTER TABLE agents ADD COLUMN net_exposure_cap DECIMAL(8,4) DEFAULT 0.5;
ALTER TABLE agents ADD COLUMN leverage_limit DECIMAL(8,4) DEFAULT 1.0;
ALTER TABLE agents ADD COLUMN current_var_contribution DECIMAL(8,4);  -- computed daily
ALTER TABLE agents ADD COLUMN current_drawdown_daily DECIMAL(8,4);
ALTER TABLE agents ADD COLUMN current_drawdown_monthly DECIMAL(8,4);
```

**Implementation in `risk_budget.py`:**
```python
@dataclass
class RiskBudget:
    agent_id: str
    max_var_contribution_pct: float  # e.g., 0.15 = no more than 15% of fund VAR
    max_daily_drawdown: float        # e.g., 0.03 = 3%
    max_monthly_drawdown: float      # e.g., 0.08
    gross_exposure_cap: float        # e.g., 1.0 = 100% of allocated capital
    net_exposure_cap: float          # e.g., 0.5 = 50% net long/short
    leverage_limit: float            # tied to strategy type

class RiskBudgetManager:
    def compute_agent_var(agent_positions, price_history, confidence=0.95) -> float:
        """Parametric VAR using position-level returns and covariance."""

    def compute_fund_var(all_agents_positions, price_history) -> float:
        """Fund-level VAR considering cross-agent correlations."""

    def check_var_budget(agent_id, agent_var, fund_var, budget) -> BudgetStatus:
        """Returns WITHIN_BUDGET, WARNING (>80%), or BREACH."""

    def check_drawdown_limits(agent_id, daily_pnl, monthly_pnl, budget) -> DrawdownStatus:
        """Check daily/monthly drawdown against limits."""

    def compute_scale_factor(agent_id, status) -> float:
        """If breaching, return scale factor (0.0 to 1.0) to apply to agent's positions."""
```

**Integration point** — `backend/jobs/strategy_execution_job.py`:
- After `engine.execute_for_agent()` returns but *before* `execute_orders()`, insert a fund overlay check
- The overlay can scale down `target_weight` on all positions or block execution entirely
- This preserves agent autonomy (agent still picks its stocks) while the fund controls sizing

**Estimated scope**: ~300 lines new code, 1 migration, ~50 lines modified in execution job

---

#### 1B. Strategy & Domain Segmentation (Strategy Item #2)

**Problem**: Two agents labeled differently (e.g., "momentum" and "trend_following") can still be dangerously correlated because they share the same risk drivers.

**New files:**
- `backend/core/fund/strategy_classification.py` — Factor-based strategy classification

**Database changes:**
```sql
-- New table for strategy buckets
CREATE TABLE IF NOT EXISTS fund_strategy_buckets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    bucket_name TEXT NOT NULL,           -- e.g., "directional_equity", "vol_selling", "mean_reversion"
    max_risk_allocation_pct DECIMAL(8,4) DEFAULT 0.25,  -- max 25% of fund risk from this bucket
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add to agents table
ALTER TABLE agents ADD COLUMN strategy_bucket TEXT;     -- FK-like reference to bucket_name
ALTER TABLE agents ADD COLUMN risk_driver_tags TEXT[];   -- e.g., ['equity_beta', 'momentum', 'rates_duration']
```

**Strategy classification mapping** (in `strategy_classification.py`):
```python
# Map strategy types to their dominant risk drivers
STRATEGY_RISK_DRIVERS: dict[str, list[str]] = {
    "momentum":              ["equity_beta", "momentum_factor", "risk_on"],
    "quality_value":         ["equity_beta", "value_factor", "defensive"],
    "quality_momentum":      ["equity_beta", "momentum_factor", "quality_factor"],
    "dividend_growth":       ["equity_beta", "dividend_yield", "rates_duration", "defensive"],
    "trend_following":       ["momentum_factor", "risk_on", "convexity"],
    "short_term_reversal":   ["mean_reversion", "liquidity"],
    "statistical_arbitrage": ["spread_risk", "liquidity", "market_neutral"],
    "volatility_premium":    ["vega", "gamma", "vol_selling", "tail_risk"],
}

# Default bucket assignments
STRATEGY_BUCKET_MAP: dict[str, str] = {
    "momentum":              "directional_equity",
    "quality_value":         "directional_equity",
    "quality_momentum":      "directional_equity",
    "dividend_growth":       "income_defensive",
    "trend_following":       "systematic_trend",
    "short_term_reversal":   "mean_reversion",
    "statistical_arbitrage": "market_neutral",
    "volatility_premium":    "vol_selling",
}
```

**Enforcement**: When computing risk budgets, aggregate by bucket and enforce `max_risk_allocation_pct` per bucket. If a user creates 3 momentum agents, they'd all fall into "directional_equity" and collectively can't exceed the bucket's risk cap.

**Estimated scope**: ~200 lines new code, 1 migration, integrated into risk budget checks

---

### Phase 2: Cross-Agent Intelligence

#### 2A. Correlation & Factor Monitoring (Strategy Item #3)

**Problem**: Agents are blind to each other. Five agents can independently accumulate the same factor exposure without anyone noticing until it's too late.

**New files:**
- `backend/core/fund/correlation_monitor.py` — Cross-agent P&L and factor correlation tracking
- `backend/jobs/fund_risk_monitoring_job.py` — Scheduled job (daily, optionally intraday)

**Database changes:**
```sql
-- Fund-level risk snapshots
CREATE TABLE IF NOT EXISTS fund_risk_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    snapshot_date DATE NOT NULL,

    -- Fund-level metrics
    fund_var_95 DECIMAL(15,4),           -- 95% parametric VAR
    fund_var_99 DECIMAL(15,4),           -- 99% VAR
    fund_gross_exposure DECIMAL(15,4),
    fund_net_exposure DECIMAL(15,4),

    -- Factor exposures (aggregate across all agents)
    equity_beta_exposure DECIMAL(8,4),
    momentum_factor_exposure DECIMAL(8,4),
    value_factor_exposure DECIMAL(8,4),
    rates_duration_exposure DECIMAL(8,4),
    credit_spread_exposure DECIMAL(8,4),
    volatility_exposure DECIMAL(8,4),

    -- Concentration metrics
    max_single_name_pct DECIMAL(8,4),    -- largest single stock across all agents
    top_10_concentration_pct DECIMAL(8,4),
    hhi_index DECIMAL(8,4),             -- Herfindahl-Hirschman Index

    -- Correlation data (stored as JSONB for flexibility)
    agent_pnl_correlations JSONB,        -- pairwise rolling correlations between agents
    factor_loadings JSONB,               -- per-agent factor beta estimates

    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, snapshot_date)
);
```

**Implementation in `correlation_monitor.py`:**
```python
class CorrelationMonitor:
    def compute_rolling_pnl_correlations(
        agent_returns: dict[str, list[float]],  # agent_id -> daily returns
        window: int = 60  # 60-day rolling window
    ) -> dict[tuple[str,str], float]:
        """Pairwise rolling correlations between agent P&L streams."""

    def compute_factor_exposures(
        all_positions: dict[str, list[Position]],  # agent_id -> positions
        market_data: dict[str, dict],
        factor_returns: dict[str, list[float]]     # factor -> daily returns
    ) -> dict[str, dict[str, float]]:
        """Estimate each agent's loading on common factors using regression."""

    def detect_crowding(
        all_positions: dict[str, list[Position]],
    ) -> dict[str, CrowdingAlert]:
        """Flag when multiple agents hold the same names or when
        aggregate position exceeds single-name limits."""

    def recommend_actions(
        correlations: dict,
        factor_exposures: dict,
        crowding: dict,
        risk_budgets: dict
    ) -> list[FundAction]:
        """Generate actionable recommendations:
        - Reduce capital to clustered agents
        - Force de-risking when correlations spike
        - Gate new positions in crowded factors"""
```

**Key factors to track** (mapped from existing data):
| Factor | Data Source | How to Compute |
|--------|-----------|----------------|
| Equity beta | `stocks.beta`, price history | Weighted avg beta of agent's positions |
| Momentum | `stocks.momentum_score` | Net exposure to high-momentum names |
| Value | `stocks.value_score` | Net exposure to high-value names |
| Volatility | ATR, realized vol from price_history | Portfolio vega/gamma proxy |
| Sector concentration | `stocks.sector` | Cross-agent sector exposure |
| Liquidity | `stocks.avg_volume` | Position size vs ADV |

**Scheduled job** (`fund_risk_monitoring_job.py`):
- Runs daily after `strategy_execution_job`
- Computes all correlations, factor loadings, and risk snapshots
- Stores in `fund_risk_snapshots`
- Generates alerts for concerning patterns
- Optionally runs intraday (every 2-4 hours) if positions table has `current_price` updates

**Estimated scope**: ~500 lines new code, 1 migration, 1 new job

---

#### 2B. Centralized Risk Overlay / "Risk Committee" (Strategy Item #4)

**Problem**: Without a central authority, no one can net exposures across agents or apply fund-level hedges.

**New files:**
- `backend/core/fund/risk_overlay.py` — The "risk committee" logic
- `backend/core/fund/fund_hedger.py` — Fund-level hedging recommendations

**Database changes:**
```sql
-- Fund overlay actions log
CREATE TABLE IF NOT EXISTS fund_overlay_actions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    action_type TEXT NOT NULL,  -- 'scale_down', 'force_exit', 'hedge', 'gate', 'override'
    target_agent_id UUID REFERENCES agents(id),
    details JSONB NOT NULL,
    executed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Fund-level hedge positions (index futures, options, etc.)
CREATE TABLE IF NOT EXISTS fund_hedges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    hedge_type TEXT NOT NULL,     -- 'index_short', 'put_spread', 'rate_hedge'
    instrument TEXT NOT NULL,     -- 'SPY', 'QQQ', 'TLT', etc.
    notional DECIMAL(15,2),
    reason TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Implementation in `risk_overlay.py`:**
```python
class FundRiskOverlay:
    """Central risk authority that can intervene in agent execution."""

    def pre_execution_check(
        self,
        agent_context: AgentContext,
        proposed_positions: list[Position],
        fund_state: FundState
    ) -> OverlayDecision:
        """Called BEFORE orders are submitted. Can:
        - APPROVE: let agent proceed as-is
        - SCALE: reduce all position weights by a factor
        - MODIFY: remove specific positions or cap weights
        - BLOCK: prevent execution entirely
        """

    def compute_fund_level_hedges(
        self,
        all_agent_positions: dict[str, list[Position]],
        factor_exposures: dict,
        risk_snapshot: FundRiskSnapshot
    ) -> list[HedgeRecommendation]:
        """Recommend fund-level hedges to offset concentrated exposures.
        Example: 5 agents all long growth → recommend short QQQ futures."""

    def net_exposures(
        self,
        all_positions: dict[str, list[Position]]
    ) -> NetExposureReport:
        """Compute net long/short across all agents per sector, factor, name."""

    def override_position_sizes(
        self,
        agent_id: str,
        positions: list[Position],
        scale_factor: float,
        reason: str
    ) -> list[Position]:
        """Scale down an agent's position sizes. Logs the override."""
```

**Integration point** — modify `strategy_execution_job.py:run_strategy_execution_job()`:

```python
# CURRENT FLOW:
for agent in agents:
    result = await engine.execute_for_agent(ctx, ...)
    orders, broker = await execute_orders(supabase, result, agent, market_data)

# NEW FLOW:
overlay = FundRiskOverlay(supabase, user_id)
fund_state = await overlay.build_fund_state(agents, market_data)

for agent in agents:
    result = await engine.execute_for_agent(ctx, ...)

    # >>> FUND OVERLAY INTERCEPT <<<
    decision = overlay.pre_execution_check(ctx, result, fund_state)
    if decision.action == "BLOCK":
        log_overlay_action(...)
        continue
    elif decision.action == "SCALE":
        result = overlay.apply_scaling(result, decision.scale_factor)
    elif decision.action == "MODIFY":
        result = overlay.apply_modifications(result, decision.modifications)

    orders, broker = await execute_orders(supabase, result, agent, market_data)
    fund_state.update_after_execution(agent, result)  # update running state

# After all agents execute, compute fund-level hedges
hedges = overlay.compute_fund_level_hedges(fund_state)
if hedges:
    await execute_fund_hedges(supabase, hedges, broker)
```

This is the most architecturally significant change. The overlay sits in the execution pipeline and can intercept any agent's output without modifying the agent's logic. The agent still "thinks" independently — the overlay just constrains what gets executed.

**Estimated scope**: ~600 lines new code, 2 migrations, ~100 lines modified in execution job

---

### Phase 3: Position-Level Controls & Mechanical Rules

#### 3A. Enhanced Position Constraints (Strategy Item #5)

**Problem**: Even within an agent's own book, certain positions can create hidden tail risk. Current constraints are limited to `max_position_size` (10%) and `max_sector_exposure` (30%).

**Changes to existing files:**
- `backend/core/strategies/base.py` — Extend `RiskConfig` and `_apply_risk_management()`
- `backend/models/agent.py` — Extend `RiskParams`

**Extended `RiskConfig`** (`base.py`):
```python
@dataclass
class RiskConfig:
    # ... existing fields ...

    # NEW: Position-level constraints
    max_single_name_pct: float = 0.05       # 5% of FUND capital per name (cross-agent)
    max_sector_pct_fund: float = 0.20       # 20% of FUND in one sector
    max_adv_pct: float = 0.10              # Position can't exceed 10% of avg daily volume
    min_market_cap: int = 500_000_000       # No micro-caps
    max_concentration_top5: float = 0.40    # Top 5 positions can't exceed 40%
```

**New liquidity check** in `_apply_risk_management()`:
```python
def _check_liquidity_constraint(self, pos, market_data):
    """Ensure position size doesn't exceed X% of average daily volume."""
    avg_volume = market_data.get(pos.symbol, {}).get("avg_volume", 0)
    price = market_data.get(pos.symbol, {}).get("current_price", 0)
    if avg_volume and price:
        max_notional = avg_volume * price * self.config.risk.max_adv_pct
        max_weight = max_notional / self.allocated_capital
        pos.target_weight = min(pos.target_weight, max_weight)
```

**Fund-level single-name aggregation** (in `risk_overlay.py`):
```python
def check_single_name_concentration(all_positions, fund_capital):
    """Aggregate position in same ticker across all agents.
    If AAPL is 8% of agent A and 7% of agent B, total is ~7.5% of fund.
    Enforce max_single_name_pct at the fund level."""
```

**Estimated scope**: ~150 lines modified in existing files, ~100 lines in overlay

---

#### 3B. Drawdown-Based Auto De-Risking (Strategy Item #6)

**Problem**: The current circuit breaker (`engine.py:730-787`) is all-or-nothing: either the agent trades normally or it liquidates everything. Real funds use graduated drawdown rules.

**New file:**
- `backend/core/fund/drawdown_manager.py` — Graduated drawdown rules

**Implementation:**
```python
@dataclass
class DrawdownRule:
    """A single drawdown threshold and its consequence."""
    drawdown_pct: float     # e.g., 0.05 = 5% drawdown
    action: str             # "reduce_50", "reduce_75", "flatten", "pause"
    scope: str              # "agent" or "fund"
    cooldown_days: int = 5  # days before re-evaluating

class DrawdownManager:
    DEFAULT_AGENT_RULES = [
        DrawdownRule(0.03, "reduce_50", "agent"),    # 3% DD → cut size by 50%
        DrawdownRule(0.05, "reduce_75", "agent"),    # 5% DD → cut size by 75%
        DrawdownRule(0.08, "flatten", "agent"),       # 8% DD → flat book
        DrawdownRule(0.10, "pause", "agent"),         # 10% DD → pause agent, reallocate capital
    ]

    DEFAULT_FUND_RULES = [
        DrawdownRule(0.02, "reduce_50", "fund"),     # 2% fund DD → all agents halve size
        DrawdownRule(0.04, "flatten", "fund"),        # 4% fund DD → flatten everything
    ]

    def evaluate_agent_drawdown(self, agent, positions, allocated_capital) -> DrawdownAction:
        """Compute current drawdown from peak and match against rules."""

    def evaluate_fund_drawdown(self, all_agents, fund_capital) -> DrawdownAction:
        """Compute fund-level drawdown and match against rules."""

    def compute_scale_factor(self, action: DrawdownAction) -> float:
        """Translate action into a position scale factor (0.0 to 1.0)."""
```

**Database changes:**
```sql
-- Track high-water marks for drawdown computation
ALTER TABLE agents ADD COLUMN peak_value DECIMAL(15,2);
ALTER TABLE agents ADD COLUMN peak_value_date DATE;
ALTER TABLE agents ADD COLUMN drawdown_state TEXT DEFAULT 'normal';  -- normal, reduced_50, reduced_75, flat, paused

-- Fund-level high-water mark
ALTER TABLE users ADD COLUMN fund_peak_value DECIMAL(15,2);
ALTER TABLE users ADD COLUMN fund_peak_value_date DATE;
ALTER TABLE users ADD COLUMN fund_drawdown_state TEXT DEFAULT 'normal';
```

**Integration**: Replace the binary circuit breaker in `engine.py:730-787` with a call to `DrawdownManager.evaluate_agent_drawdown()`. The scale factor flows into the overlay's pre-execution check.

**Estimated scope**: ~250 lines new code, 1 migration, ~30 lines modified in engine.py

---

### Phase 4: Stress Testing & Liquidity

#### 4A. Stress Testing & Scenario Analysis (Strategy Item #7)

**Problem**: Historical VAR underestimates tail risk. The system needs to answer: "Which agents lose together?" and "Where do we blow up simultaneously?"

**New files:**
- `backend/core/fund/stress_testing.py` — Scenario engine
- `backend/api/stress_test.py` — API endpoint for on-demand and scheduled stress tests

**Implementation:**
```python
@dataclass
class StressScenario:
    name: str
    description: str
    factor_shocks: dict[str, float]  # factor_name -> shock magnitude

PREDEFINED_SCENARIOS = [
    StressScenario(
        name="2008_liquidity_freeze",
        description="Global liquidity crisis",
        factor_shocks={
            "equity_beta": -0.40,       # S&P down 40%
            "credit_spread": +0.08,     # spreads widen 800bps
            "volatility": +2.5,         # VIX triples
            "liquidity": -0.50,         # volume drops 50%
            "momentum_factor": -0.25,   # momentum crash
        }
    ),
    StressScenario(
        name="2020_covid_crash",
        factor_shocks={
            "equity_beta": -0.34,
            "volatility": +3.0,         # VIX 13 → 82
            "rates_duration": -0.015,   # rates drop 150bps
            "credit_spread": +0.04,
        }
    ),
    StressScenario(
        name="rate_shock_200bps",
        factor_shocks={
            "rates_duration": +0.02,
            "equity_beta": -0.10,
            "value_factor": +0.05,      # value outperforms
            "momentum_factor": -0.10,   # growth sells off
        }
    ),
    StressScenario(
        name="vol_spike_vix_40",
        factor_shocks={
            "volatility": +1.67,        # VIX 15 → 40
            "equity_beta": -0.15,
            "vol_selling": -0.30,       # vol sellers crushed
        }
    ),
    StressScenario(
        name="correlation_breakdown",
        factor_shocks={
            "correlation_spike": 1.0,   # all correlations → 1
            "equity_beta": -0.20,
            "liquidity": -0.30,
        }
    ),
]

class StressTestEngine:
    def run_scenario(
        self,
        scenario: StressScenario,
        all_agent_positions: dict[str, list[Position]],
        factor_exposures: dict[str, dict[str, float]]
    ) -> StressTestResult:
        """Estimate P&L impact per agent and at fund level.
        Uses factor_exposures × factor_shocks to estimate losses."""

    def identify_correlated_losses(
        self,
        results: list[StressTestResult]
    ) -> list[tuple[str, str, float]]:
        """Find agent pairs that lose together across scenarios."""

    def generate_report(self, results) -> StressTestReport:
        """Human-readable report answering:
        - Which agents lose together?
        - Where do we blow up simultaneously?
        - What's the worst-case fund-level loss?"""
```

**API endpoint** (`backend/api/stress_test.py`):
```python
@router.post("/fund/stress-test")
async def run_stress_test(scenario_name: str = None):
    """Run stress test on current portfolio. If no scenario, run all predefined."""

@router.get("/fund/stress-test/results")
async def get_stress_test_results(limit: int = 10):
    """Get recent stress test results."""
```

**Database changes:**
```sql
CREATE TABLE IF NOT EXISTS stress_test_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    scenario_name TEXT NOT NULL,
    run_date TIMESTAMPTZ DEFAULT NOW(),

    -- Results
    fund_pnl_impact DECIMAL(15,2),
    fund_pnl_impact_pct DECIMAL(8,4),
    per_agent_results JSONB,       -- {agent_id: {pnl, pnl_pct, top_losers}}
    correlated_loss_pairs JSONB,   -- [{agent_a, agent_b, joint_loss}]
    worst_case_summary TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Estimated scope**: ~400 lines new code, 1 migration, 1 API route

---

#### 4B. Liquidity & Exit Risk Management (Strategy Item #8)

**Problem**: A position can look great on paper but be impossible to exit under stress. Current system has no liquidity awareness.

**New file:**
- `backend/core/fund/liquidity_risk.py`

**Implementation:**
```python
class LiquidityRiskManager:
    def compute_days_to_liquidate(
        self,
        position_value: float,
        avg_daily_volume: int,
        current_price: float,
        stress_volume_haircut: float = 0.5  # assume 50% volume drop in stress
    ) -> float:
        """Days to exit assuming max 10% of daily volume participation."""

    def compute_portfolio_liquidity_score(
        self,
        positions: list[Position],
        market_data: dict
    ) -> LiquidityReport:
        """Returns:
        - Days to liquidate full portfolio under normal conditions
        - Days to liquidate under stress
        - % of book in top 10 illiquid names
        - Crowd-ingestion risk (positions in popular names)
        """

    def apply_liquidity_constraints(
        self,
        positions: list[Position],
        market_data: dict,
        max_days_to_liquidate: float = 3.0,  # must be able to exit in 3 days
        max_adv_pct: float = 0.10
    ) -> list[Position]:
        """Cap position sizes to satisfy liquidity constraints."""
```

**Data source**: The `stocks` table already has `avg_volume` and `volume`. This is sufficient for equity liquidity estimation.

**Integration points:**
1. `_apply_risk_management()` in `base.py` — add liquidity check as step 6
2. `risk_overlay.py` — fund-level aggregate liquidity check
3. `fund_risk_monitoring_job.py` — daily liquidity snapshot

**Estimated scope**: ~200 lines new code, integrated into existing flows

---

### Phase 5: Fund-Level Controls & Kill Switches

#### 5A. Risk-Adjusted Scoring / Incentive Design (Strategy Item #9)

**Problem**: Agents are currently evaluated by raw return (`total_return_pct`). This incentivizes risk-taking without regard to quality of returns.

**New file:**
- `backend/core/fund/performance_scoring.py`

**Implementation:**
```python
class PerformanceScorer:
    def compute_risk_adjusted_metrics(
        self,
        agent_returns: list[float],
        risk_free_rate: float = 0.05
    ) -> RiskAdjustedMetrics:
        """Compute:
        - Sharpe ratio (already exists, but recalculate properly)
        - Sortino ratio (downside deviation only)
        - Calmar ratio (return / max drawdown)
        - Information ratio (vs benchmark)
        """

    def compute_fund_contribution_score(
        self,
        agent_returns: list[float],
        fund_returns: list[float],
        agent_var_contribution: float
    ) -> float:
        """Score based on:
        - Risk-adjusted return (not raw P&L)
        - Diversification benefit (negative correlation with fund = bonus)
        - VAR contribution efficiency (return per unit of risk budget consumed)
        - Penalty for correlation with fund drawdowns
        """

    def recommend_capital_reallocation(
        self,
        agent_scores: dict[str, float],
        current_allocations: dict[str, float]
    ) -> dict[str, float]:
        """Suggest moving capital from low-scoring to high-scoring agents.
        Capital permanence tied to quality of returns, not just magnitude."""
```

**Database changes:**
```sql
ALTER TABLE agents ADD COLUMN sortino_ratio DECIMAL(8,4);
ALTER TABLE agents ADD COLUMN calmar_ratio DECIMAL(8,4);
ALTER TABLE agents ADD COLUMN information_ratio DECIMAL(8,4);
ALTER TABLE agents ADD COLUMN fund_contribution_score DECIMAL(8,4);
ALTER TABLE agents ADD COLUMN risk_adjusted_return DECIMAL(8,4);
```

**Frontend integration**: Extend the existing performance display components to show risk-adjusted metrics alongside raw returns. Surface "fund contribution score" to help users understand which agents are providing genuine diversified alpha vs. taking concentrated bets.

**Estimated scope**: ~250 lines new code, 1 migration

---

#### 5B. Kill Switches & Hard Stops (Strategy Item #10)

**Problem**: When things go sideways, there needs to be zero ambiguity. Current circuit breaker is per-agent only.

**New file:**
- `backend/core/fund/kill_switch.py`

**Implementation:**
```python
class KillSwitch:
    """Non-negotiable, mechanical fund-level circuit breakers."""

    TRIGGERS = [
        KillTrigger("fund_var_breach",  condition="fund_var_99 > 0.05 * fund_capital"),
        KillTrigger("vol_circuit_breaker", condition="vix_proxy > 40"),
        KillTrigger("fund_drawdown_hard", condition="fund_drawdown > 0.05"),
        KillTrigger("correlation_spike", condition="avg_agent_correlation > 0.8"),
        KillTrigger("liquidity_freeze", condition="avg_volume_ratio < 0.3"),
    ]

    def check_all_triggers(self, fund_state: FundState) -> list[KillTrigger]:
        """Evaluate all kill switch conditions. Returns triggered switches."""

    def execute_global_risk_reduction(
        self,
        trigger: KillTrigger,
        all_agents: list[dict],
        broker
    ) -> GlobalReductionResult:
        """Immediate actions:
        - Cancel all pending orders
        - Close positions based on trigger severity
        - Pause all agents
        - Log everything
        - Notify user immediately
        """

    def execute_agent_freeze(self, agent_id: str) -> None:
        """Immediately pause agent and prevent new orders."""
```

**Integration**: Kill switch checks run at the *start* of `run_strategy_execution_job()`, before any agent processing. If a fund-level trigger fires, all agent execution is skipped and the global risk reduction procedure runs instead.

```python
async def run_strategy_execution_job() -> dict:
    # >>> KILL SWITCH CHECK (runs first, before everything) <<<
    kill_switch = KillSwitch(supabase, user_id)
    fund_state = await kill_switch.build_fund_state()
    triggered = kill_switch.check_all_triggers(fund_state)
    if triggered:
        return await kill_switch.execute_global_risk_reduction(triggered, agents, broker)

    # ... normal execution continues ...
```

**Estimated scope**: ~200 lines new code, integrates into execution job entry point

---

## New Directory Structure

```
backend/core/fund/               # NEW: Fund-level overlay package
├── __init__.py
├── risk_budget.py               # Phase 1A: VAR budgets & drawdown limits
├── strategy_classification.py   # Phase 1B: Strategy bucketing & risk drivers
├── correlation_monitor.py       # Phase 2A: Cross-agent correlation & factor tracking
├── risk_overlay.py              # Phase 2B: Central risk committee logic
├── fund_hedger.py               # Phase 2B: Fund-level hedge recommendations
├── drawdown_manager.py          # Phase 3B: Graduated drawdown rules
├── stress_testing.py            # Phase 4A: Scenario engine
├── liquidity_risk.py            # Phase 4B: Liquidity constraints & exit risk
├── performance_scoring.py       # Phase 5A: Risk-adjusted scoring
├── kill_switch.py               # Phase 5B: Hard stops & circuit breakers
└── models.py                    # Shared data classes for fund layer
```

---

## Database Migration Summary

All changes are additive (no breaking changes to existing schema):

| Migration | Tables Modified | Tables Created |
|-----------|----------------|----------------|
| Phase 1A  | `agents` (6 columns) | — |
| Phase 1B  | `agents` (2 columns) | `fund_strategy_buckets` |
| Phase 2A  | — | `fund_risk_snapshots` |
| Phase 2B  | — | `fund_overlay_actions`, `fund_hedges` |
| Phase 3B  | `agents` (3 columns), `users` (3 columns) | — |
| Phase 4A  | — | `stress_test_results` |
| Phase 5A  | `agents` (5 columns) | — |

---

## Execution Pipeline: Before vs After

### Current Pipeline (`strategy_execution_job.py`)

```
1. Fetch active agents
2. Fetch market + sentiment data (shared)
3. FOR EACH agent:
   a. Build AgentContext
   b. engine.execute_for_agent() → positions, orders
   c. execute_orders() → submit to Alpaca
   d. sync_positions() → update DB
   e. sync_agent_cash_balance()
4. Done
```

### Proposed Pipeline (with fund overlay)

```
1. Kill switch check → abort if triggered               [NEW - Phase 5B]
2. Fetch active agents
3. Fetch market + sentiment data (shared)
4. Build FundState (all positions, correlations, VAR)    [NEW - Phase 2B]
5. Run drawdown checks (fund-level)                     [NEW - Phase 3B]
6. FOR EACH agent:
   a. Build AgentContext
   b. Check agent-level drawdown state                   [NEW - Phase 3B]
   c. engine.execute_for_agent() → positions, orders     [UNCHANGED - agent autonomy preserved]
   d. Apply liquidity constraints                        [NEW - Phase 4B]
   e. Fund overlay pre-execution check:                  [NEW - Phase 2B]
      - Risk budget check (VAR contribution)             [Phase 1A]
      - Strategy bucket cap check                        [Phase 1B]
      - Cross-agent single-name concentration check      [Phase 3A]
      - Correlation-based scaling                        [Phase 2A]
   f. execute_orders() → submit to Alpaca               [UNCHANGED]
   g. sync_positions() → update DB                      [UNCHANGED]
   h. sync_agent_cash_balance()                         [UNCHANGED]
   i. Update FundState running totals                    [NEW]
7. Compute fund-level hedges if needed                   [NEW - Phase 2B]
8. Execute fund hedges                                   [NEW - Phase 2B]
9. Run stress tests on final portfolio                   [NEW - Phase 4A]
10. Compute risk-adjusted scores                         [NEW - Phase 5A]
11. Store fund risk snapshot                             [NEW - Phase 2A]
12. Generate fund-level alerts                           [NEW]
```

**Key point**: Step 6c is unchanged. The agent's `execute_for_agent()` still runs with full autonomy. The fund overlay only constrains the *output* (steps 6d-6e), never the *input* or *logic*.

---

## Phased Rollout Recommendation

| Phase | What Ships | Estimated Scope | Dependencies |
|-------|-----------|----------------|--------------|
| **Phase 1** | Risk budgets + strategy classification | ~500 lines + 2 migrations | None |
| **Phase 2** | Correlation monitor + risk overlay | ~1100 lines + 2 migrations | Phase 1 |
| **Phase 3** | Position constraints + graduated drawdowns | ~350 lines + 1 migration | Phase 1 |
| **Phase 4** | Stress testing + liquidity risk | ~600 lines + 1 migration | Phase 2 |
| **Phase 5** | Performance scoring + kill switches | ~450 lines + 1 migration | Phase 2, 3 |

**Total estimated new code**: ~3,000 lines across 11 new files
**Total migrations**: 7 additive migrations
**Existing files modified**: 3-4 files (engine.py, strategy_execution_job.py, base.py, agents.py)

---

## Key Design Decisions

### 1. Fund overlay intercepts OUTPUT, not INPUT
Agents still pick their own stocks and generate their own signals. The overlay only constrains what gets executed. This means agent backtests remain valid, agent-level reports still reflect "what the agent wanted to do," and agent logic doesn't need to know about other agents.

### 2. Scaling over blocking
The overlay prefers scaling positions down (reducing target_weight by a factor) over blocking entire agents. This maintains partial agent autonomy and produces smoother behavior than binary on/off switches.

### 3. Factor-based classification over label-based
Strategy bucketing uses risk driver tags (equity_beta, momentum_factor, etc.) rather than strategy type names. This catches hidden correlations that labels miss — e.g., a "dividend_growth" agent and a "quality_value" agent may both be long defensive/low-beta equities.

### 4. Graduated drawdowns replace binary circuit breaker
The existing `max_drawdown_limit` → full liquidation behavior is replaced with a graduated system: 50% cut → 75% cut → flatten → pause. This prevents panic selling and allows agents to recover from moderate drawdowns.

### 5. All fund-level state is per-user
Since AgentFund is a multi-user platform, all fund-level tables (risk_snapshots, overlay_actions, etc.) are scoped by `user_id`. Each user effectively runs their own "fund" with their own overlay settings.

### 6. Configuration is hierarchical
Default risk budgets and drawdown rules ship with sensible defaults but are configurable per user and per agent. Power users can tighten or loosen constraints. The defaults match institutional best practices described in the requirements.
