"""
Strategy Execution Engine

Maps agent configurations to the strategy framework, fetches required
market + sentiment data, runs strategies with full sentiment integration,
and returns position recommendations.

This is the bridge between:
  - Agent configs (api/agents.py)       → what the user configured
  - Strategy framework (core/strategies) → signal generation + portfolio construction
  - Sentiment integration (core/sentiment_integration) → proprietary scoring
  - Broker (core/broker)                 → order execution
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.factors import FactorCalculator
from core.sentiment_integration import (
    SentimentFactorIntegrator,
    SentimentInput,
    TemporalSentimentAnalyzer,
)
from core.strategies import (
    SentimentConfig,
    SentimentMode,
    StrategyConfig,
    StrategyOutput,
    StrategyRegistry,
    StrategyType,
)
from core.strategies.presets import get_preset

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mapping from agent strategy_type → strategy preset name + StrategyType
# ---------------------------------------------------------------------------

AGENT_STRATEGY_MAP: dict[str, dict[str, Any]] = {
    "momentum": {
        "preset": "momentum",
        "strategy_type": StrategyType.CROSS_SECTIONAL_FACTOR,
        "sentiment_mode": SentimentMode.FILTER,
    },
    "quality_value": {
        "preset": "quality_value",
        "strategy_type": StrategyType.CROSS_SECTIONAL_FACTOR,
        "sentiment_mode": SentimentMode.CONFIRMATION,
    },
    "quality_momentum": {
        "preset": "quality_momentum",
        "strategy_type": StrategyType.CROSS_SECTIONAL_FACTOR,
        "sentiment_mode": SentimentMode.ALPHA,
    },
    "dividend_growth": {
        "preset": "dividend_growth",
        "strategy_type": StrategyType.CROSS_SECTIONAL_FACTOR,
        "sentiment_mode": SentimentMode.FILTER,
    },
    "trend_following": {
        "preset": "trend_following",
        "strategy_type": StrategyType.TREND_FOLLOWING,
        "sentiment_mode": SentimentMode.RISK_ADJUSTMENT,
    },
    "short_term_reversal": {
        "preset": "short_term_reversal",
        "strategy_type": StrategyType.SHORT_TERM_REVERSAL,
        "sentiment_mode": SentimentMode.CONFIRMATION,
    },
    "statistical_arbitrage": {
        "preset": "statistical_arbitrage",
        "strategy_type": StrategyType.STATISTICAL_ARBITRAGE,
        "sentiment_mode": SentimentMode.ALPHA,
    },
    "volatility_premium": {
        "preset": "volatility_premium",
        "strategy_type": StrategyType.VOLATILITY_PREMIUM,
        "sentiment_mode": SentimentMode.FILTER,
    },
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class AgentContext:
    """Everything needed to execute a strategy for an agent."""

    agent_id: str
    user_id: str
    strategy_type: str
    strategy_params: dict[str, Any]
    risk_params: dict[str, Any]
    allocated_capital: float
    current_positions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ExecutionResult:
    """Output of a strategy execution for one agent."""

    agent_id: str
    strategy_output: StrategyOutput | None = None
    integrated_scores: dict[str, float] = field(default_factory=dict)
    regime: str = "neutral"
    error: str | None = None
    executed_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class StrategyEngine:
    """
    Executes strategies for agents with full sentiment integration.

    Usage::

        engine = StrategyEngine(db_client=supabase)
        result = await engine.execute_for_agent(agent_context)
    """

    def __init__(self, db_client: Any = None):
        self._db = db_client

    async def execute_for_agent(
        self,
        ctx: AgentContext,
        market_data: dict[str, dict[str, Any]] | None = None,
        sentiment_data: dict[str, SentimentInput] | None = None,
    ) -> ExecutionResult:
        """
        Run the full strategy pipeline for a single agent.

        Steps:
        1. Resolve agent config → strategy preset
        2. Fetch market data + sentiment (if not provided)
        3. Run sentiment-factor integration
        4. Instantiate strategy with sentiment mode
        5. Execute strategy → StrategyOutput with positions

        Args:
            ctx: Agent context with config and current positions.
            market_data: Pre-fetched market data (optional, fetched if None).
            sentiment_data: Pre-fetched sentiment data (optional, fetched if None).

        Returns:
            ExecutionResult with position recommendations.
        """
        try:
            # Step 1: Resolve strategy config from agent settings
            config = self._resolve_strategy_config(ctx)
            logger.info(
                "Agent %s: resolved strategy=%s sentiment_mode=%s",
                ctx.agent_id,
                config.strategy_type.value,
                config.sentiment.mode.value,
            )

            # Step 2: Fetch data if not pre-supplied
            if market_data is None or sentiment_data is None:
                market_data, sentiment_data = await self._fetch_data(ctx)

            # Step 3: Enrich sentiment with temporal history
            temporal = TemporalSentimentAnalyzer(db_client=self._db)
            sentiment_data = await temporal.enrich(sentiment_data, lookback_days=30)

            # Step 4: Run sentiment-factor integration
            integrator = SentimentFactorIntegrator(
                strategy_type=ctx.strategy_type,
                sentiment_weight=ctx.strategy_params.get("sentiment_weight", 0.25),
            )

            # Build factor scores from market data
            calculator = FactorCalculator(sector_aware=True)
            sectors = {
                sym: d.get("sector", "Unknown") for sym, d in market_data.items()
            }
            factor_scores = calculator.calculate_all(market_data, sectors)

            factor_data = {
                sym: {
                    "momentum_score": fs.momentum_score,
                    "value_score": fs.value_score,
                    "quality_score": fs.quality_score,
                    "dividend_score": fs.dividend_score,
                    "volatility_score": fs.volatility_score,
                }
                for sym, fs in factor_scores.items()
            }

            integrated = integrator.integrate(
                factor_data, sentiment_data, market_data=market_data
            )

            # Step 4: Build sentiment_data dict for strategy framework
            # (the strategy framework expects symbol → {combined, news, social, velocity})
            strategy_sentiment = {}
            for sym, si in sentiment_data.items():
                strategy_sentiment[sym] = {
                    "combined_sentiment": si.combined_sentiment,
                    "news_sentiment": si.news_sentiment,
                    "social_sentiment": si.social_sentiment,
                    "sentiment_velocity": si.velocity,
                }

            # Step 5: Instantiate and execute strategy
            strategy = StrategyRegistry.create(config)
            output = await strategy.execute(
                market_data=market_data,
                sentiment_data=strategy_sentiment,
                current_positions={
                    p.get("ticker", p.get("symbol", "")): p
                    for p in ctx.current_positions
                },
            )

            # Collect integrated composites for logging / ranking
            integrated_scores = {
                sym: iscore.composite_score for sym, iscore in integrated.items()
            }

            regime = integrator._detect_regime(sentiment_data).label

            logger.info(
                "Agent %s: strategy produced %d positions | regime=%s",
                ctx.agent_id,
                len(output.positions),
                regime,
            )

            return ExecutionResult(
                agent_id=ctx.agent_id,
                strategy_output=output,
                integrated_scores=integrated_scores,
                regime=regime,
            )

        except Exception as e:
            logger.exception(
                "Agent %s: strategy execution failed: %s",
                ctx.agent_id,
                str(e),
            )
            return ExecutionResult(agent_id=ctx.agent_id, error=str(e))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_strategy_config(self, ctx: AgentContext) -> StrategyConfig:
        """Map agent settings to a StrategyConfig."""
        mapping = AGENT_STRATEGY_MAP.get(ctx.strategy_type)
        if not mapping:
            raise ValueError(
                f"Unknown strategy_type: {ctx.strategy_type}. "
                f"Valid: {list(AGENT_STRATEGY_MAP.keys())}"
            )

        # Start from the preset, then overlay agent-specific params
        preset_name = mapping["preset"]
        sentiment_mode = mapping["sentiment_mode"]

        # Build universe from agent's sector and exclusion preferences
        universe = ctx.strategy_params.get("universe", [])
        exclude = ctx.strategy_params.get("exclude_tickers", [])

        config = get_preset(
            preset_name,
            name=f"agent-{ctx.agent_id}",
            universe=universe,
            sentiment_mode=sentiment_mode,
        )

        # Override from agent params
        sentiment_weight = ctx.strategy_params.get("sentiment_weight", 0.3)
        config.sentiment = SentimentConfig(
            mode=sentiment_mode,
            news_weight=0.4,
            social_weight=0.3,
            velocity_weight=0.3,
            sentiment_alpha_weight=sentiment_weight,
        )

        # Apply max_positions and other custom params
        if "max_positions" in ctx.strategy_params:
            config.custom_params["top_n"] = ctx.strategy_params["max_positions"]
        if exclude:
            config.custom_params["exclude_tickers"] = exclude

        return config

    async def _fetch_data(
        self, ctx: AgentContext
    ) -> tuple[dict[str, dict[str, Any]], dict[str, SentimentInput]]:
        """Fetch market + sentiment data from database."""
        if not self._db:
            raise RuntimeError("No database client configured for StrategyEngine")

        market_data: dict[str, dict[str, Any]] = {}
        sentiment_data: dict[str, SentimentInput] = {}

        result = self._db.table("stocks").select("*").execute()

        for row in result.data:
            symbol = row.get("symbol")
            if not symbol:
                continue

            market_data[symbol] = {
                "current_price": row.get("price"),
                "price_history": [],
                "pe_ratio": row.get("pe_ratio"),
                "pb_ratio": row.get("pb_ratio"),
                "roe": row.get("roe"),
                "profit_margin": row.get("profit_margin"),
                "debt_to_equity": row.get("debt_to_equity"),
                "dividend_yield": row.get("dividend_yield"),
                "dividend_growth_5y": row.get("dividend_growth_5y"),
                "ma_30": row.get("ma_30"),
                "ma_100": row.get("ma_100"),
                "ma_200": row.get("ma_200"),
                "atr": row.get("atr"),
                "sector": row.get("sector"),
            }

            sentiment_data[symbol] = SentimentInput(
                symbol=symbol,
                news_sentiment=row.get("news_sentiment"),
                social_sentiment=row.get("social_sentiment"),
                combined_sentiment=row.get("combined_sentiment"),
                velocity=row.get("sentiment_velocity"),
            )

        return market_data, sentiment_data
