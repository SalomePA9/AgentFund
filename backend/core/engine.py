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
from datetime import datetime, timezone
from typing import Any

from core.factors import FactorCalculator
from core.macro_risk_overlay import MacroRiskOverlay, OverlayResult
from core.sentiment_integration import (
    DEFAULT_FACTOR_WEIGHTS,
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
    cash_balance: float = 0.0
    current_positions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class OrderAction:
    """A concrete order action produced by diffing recommended vs current positions."""

    symbol: str
    action: str  # "buy", "sell", "hold", "increase", "decrease"
    target_weight: float  # recommended weight
    current_weight: float  # current weight (0 if new entry)
    signal_strength: float = 0.0
    reason: str = ""


@dataclass
class ExecutionResult:
    """Output of a strategy execution for one agent."""

    agent_id: str
    strategy_output: StrategyOutput | None = None
    integrated_scores: dict[str, float] = field(default_factory=dict)
    order_actions: list[OrderAction] = field(default_factory=list)
    regime: str = "neutral"
    error: str | None = None
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    macro_overlay: OverlayResult | None = None


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
        macro_data: dict[str, Any] | None = None,
        insider_data: dict[str, dict[str, Any]] | None = None,
        vol_regime_data: dict[str, Any] | None = None,
        short_interest_data: dict[str, dict[str, Any]] | None = None,
        pre_computed_overlay: "OverlayResult | None" = None,
    ) -> ExecutionResult:
        """
        Run the full strategy pipeline for a single agent.

        Steps:
        1. Resolve agent config → strategy preset
        2. Fetch market data + sentiment (if not provided)
        3. Run sentiment-factor integration
        4. Instantiate strategy with sentiment mode
        5. Execute strategy → StrategyOutput with positions
        6. Apply MacroRiskOverlay to scale position sizes

        Args:
            ctx: Agent context with config and current positions.
            market_data: Pre-fetched market data (optional, fetched if None).
            sentiment_data: Pre-fetched sentiment data (optional, fetched if None).
            macro_data: Pre-fetched FRED macro data (credit spreads, yield curve).
            insider_data: Pre-fetched insider transaction data per symbol.
            vol_regime_data: Pre-fetched VIX/volatility regime data.
            short_interest_data: Pre-fetched short interest data per symbol.
                Currently stored on ExecutionResult for downstream
                consumers (reports, logging) but not used by the overlay
                which operates on portfolio-level macro signals only.

        Returns:
            ExecutionResult with position recommendations.
        """
        try:
            # Step 0: Drawdown circuit breaker — halt trading if the
            # agent's portfolio has lost more than the configured max.
            breaker_result = self._check_drawdown_breaker(ctx)
            if breaker_result is not None:
                return breaker_result

            # Step 0b: Rebalance frequency gate — skip execution if the
            # agent has already rebalanced within its configured period.
            skip_reason = self._check_rebalance_frequency(ctx)
            if skip_reason:
                logger.info("Agent %s: skipping — %s", ctx.agent_id, skip_reason)
                return ExecutionResult(agent_id=ctx.agent_id, error=skip_reason)

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

            # Build factor scores from market data using strategy-specific
            # factor weights so the composite score reflects this strategy's
            # priorities (e.g. momentum-heavy for momentum strategies).
            calculator = FactorCalculator(sector_aware=True)
            sectors = {
                sym: d.get("sector", "Unknown") for sym, d in market_data.items()
            }
            strategy_weights = DEFAULT_FACTOR_WEIGHTS.get(ctx.strategy_type)
            factor_scores = calculator.calculate_all(
                market_data, sectors, factor_weights=strategy_weights
            )

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

            # Step 4b: Build sentiment_data dict for strategy framework
            # (the strategy framework expects symbol → {combined, news, social, velocity})
            strategy_sentiment = {}
            for sym, si in sentiment_data.items():
                strategy_sentiment[sym] = {
                    "combined_sentiment": si.combined_sentiment,
                    "news_sentiment": si.news_sentiment,
                    "social_sentiment": si.social_sentiment,
                    "sentiment_velocity": si.velocity,
                }

            # Step 5: Inject integrated composite scores into market_data so
            # strategy.construct_portfolio() can use them for final ranking.
            # Shallow-copy each stock's dict to avoid mutating the shared
            # market_data across agents (composite scores are agent-specific
            # due to different factor weights).
            market_data = {sym: {**data} for sym, data in market_data.items()}
            for sym, iscore in integrated.items():
                if sym in market_data:
                    market_data[sym]["integrated_composite"] = iscore.composite_score

            # Step 6: Instantiate and execute strategy.
            # Disable the strategy-level sentiment overlay for
            # CrossSectionalFactor strategies because the 7-layer
            # SentimentFactorIntegrator has already processed sentiment
            # into integrated_composite scores injected above.  Running
            # both would double-count sentiment.
            #
            # Advanced strategies (TrendFollowing, ShortTermReversal,
            # StatisticalArbitrage, VolatilityPremium) do NOT read
            # integrated_composite and rely on their own sentiment
            # overlays (RISK_ADJUSTMENT, CONFIRMATION, ALPHA, FILTER),
            # so we preserve their designed sentiment modes.  This is
            # especially important for VolatilityPremium's crisis gate
            # which requires FILTER mode to halt vol-selling during
            # market crashes.
            if config.strategy_type == StrategyType.CROSS_SECTIONAL_FACTOR:
                config.sentiment.mode = SentimentMode.DISABLED

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

            # Step 6b: Scale new position weights to fit within available
            # cash.  If cash_balance is set, compute the fraction of
            # allocated_capital that is still available and scale down
            # new entries proportionally.
            self._constrain_to_cash(output, ctx)

            # Step 6c: Apply MacroRiskOverlay — scale ALL position weights
            # based on uncorrelated macro signals (credit spreads, VIX
            # term structure, yield curve, seasonality, insider breadth).
            # This is the cross-agent risk coordinator that reduces
            # exposure when multiple uncorrelated signals confirm danger.
            # Use pre-computed overlay if provided (avoids redundant
            # computation when shared across agents).
            if pre_computed_overlay is not None:
                overlay_result = pre_computed_overlay
            else:
                overlay = MacroRiskOverlay()
                overlay_result = overlay.compute(
                    macro_data=macro_data,
                    insider_data=insider_data,
                    vol_regime_data=vol_regime_data,
                )

            if overlay_result.risk_scale_factor != 1.0 and output:
                for pos in output.positions:
                    pos.target_weight *= overlay_result.risk_scale_factor
                logger.info(
                    "Agent %s: macro overlay applied scale=%.2f "
                    "(regime=%s, composite=%.1f)",
                    ctx.agent_id,
                    overlay_result.risk_scale_factor,
                    overlay_result.regime_label,
                    overlay_result.composite_risk_score,
                )
                for warning in overlay_result.warnings:
                    logger.warning("Agent %s macro: %s", ctx.agent_id, warning)

            # Step 7: Diff recommended positions against current holdings
            # to produce concrete buy/sell/hold order actions.
            order_actions = self._diff_positions(
                output,
                ctx.current_positions,
                allocated_capital=ctx.allocated_capital,
                market_data=market_data,
            )

            # Step 8: Stop-loss check — scan current positions for any
            # that have breached their stop price and inject sell actions.
            stop_exits = self._check_stop_losses(ctx, market_data)
            if stop_exits:
                logger.warning(
                    "Agent %s: %d positions breached stop-loss",
                    ctx.agent_id,
                    len(stop_exits),
                )
                # Merge stop exits into order_actions (overriding any hold/increase)
                stop_syms = {a.symbol for a in stop_exits}
                order_actions = [
                    a for a in order_actions if a.symbol not in stop_syms
                ] + stop_exits

            # Step 9: Take-profit check — scan current positions for any
            # that have reached their target price and inject sell actions.
            tp_exits = self._check_take_profits(ctx, market_data)
            if tp_exits:
                logger.info(
                    "Agent %s: %d positions hit take-profit target",
                    ctx.agent_id,
                    len(tp_exits),
                )
                tp_syms = {a.symbol for a in tp_exits}
                order_actions = [
                    a for a in order_actions if a.symbol not in tp_syms
                ] + tp_exits

            # Step 10: Position aging — exit positions that have exceeded
            # their configured time horizon.
            age_exits = self._check_position_aging(ctx)
            if age_exits:
                logger.info(
                    "Agent %s: %d positions exceeded time horizon",
                    ctx.agent_id,
                    len(age_exits),
                )
                age_syms = {a.symbol for a in age_exits}
                order_actions = [
                    a for a in order_actions if a.symbol not in age_syms
                ] + age_exits

            # Step 11: Enrich buy actions with a per-position investment
            # thesis that explains why the agent is entering this trade.
            self._enrich_trade_theses(
                order_actions, output, integrated_scores, regime, market_data
            )

            logger.info(
                "Agent %s: strategy produced %d positions, "
                "%d order actions | regime=%s",
                ctx.agent_id,
                len(output.positions),
                len(order_actions),
                regime,
            )

            return ExecutionResult(
                agent_id=ctx.agent_id,
                strategy_output=output,
                integrated_scores=integrated_scores,
                order_actions=order_actions,
                regime=regime,
                macro_overlay=overlay_result,
            )

        except Exception as e:
            logger.exception(
                "Agent %s: strategy execution failed: %s",
                ctx.agent_id,
                str(e),
            )
            return ExecutionResult(agent_id=ctx.agent_id, error=str(e))

    # ------------------------------------------------------------------
    # Stop-loss monitoring
    # ------------------------------------------------------------------

    @staticmethod
    def _check_stop_losses(
        ctx: AgentContext,
        market_data: dict[str, dict[str, Any]],
    ) -> list[OrderAction]:
        """
        Check current positions against their stop-loss prices.

        If a position's current market price has breached its stop, produce
        a sell action so the execution layer exits the position.

        Positions are expected to have ``stop_loss`` and ``side`` fields,
        set by the strategy's risk management pass.
        """
        exits: list[OrderAction] = []

        for pos in ctx.current_positions:
            sym = pos.get("ticker", pos.get("symbol", ""))
            stop = pos.get("stop_loss_price") or pos.get("stop_loss")
            side = pos.get("side", "long")

            if not sym or stop is None:
                continue

            current_price = (market_data.get(sym) or {}).get("current_price")
            if current_price is None:
                continue

            try:
                stop = float(stop)
                current_price = float(current_price)
            except (TypeError, ValueError):
                continue

            breached = False
            if side == "long" and current_price <= stop:
                breached = True
            elif side == "short" and current_price >= stop:
                breached = True

            if breached:
                exits.append(
                    OrderAction(
                        symbol=sym,
                        action="sell",
                        target_weight=0.0,
                        current_weight=float(pos.get("target_weight", 0) or 0),
                        signal_strength=100.0,
                        reason=(
                            f"Stop-loss breached: price {current_price:.2f} "
                            f"{'<=' if side == 'long' else '>='} stop {stop:.2f}"
                        ),
                    )
                )

        return exits

    # ------------------------------------------------------------------
    # Take-profit monitoring
    # ------------------------------------------------------------------

    @staticmethod
    def _check_take_profits(
        ctx: AgentContext,
        market_data: dict[str, dict[str, Any]],
    ) -> list[OrderAction]:
        """
        Check current positions against their take-profit prices.

        If a position's current market price has reached its target, produce
        a sell action so the execution layer exits the position with profit.

        Positions are expected to have ``target_price`` and ``side`` fields.
        """
        exits: list[OrderAction] = []

        for pos in ctx.current_positions:
            sym = pos.get("ticker", pos.get("symbol", ""))
            target = pos.get("target_price")
            side = pos.get("side", "long")

            if not sym or target is None:
                continue

            current_price = (market_data.get(sym) or {}).get("current_price")
            if current_price is None:
                continue

            try:
                target = float(target)
                current_price = float(current_price)
            except (TypeError, ValueError):
                continue

            reached = False
            if side == "long" and current_price >= target:
                reached = True
            elif side == "short" and current_price <= target:
                reached = True

            if reached:
                exits.append(
                    OrderAction(
                        symbol=sym,
                        action="sell",
                        target_weight=0.0,
                        current_weight=float(pos.get("target_weight", 0) or 0),
                        signal_strength=100.0,
                        reason=(
                            f"Take-profit reached: price {current_price:.2f} "
                            f"{'≥' if side == 'long' else '≤'} target {target:.2f}"
                        ),
                    )
                )

        return exits

    # ------------------------------------------------------------------
    # Position aging
    # ------------------------------------------------------------------

    @staticmethod
    def _check_position_aging(ctx: AgentContext) -> list[OrderAction]:
        """
        Check if any current positions have exceeded their time horizon.

        Uses ``max_holding_days`` from strategy_params or risk_params.
        Compares against the position's ``entry_date`` field.
        """
        max_days = ctx.strategy_params.get("max_holding_days") or ctx.risk_params.get(
            "max_holding_days"
        )

        if not max_days:
            return []

        from datetime import date as _date

        exits: list[OrderAction] = []
        today = _date.today()

        for pos in ctx.current_positions:
            sym = pos.get("ticker", pos.get("symbol", ""))
            entry_date_str = pos.get("entry_date")
            if not sym or not entry_date_str:
                continue

            try:
                entry_date = (
                    _date.fromisoformat(entry_date_str)
                    if isinstance(entry_date_str, str)
                    else entry_date_str
                )
                days_held = (today - entry_date).days
            except (ValueError, TypeError):
                continue

            if days_held >= max_days:
                exits.append(
                    OrderAction(
                        symbol=sym,
                        action="sell",
                        target_weight=0.0,
                        current_weight=float(pos.get("target_weight", 0) or 0),
                        signal_strength=100.0,
                        reason=(
                            f"Position aged out: held {days_held}d, "
                            f"max horizon {max_days}d"
                        ),
                    )
                )

        return exits

    # ------------------------------------------------------------------
    # Trade thesis generation
    # ------------------------------------------------------------------

    @staticmethod
    def _enrich_trade_theses(
        order_actions: list[OrderAction],
        output: "StrategyOutput",
        integrated_scores: dict[str, float],
        regime: str,
        market_data: dict[str, dict[str, Any]],
    ) -> None:
        """
        Replace generic order reasons with a detailed investment thesis
        for buy and increase actions.  Each thesis captures the signal
        analysis, integrated score, price targets, stop level, time
        horizon, and market regime — like a human trader's trade journal.

        Modifies order_actions in place.
        """
        # Build lookup of strategy-recommended positions
        pos_lookup: dict[str, Any] = {}
        if output:
            for pos in output.positions:
                pos_lookup[pos.symbol] = pos

        for action in order_actions:
            if action.action not in ("buy", "increase"):
                continue

            pos = pos_lookup.get(action.symbol)
            if not pos:
                continue

            md = market_data.get(action.symbol) or {}
            score = integrated_scores.get(action.symbol)
            strategy = pos.metadata.get("strategy", "unknown")
            price = md.get("current_price")

            parts = [f"Strategy: {strategy}"]
            if score is not None:
                parts.append(f"Integrated score: {score:.1f}/100")
            parts.append(f"Signal strength: {pos.signal_strength:.1f}")
            parts.append(f"Regime: {regime}")
            parts.append(f"Weight: {action.target_weight:.1%}")

            if price:
                parts.append(f"Entry ~${float(price):.2f}")
            if pos.stop_loss is not None:
                parts.append(f"Stop: ${pos.stop_loss:.2f}")
            if pos.take_profit is not None:
                parts.append(f"Target: ${pos.take_profit:.2f}")
            if pos.max_holding_days:
                parts.append(f"Horizon: {pos.max_holding_days}d")

            action.reason = " | ".join(parts)

    # ------------------------------------------------------------------
    # Cash-constrained position sizing
    # ------------------------------------------------------------------

    @staticmethod
    def _constrain_to_cash(
        output: "StrategyOutput",
        ctx: AgentContext,
    ) -> None:
        """
        Scale down recommended new-position weights so the total
        notional value of new buys does not exceed the agent's
        available cash.

        Existing positions (already held) are not affected.
        If ``cash_balance`` is 0 or allocated_capital is 0, no
        constraining is performed (the broker-side buying power
        check in execute_orders acts as the final gate).
        """
        if ctx.allocated_capital <= 0 or ctx.cash_balance <= 0:
            return
        if not output or not output.positions:
            return

        # What fraction of allocated capital is available as cash?
        cash_fraction = ctx.cash_balance / ctx.allocated_capital
        if cash_fraction >= 1.0:
            return  # fully liquid — no constraint needed

        # Identify which symbols are NEW (not already held)
        held_syms = {
            p.get("ticker", p.get("symbol", "")) for p in ctx.current_positions
        }

        new_weight_total = sum(
            p.target_weight for p in output.positions if p.symbol not in held_syms
        )

        if new_weight_total <= 0:
            return

        # If new buys exceed cash, scale them down proportionally
        if new_weight_total > cash_fraction:
            scale = cash_fraction / new_weight_total
            for p in output.positions:
                if p.symbol not in held_syms:
                    p.target_weight *= scale

            logger.info(
                "Agent %s: scaled new positions by %.2f "
                "(cash=%.2f, allocated=%.2f, new_wt=%.2f)",
                ctx.agent_id,
                scale,
                ctx.cash_balance,
                ctx.allocated_capital,
                new_weight_total,
            )

    # ------------------------------------------------------------------
    # Rebalance frequency gate
    # ------------------------------------------------------------------

    def _check_rebalance_frequency(self, ctx: AgentContext) -> str | None:
        """
        Check if enough time has passed since the agent's last rebalance.

        Returns a skip-reason string if the agent should not execute, or
        None if it's time to rebalance.
        """
        frequency = ctx.strategy_params.get("rebalance_frequency", "daily")

        # Map frequency to minimum interval.
        # "intraday" allows multiple runs per day with a configurable
        # minimum interval in hours (default 1h) between executions.
        freq_hours: dict[str, float] = {
            "intraday": ctx.strategy_params.get("min_interval_hours", 1.0),
            "daily": 24,
            "weekly": 24 * 7,
            "monthly": 24 * 28,
        }
        min_hours = freq_hours.get(frequency, 24)

        if not self._db:
            return None  # can't check without DB

        try:
            result = (
                self._db.table("agent_activity")
                .select("created_at")
                .eq("agent_id", ctx.agent_id)
                .eq("activity_type", "rebalance")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            if not result.data:
                return None  # never rebalanced — run now

            last_rebalance_str = result.data[0].get("created_at", "")
            if not last_rebalance_str:
                return None

            last_dt = datetime.fromisoformat(last_rebalance_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            elapsed_hours = (now - last_dt).total_seconds() / 3600

            if elapsed_hours < min_hours:
                return (
                    f"Rebalance frequency is {frequency} "
                    f"(min {min_hours:.0f}h) but only "
                    f"{elapsed_hours:.1f}h since last rebalance"
                )
            return None

        except Exception:
            logger.warning(
                "Agent %s: failed to check rebalance frequency — allowing run",
                ctx.agent_id,
                exc_info=True,
            )
            return None

    # ------------------------------------------------------------------
    # Drawdown circuit breaker
    # ------------------------------------------------------------------

    @staticmethod
    def _check_drawdown_breaker(ctx: AgentContext) -> ExecutionResult | None:
        """
        Check if the agent's portfolio drawdown exceeds its configured limit.

        Uses the agent's current positions to compute unrealised P&L vs
        allocated capital.  If drawdown exceeds the max, returns an
        ExecutionResult that signals a full liquidation (sell-all) and
        halts normal strategy execution.

        Returns None if the breaker is not triggered.
        """
        max_drawdown = ctx.risk_params.get("max_drawdown_limit", 0.20)
        allocated = ctx.allocated_capital

        if allocated <= 0:
            return None

        # Compute total P&L from open positions
        total_pnl = 0.0
        for pos in ctx.current_positions:
            pnl = pos.get("unrealized_pl", 0) or 0
            total_pnl += float(pnl)

        drawdown = -total_pnl / allocated if total_pnl < 0 else 0.0

        if drawdown < max_drawdown:
            return None

        logger.warning(
            "CIRCUIT BREAKER: Agent %s drawdown %.1f%% exceeds limit %.1f%% "
            "— halting trading and signalling liquidation",
            ctx.agent_id,
            drawdown * 100,
            max_drawdown * 100,
        )

        # Build sell-all order actions for every open position
        sell_actions: list[OrderAction] = []
        for pos in ctx.current_positions:
            sym = pos.get("ticker", pos.get("symbol", ""))
            if sym:
                sell_actions.append(
                    OrderAction(
                        symbol=sym,
                        action="sell",
                        target_weight=0.0,
                        current_weight=float(pos.get("target_weight", 0) or 0),
                        signal_strength=100.0,
                        reason=f"Circuit breaker: drawdown {drawdown:.1%} exceeds {max_drawdown:.0%} limit",
                    )
                )

        return ExecutionResult(
            agent_id=ctx.agent_id,
            order_actions=sell_actions,
            regime="circuit_breaker",
            error=None,
        )

    # ------------------------------------------------------------------
    # Position diffing
    # ------------------------------------------------------------------

    @staticmethod
    def _diff_positions(
        output: StrategyOutput,
        current_positions: list[dict[str, Any]],
        allocated_capital: float = 0.0,
        market_data: dict[str, dict[str, Any]] | None = None,
    ) -> list[OrderAction]:
        """
        Compare strategy-recommended positions against current holdings
        and produce concrete order actions.

        Computes each position's current weight from its market value
        (shares * current_price) relative to allocated_capital, since
        the positions table does not store target_weight.

        Returns a list of OrderAction objects covering:
        - "buy"      — new position not currently held
        - "sell"     — currently held but not in recommendations (exit)
        - "increase" — held and recommended at a higher weight
        - "decrease" — held and recommended at a lower weight
        - "hold"     — held and recommended at similar weight (±1%)
        """
        market_data = market_data or {}

        # Build lookup of recommended positions by symbol
        recommended: dict[str, Any] = {}
        for pos in output.positions:
            recommended[pos.symbol] = pos

        # Build lookup of current positions by symbol, computing weight
        # from shares * price / allocated_capital.
        current: dict[str, dict[str, Any]] = {}
        for p in current_positions:
            sym = p.get("ticker", p.get("symbol", ""))
            if sym:
                current[sym] = p

        def _calc_weight(sym: str, p: dict) -> float:
            """Compute current portfolio weight for a held position."""
            if allocated_capital <= 0:
                return 0.0
            shares = float(p.get("shares", 0) or 0)
            price = float(
                p.get("current_price")
                or (market_data.get(sym) or {}).get("current_price")
                or p.get("entry_price")
                or 0
            )
            return (shares * price) / allocated_capital if price > 0 else 0.0

        actions: list[OrderAction] = []

        # 1. Check all recommended positions
        for sym, pos in recommended.items():
            if sym in current:
                # Already held — compare weights
                cur_weight = _calc_weight(sym, current[sym])
                diff = pos.target_weight - cur_weight

                if abs(diff) < 0.01:
                    action = "hold"
                    reason = "Weight unchanged"
                elif diff > 0:
                    action = "increase"
                    reason = f"Increase weight by {diff:.1%}"
                else:
                    action = "decrease"
                    reason = f"Decrease weight by {abs(diff):.1%}"

                actions.append(
                    OrderAction(
                        symbol=sym,
                        action=action,
                        target_weight=pos.target_weight,
                        current_weight=cur_weight,
                        signal_strength=pos.signal_strength,
                        reason=reason,
                    )
                )
            else:
                # New entry
                actions.append(
                    OrderAction(
                        symbol=sym,
                        action="buy",
                        target_weight=pos.target_weight,
                        current_weight=0.0,
                        signal_strength=pos.signal_strength,
                        reason="New position recommended",
                    )
                )

        # 2. Check for exits: currently held but not recommended
        for sym, p in current.items():
            if sym not in recommended:
                cur_weight = _calc_weight(sym, p)
                actions.append(
                    OrderAction(
                        symbol=sym,
                        action="sell",
                        target_weight=0.0,
                        current_weight=cur_weight,
                        reason="No longer recommended — exit",
                    )
                )

        return actions

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

        # Override from agent params — preserve the preset's carefully tuned
        # sentiment weights (news/social/velocity/filter_threshold) and only
        # update the mode and alpha weight from agent configuration.
        config.sentiment.mode = sentiment_mode
        if "sentiment_weight" in ctx.strategy_params:
            config.sentiment.sentiment_alpha_weight = ctx.strategy_params[
                "sentiment_weight"
            ]

        # Apply max_positions and other custom params
        if "max_positions" in ctx.strategy_params:
            config.custom_params["top_n"] = ctx.strategy_params["max_positions"]
        if exclude:
            config.custom_params["exclude_tickers"] = exclude

        return config

    def _fetch_price_history(self, symbols: list[str]) -> dict[str, list[float]]:
        """Fetch price history from the price_history table for all symbols.

        Limits to the most recent 400 trading days (~18 months) which is
        sufficient for all factor calculations (momentum needs at most 252
        days) while avoiding unbounded table scans.
        """
        from datetime import datetime, timedelta, timezone

        history: dict[str, list[float]] = {s: [] for s in symbols}

        # 400 trading days ≈ 560 calendar days — covers the 252-day lookback
        # needed for 12-month momentum with comfortable margin.
        cutoff = (datetime.now(timezone.utc) - timedelta(days=560)).strftime("%Y-%m-%d")

        try:
            result = (
                self._db.table("price_history")
                .select("symbol, date, price")
                .in_("symbol", symbols)
                .gte("date", cutoff)
                .order("date", desc=False)
                .execute()
            )

            for row in result.data:
                sym = row.get("symbol")
                price = row.get("price")
                if sym and price is not None:
                    history[sym].append(float(price))

        except Exception:
            logger.warning("Failed to fetch price history", exc_info=True)

        loaded = sum(1 for v in history.values() if v)
        logger.info("Loaded price history for %d/%d symbols", loaded, len(symbols))
        return history

    async def _fetch_data(
        self, ctx: AgentContext
    ) -> tuple[dict[str, dict[str, Any]], dict[str, SentimentInput]]:
        """Fetch market + sentiment data from database."""
        if not self._db:
            raise RuntimeError("No database client configured for StrategyEngine")

        market_data: dict[str, dict[str, Any]] = {}
        sentiment_data: dict[str, SentimentInput] = {}

        result = self._db.table("stocks").select("*").execute()

        symbols = [r.get("symbol") for r in result.data if r.get("symbol")]
        price_history = self._fetch_price_history(symbols)

        for row in result.data:
            symbol = row.get("symbol")
            if not symbol:
                continue

            market_data[symbol] = {
                "current_price": row.get("price"),
                "price_history": price_history.get(symbol, []),
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
