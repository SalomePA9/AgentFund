"""
Strategy Implementations

Concrete implementations of the 5 core strategy types:
1. TrendFollowingStrategy - Time-series momentum
2. CrossSectionalFactorStrategy - Multi-factor equity ranking
3. ShortTermReversalStrategy - Mean reversion (1-5 days)
4. StatisticalArbitrageStrategy - Pairs/spread trading
5. VolatilityPremiumStrategy - Systematic vol selling

Each strategy:
- Inherits from BaseStrategy
- Configures appropriate signal generators
- Implements portfolio construction logic
- Integrates sentiment based on configuration
"""

from typing import Any

import numpy as np

from core.strategies.base import (
    BaseStrategy,
    Position,
    PositionSide,
    SentimentMode,
    Signal,
    SignalType,
    StrategyRegistry,
    StrategyType,
)
from core.strategies.signals import (
    CrossSectionalMomentumSignal,
    DividendYieldSignal,
    NewsSentimentSignal,
    QualitySignal,
    RealizedVolatilitySignal,
    SentimentVelocitySignal,
    ShortTermReversalSignal,
    SignalCombiner,
    SocialSentimentSignal,
    TimeSeriesMomentumSignal,
    ValueSignal,
    ZScoreSignal,
)

# =============================================================================
# 1. Trend Following Strategy
# =============================================================================


@StrategyRegistry.register(StrategyType.TREND_FOLLOWING)
class TrendFollowingStrategy(BaseStrategy):
    """
    Trend Following / Time-Series Momentum Strategy

    Systematically goes long assets with positive medium-term trends
    and optionally short those with negative trends.

    Key characteristics:
    - Uses time-series momentum (not cross-sectional)
    - Position sizing based on volatility (risk parity)
    - Supports multiple asset classes
    - Typically lower turnover

    Sentiment Integration:
    - FILTER: Only take long positions when sentiment is positive
    - ALPHA: Increase position size when sentiment confirms trend
    - RISK_ADJUST: Reduce position size on sentiment divergence
    """

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.TREND_FOLLOWING

    def _setup_signal_generators(self) -> None:
        params = self.config.custom_params

        self.signal_generators = [
            TimeSeriesMomentumSignal(
                lookback_days=params.get("lookback_days", 252),
                short_window=params.get("short_window", 20),
                long_window=params.get("long_window", 60),
            ),
            RealizedVolatilitySignal(lookback_days=params.get("vol_lookback", 20)),
        ]

        # Add sentiment generators if enabled
        if self.config.sentiment.mode != SentimentMode.DISABLED:
            self.signal_generators.extend(
                [
                    NewsSentimentSignal(),
                    SocialSentimentSignal(),
                    SentimentVelocitySignal(),
                ]
            )

    async def generate_signals(
        self, market_data: dict[str, Any], sentiment_data: dict[str, Any] | None = None
    ) -> list[Signal]:
        all_signals = []
        symbols = self.config.universe or list(market_data.keys())

        for generator in self.signal_generators:
            if generator.signal_type in [
                SignalType.NEWS_SENTIMENT,
                SignalType.SOCIAL_SENTIMENT,
                SignalType.SENTIMENT_VELOCITY,
            ]:
                signals = await generator.generate(
                    symbols, market_data, sentiment_data=sentiment_data
                )
            else:
                signals = await generator.generate(symbols, market_data)

            all_signals.extend(signals)

        return all_signals

    async def construct_portfolio(
        self,
        signals: list[Signal],
        current_positions: dict[str, Any] | None = None,
        market_data: dict[str, Any] | None = None,
    ) -> list[Position]:
        """
        Construct trend-following portfolio.

        Position sizing: Volatility-scaled (inverse vol weighting)
        Direction: Based on momentum signal sign
        """
        # Group signals by symbol
        momentum_signals: dict[str, Signal] = {}
        vol_signals: dict[str, Signal] = {}

        for signal in signals:
            if signal.signal_type == SignalType.PRICE_MOMENTUM:
                momentum_signals[signal.symbol] = signal
            elif signal.signal_type == SignalType.REALIZED_VOLATILITY:
                vol_signals[signal.symbol] = signal

        positions = []
        params = self.config.custom_params
        min_signal = params.get("min_signal_strength", 20)
        allow_short = params.get("allow_short", False)
        max_holding = params.get("max_holding_days", 90)  # ~1 quarter

        for symbol, mom_signal in momentum_signals.items():
            # Skip weak signals
            if abs(mom_signal.value) < min_signal:
                continue

            # Determine direction
            if mom_signal.value > 0:
                side = PositionSide.LONG
            elif allow_short and mom_signal.value < 0:
                side = PositionSide.SHORT
            else:
                continue

            # Calculate volatility-scaled weight
            vol_signal = vol_signals.get(symbol)
            if vol_signal and vol_signal.metadata.get("annualized_volatility"):
                vol = vol_signal.metadata["annualized_volatility"]
                # Target 15% vol, scale inversely
                target_vol = self.config.risk.target_volatility
                weight = (target_vol / vol) * (abs(mom_signal.value) / 100)
            else:
                weight = abs(mom_signal.value) / 100 * 0.05  # Default 5% base

            # Cap at max position size
            weight = min(weight, self.config.risk.max_position_size)

            positions.append(
                Position(
                    symbol=symbol,
                    side=side,
                    target_weight=weight,
                    signal_strength=abs(mom_signal.value),
                    max_holding_days=max_holding,
                    metadata={
                        "strategy": "trend_following",
                        "momentum_signal": mom_signal.value,
                        "trend_score": mom_signal.metadata.get("trend_score"),
                    },
                )
            )

        # Apply hysteresis to reduce whipsaw from MA crossover flips
        hysteresis_band = params.get("hysteresis_band", 5.0)
        positions = self._apply_hysteresis(
            positions, current_positions, hysteresis_band
        )

        return positions


# =============================================================================
# 2. Cross-Sectional Factor Strategy
# =============================================================================


@StrategyRegistry.register(StrategyType.CROSS_SECTIONAL_FACTOR)
class CrossSectionalFactorStrategy(BaseStrategy):
    """
    Cross-Sectional Equity Factor Strategy

    Ranks stocks by multiple factors and constructs long/short portfolios
    based on relative rankings.

    Factors:
    - Momentum (6-12 month returns)
    - Value (P/E, P/B)
    - Quality (ROE, margins, stability)
    - Low Volatility (optional)

    Sentiment Integration:
    - FILTER: Exclude stocks with extreme negative sentiment from longs
    - ALPHA: Add sentiment as an additional factor with configurable weight
    - CONFIRMATION: Require sentiment alignment for top decile positions
    """

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.CROSS_SECTIONAL_FACTOR

    def _setup_signal_generators(self) -> None:
        params = self.config.custom_params

        # Factor weights
        factors = params.get(
            "factors",
            {
                "momentum": 0.3,
                "value": 0.3,
                "quality": 0.3,
                "low_vol": 0.1,
            },
        )

        self.signal_generators = []
        self.factor_weights = {}

        if factors.get("momentum", 0) > 0:
            self.signal_generators.append(
                CrossSectionalMomentumSignal(
                    lookback_days=params.get("momentum_lookback", 126)
                )
            )
            self.factor_weights[SignalType.CROSS_SECTIONAL_MOMENTUM] = factors[
                "momentum"
            ]

        if factors.get("value", 0) > 0:
            self.signal_generators.append(ValueSignal())
            self.factor_weights[SignalType.VALUE] = factors["value"]

        if factors.get("quality", 0) > 0:
            self.signal_generators.append(QualitySignal())
            self.factor_weights[SignalType.QUALITY] = factors["quality"]

        if factors.get("low_vol", 0) > 0:
            self.signal_generators.append(RealizedVolatilitySignal())
            self.factor_weights[SignalType.REALIZED_VOLATILITY] = factors["low_vol"]

        if factors.get("dividend", 0) > 0:
            self.signal_generators.append(
                DividendYieldSignal(min_yield=params.get("min_dividend_yield", 0.0))
            )
            self.factor_weights[SignalType.DIVIDEND_YIELD] = factors["dividend"]

        # Add sentiment if enabled
        if self.config.sentiment.mode == SentimentMode.ALPHA:
            sentiment_weight = self.config.sentiment.sentiment_alpha_weight
            self.signal_generators.extend(
                [
                    NewsSentimentSignal(),
                    SocialSentimentSignal(),
                ]
            )
            self.factor_weights[SignalType.NEWS_SENTIMENT] = sentiment_weight / 2
            self.factor_weights[SignalType.SOCIAL_SENTIMENT] = sentiment_weight / 2

    async def generate_signals(
        self, market_data: dict[str, Any], sentiment_data: dict[str, Any] | None = None
    ) -> list[Signal]:
        all_signals = []
        symbols = self.config.universe or list(market_data.keys())

        for generator in self.signal_generators:
            if generator.signal_type in [
                SignalType.NEWS_SENTIMENT,
                SignalType.SOCIAL_SENTIMENT,
            ]:
                signals = await generator.generate(
                    symbols, market_data, sentiment_data=sentiment_data
                )
            else:
                signals = await generator.generate(symbols, market_data)

            all_signals.extend(signals)

        return all_signals

    async def construct_portfolio(
        self,
        signals: list[Signal],
        current_positions: dict[str, Any] | None = None,
        market_data: dict[str, Any] | None = None,
    ) -> list[Position]:
        """
        Construct factor portfolio.

        Uses weighted composite score to rank stocks.  When the engine has
        pre-computed integrated composite scores (via SentimentFactorIntegrator),
        those are blended in to give sentiment-aware ranking.
        Takes top N% long, bottom N% short (if enabled).
        """
        params = self.config.custom_params
        top_pct = params.get("top_percentile", 20)  # Top 20%
        bottom_pct = params.get("bottom_percentile", 20)
        allow_short = params.get("allow_short", False)
        equal_weight = params.get("equal_weight", True)
        max_holding = params.get("max_holding_days", 180)  # ~2 quarters
        market_data = market_data or {}

        # Combine signals from signal generators
        combiner = SignalCombiner(weights=self.factor_weights)
        combined_scores = combiner.combine(signals, method="weighted_average")

        if not combined_scores:
            return []

        # Blend with pre-computed integrated composite scores when available.
        # Integrated scores are on a 0-100 scale; signal combiner scores are
        # on a -100 to +100 scale.  Normalise integrated to the same range
        # and blend at 40% weight so the 7-layer integration meaningfully
        # influences final ranking without completely overriding signals.
        integrated_weight = 0.4
        for sym in list(combined_scores.keys()):
            ic = (market_data.get(sym) or {}).get("integrated_composite")
            if ic is not None:
                # Convert 0-100 → -100 to +100
                ic_normalised = (ic - 50.0) * 2.0
                combined_scores[sym] = (
                    combined_scores[sym] * (1.0 - integrated_weight)
                    + ic_normalised * integrated_weight
                )

        # Turnover hysteresis: give currently-held positions a stickiness
        # bonus so they aren't replaced unless a new candidate outscores
        # them by at least `hysteresis_band` points.  This prevents
        # unnecessary churn and implicit transaction costs.
        hysteresis_band = params.get("hysteresis_band", 5.0)
        current_positions = current_positions or {}

        ranking_scores = dict(combined_scores)
        for sym in ranking_scores:
            if sym in current_positions:
                ranking_scores[sym] += hysteresis_band

        # Rank and select
        sorted_symbols = sorted(
            ranking_scores.keys(), key=lambda s: ranking_scores[s], reverse=True
        )

        n = len(sorted_symbols)
        n_long = max(1, int(n * top_pct / 100))
        n_short = max(1, int(n * bottom_pct / 100)) if allow_short else 0

        # Honour top_n (set by engine from agent's max_positions) as a hard cap
        top_n = params.get("top_n")
        if top_n is not None:
            n_long = min(n_long, int(top_n))

        positions = []

        # Long positions (top ranked)
        long_symbols = sorted_symbols[:n_long]
        long_weight = (
            self.config.risk.max_position_size
            if not equal_weight
            else (min(1.0 / n_long, self.config.risk.max_position_size))
        )

        for symbol in long_symbols:
            score = combined_scores[symbol]
            weight = (
                long_weight
                if equal_weight
                else (long_weight * (score + 100) / 200)  # Scale by score
            )

            positions.append(
                Position(
                    symbol=symbol,
                    side=PositionSide.LONG,
                    target_weight=weight,
                    signal_strength=score,
                    max_holding_days=max_holding,
                    metadata={
                        "strategy": "cross_sectional_factor",
                        "composite_score": score,
                        "rank": sorted_symbols.index(symbol) + 1,
                    },
                )
            )

        # Short positions (bottom ranked)
        if allow_short:
            short_symbols = sorted_symbols[-n_short:]
            short_weight = (
                self.config.risk.max_position_size
                if not equal_weight
                else (min(1.0 / n_short, self.config.risk.max_position_size))
            )

            for symbol in short_symbols:
                score = combined_scores[symbol]
                weight = (
                    short_weight
                    if equal_weight
                    else (short_weight * (100 - score) / 200)
                )

                positions.append(
                    Position(
                        symbol=symbol,
                        side=PositionSide.SHORT,
                        target_weight=weight,
                        signal_strength=abs(score),
                        max_holding_days=max_holding,
                        metadata={
                            "strategy": "cross_sectional_factor",
                            "composite_score": score,
                            "rank": sorted_symbols.index(symbol) + 1,
                        },
                    )
                )

        return positions


# =============================================================================
# 3. Short-Term Reversal Strategy
# =============================================================================


@StrategyRegistry.register(StrategyType.SHORT_TERM_REVERSAL)
class ShortTermReversalStrategy(BaseStrategy):
    """
    Short-Term Reversal Strategy

    Exploits short-horizon price overreaction by buying recent losers
    and selling recent winners (1-5 day horizon).

    Key characteristics:
    - Captures liquidity shocks and forced trading effects
    - High turnover, requires low transaction costs
    - Best run market-neutral

    Sentiment Integration:
    - FILTER: Avoid reversals in stocks with momentum in sentiment
    - RISK_ADJUST: Reduce size when sentiment is extreme (might not reverse)
    - CONFIRMATION: Only trade reversals when sentiment is mean-reverting too
    """

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.SHORT_TERM_REVERSAL

    def _setup_signal_generators(self) -> None:
        params = self.config.custom_params

        self.signal_generators = [
            ShortTermReversalSignal(lookback_days=params.get("lookback_days", 5)),
            RealizedVolatilitySignal(lookback_days=params.get("vol_lookback", 20)),
        ]

        if self.config.sentiment.mode != SentimentMode.DISABLED:
            self.signal_generators.append(SentimentVelocitySignal())

    async def generate_signals(
        self, market_data: dict[str, Any], sentiment_data: dict[str, Any] | None = None
    ) -> list[Signal]:
        all_signals = []
        symbols = self.config.universe or list(market_data.keys())

        for generator in self.signal_generators:
            if generator.signal_type == SignalType.SENTIMENT_VELOCITY:
                signals = await generator.generate(
                    symbols, market_data, sentiment_data=sentiment_data
                )
            else:
                signals = await generator.generate(symbols, market_data)

            all_signals.extend(signals)

        return all_signals

    async def construct_portfolio(
        self,
        signals: list[Signal],
        current_positions: dict[str, Any] | None = None,
        market_data: dict[str, Any] | None = None,
    ) -> list[Position]:
        """
        Construct reversal portfolio.

        Buys oversold stocks (negative short-term return)
        Sells overbought stocks (positive short-term return)
        """
        params = self.config.custom_params
        min_zscore = params.get("min_zscore", 1.5)  # Minimum z-score to trade
        holding_days = params.get("holding_days", 5)
        market_neutral = params.get("market_neutral", True)

        reversal_signals: dict[str, Signal] = {}
        vol_signals: dict[str, Signal] = {}
        sentiment_signals: dict[str, Signal] = {}

        for signal in signals:
            if signal.signal_type == SignalType.REVERSAL:
                reversal_signals[signal.symbol] = signal
            elif signal.signal_type == SignalType.REALIZED_VOLATILITY:
                vol_signals[signal.symbol] = signal
            elif signal.signal_type == SignalType.SENTIMENT_VELOCITY:
                sentiment_signals[signal.symbol] = signal

        positions = []

        for symbol, rev_signal in reversal_signals.items():
            z_score = abs(rev_signal.metadata.get("z_score", 0))

            # Skip if z-score not extreme enough
            if z_score < min_zscore:
                continue

            # Check sentiment velocity for confirmation/filter
            sent_signal = sentiment_signals.get(symbol)
            if self.config.sentiment.mode == SentimentMode.CONFIRMATION:
                if sent_signal:
                    # Require sentiment moving in same direction as expected reversal
                    price_reversal_dir = 1 if rev_signal.value > 0 else -1
                    sent_dir = 1 if sent_signal.value > 0 else -1
                    if price_reversal_dir != sent_dir:
                        continue  # Skip if sentiment not confirming

            # Determine side (reversal signal is already inverted)
            if rev_signal.value > 0:
                side = PositionSide.LONG  # Oversold, expect bounce
            else:
                side = PositionSide.SHORT  # Overbought, expect pullback

            # Size based on z-score magnitude
            weight = min(
                z_score / 5 * 0.05,  # Scale by extremity
                self.config.risk.max_position_size,
            )

            positions.append(
                Position(
                    symbol=symbol,
                    side=side,
                    target_weight=weight,
                    signal_strength=abs(rev_signal.value),
                    max_holding_days=holding_days,
                    metadata={
                        "strategy": "short_term_reversal",
                        "z_score": rev_signal.metadata.get("z_score"),
                        "short_term_return": rev_signal.raw_value,
                    },
                )
            )

        # Apply hysteresis to reduce churn in short-horizon signals
        hysteresis_band = params.get("hysteresis_band", 3.0)
        positions = self._apply_hysteresis(
            positions, current_positions, hysteresis_band
        )

        # Balance for market neutrality if required
        if market_neutral:
            positions = self._balance_market_neutral(positions)

        return positions

    def _balance_market_neutral(self, positions: list[Position]) -> list[Position]:
        """Adjust weights to achieve market neutrality."""
        long_weight = sum(
            p.target_weight for p in positions if p.side == PositionSide.LONG
        )
        short_weight = sum(
            p.target_weight for p in positions if p.side == PositionSide.SHORT
        )

        if long_weight == 0 or short_weight == 0:
            return positions

        # Scale to balance
        target = min(long_weight, short_weight)

        for pos in positions:
            if pos.side == PositionSide.LONG:
                pos.target_weight *= target / long_weight
            else:
                pos.target_weight *= target / short_weight

        return positions


# =============================================================================
# 4. Statistical Arbitrage Strategy
# =============================================================================


@StrategyRegistry.register(StrategyType.STATISTICAL_ARBITRAGE)
class StatisticalArbitrageStrategy(BaseStrategy):
    """
    Statistical Arbitrage Strategy

    Exploits relative mispricings between related securities using
    statistical methods (z-scores, cointegration).

    Key characteristics:
    - Market-neutral by design
    - Trades spreads, not outright positions
    - Requires constant model refinement

    Sentiment Integration:
    - ALPHA: Use sentiment divergence between pair members as additional signal
    - FILTER: Avoid pairs where sentiment is trending (not mean-reverting)
    """

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.STATISTICAL_ARBITRAGE

    def _setup_signal_generators(self) -> None:
        params = self.config.custom_params

        self.signal_generators = [
            ZScoreSignal(lookback_days=params.get("zscore_lookback", 60)),
            RealizedVolatilitySignal(lookback_days=params.get("vol_lookback", 20)),
        ]

        if self.config.sentiment.mode == SentimentMode.ALPHA:
            self.signal_generators.extend(
                [
                    NewsSentimentSignal(),
                    SocialSentimentSignal(),
                ]
            )

    async def generate_signals(
        self, market_data: dict[str, Any], sentiment_data: dict[str, Any] | None = None
    ) -> list[Signal]:
        all_signals = []
        symbols = self.config.universe or list(market_data.keys())

        for generator in self.signal_generators:
            if generator.signal_type in [
                SignalType.NEWS_SENTIMENT,
                SignalType.SOCIAL_SENTIMENT,
            ]:
                signals = await generator.generate(
                    symbols, market_data, sentiment_data=sentiment_data
                )
            else:
                signals = await generator.generate(symbols, market_data)

            all_signals.extend(signals)

        return all_signals

    async def construct_portfolio(
        self,
        signals: list[Signal],
        current_positions: dict[str, Any] | None = None,
        market_data: dict[str, Any] | None = None,
    ) -> list[Position]:
        """
        Construct stat arb portfolio.

        Uses z-scores to identify mean-reverting opportunities.
        Can trade individual securities or pairs (if pairs defined in config).
        """
        params = self.config.custom_params
        min_zscore = params.get("min_zscore", 2.0)
        max_zscore = params.get("max_zscore", 4.0)  # Avoid extreme outliers
        pairs = params.get("pairs", [])  # List of (symbol1, symbol2) tuples
        max_holding = params.get("max_holding_days", 30)  # ~1 month convergence

        zscore_signals: dict[str, Signal] = {}
        sentiment_signals: dict[str, Signal] = {}

        for signal in signals:
            if signal.signal_type == SignalType.STATISTICAL_ZSCORE:
                zscore_signals[signal.symbol] = signal
            elif signal.signal_type in [
                SignalType.NEWS_SENTIMENT,
                SignalType.SOCIAL_SENTIMENT,
            ]:
                if signal.symbol not in sentiment_signals:
                    sentiment_signals[signal.symbol] = signal

        positions = []

        if pairs:
            # Pairs trading mode
            for sym1, sym2 in pairs:
                z1 = zscore_signals.get(sym1)
                z2 = zscore_signals.get(sym2)

                if not z1 or not z2:
                    continue

                # Calculate spread z-score
                spread_z = z1.metadata.get("z_score", 0) - z2.metadata.get("z_score", 0)

                if abs(spread_z) >= min_zscore and abs(spread_z) <= max_zscore:
                    weight = min(abs(spread_z) / 10, self.config.risk.max_position_size)

                    if spread_z > 0:
                        # Spread too high: short sym1, long sym2
                        positions.append(
                            Position(
                                symbol=sym1,
                                side=PositionSide.SHORT,
                                target_weight=weight,
                                signal_strength=abs(spread_z) * 25,
                                metadata={"pair": (sym1, sym2), "spread_z": spread_z},
                            )
                        )
                        positions.append(
                            Position(
                                symbol=sym2,
                                side=PositionSide.LONG,
                                target_weight=weight,
                                signal_strength=abs(spread_z) * 25,
                                metadata={"pair": (sym1, sym2), "spread_z": spread_z},
                            )
                        )
                    else:
                        # Spread too low: long sym1, short sym2
                        positions.append(
                            Position(
                                symbol=sym1,
                                side=PositionSide.LONG,
                                target_weight=weight,
                                signal_strength=abs(spread_z) * 25,
                                metadata={"pair": (sym1, sym2), "spread_z": spread_z},
                            )
                        )
                        positions.append(
                            Position(
                                symbol=sym2,
                                side=PositionSide.SHORT,
                                target_weight=weight,
                                signal_strength=abs(spread_z) * 25,
                                metadata={"pair": (sym1, sym2), "spread_z": spread_z},
                            )
                        )

        else:
            # Individual z-score mode
            for symbol, z_signal in zscore_signals.items():
                z = z_signal.metadata.get("z_score", 0)

                if abs(z) >= min_zscore and abs(z) <= max_zscore:
                    # Mean reversion: buy when z is negative, sell when positive
                    side = PositionSide.LONG if z < 0 else PositionSide.SHORT
                    weight = min(abs(z) / 10, self.config.risk.max_position_size)

                    positions.append(
                        Position(
                            symbol=symbol,
                            side=side,
                            target_weight=weight,
                            signal_strength=abs(z_signal.value),
                            max_holding_days=max_holding,
                            metadata={
                                "strategy": "statistical_arbitrage",
                                "z_score": z,
                            },
                        )
                    )

        # Apply hysteresis
        hysteresis_band = params.get("hysteresis_band", 4.0)
        positions = self._apply_hysteresis(
            positions, current_positions, hysteresis_band
        )

        return positions


# =============================================================================
# 5. Volatility Premium Strategy
# =============================================================================


@StrategyRegistry.register(StrategyType.VOLATILITY_PREMIUM)
class VolatilityPremiumStrategy(BaseStrategy):
    """
    Volatility Risk Premium Strategy

    Systematically sells insurance (implied volatility) and manages
    tail risk through hedging or diversification.

    Key characteristics:
    - Earns premium from risk-averse investors
    - Requires strict risk controls
    - Can blow up without proper hedging

    Sentiment Integration:
    - FILTER: Avoid selling vol when sentiment is extremely negative (crisis risk)
    - RISK_ADJUST: Reduce exposure when sentiment volatility is high
    """

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.VOLATILITY_PREMIUM

    def _setup_signal_generators(self) -> None:
        params = self.config.custom_params

        self.signal_generators = [
            RealizedVolatilitySignal(lookback_days=params.get("vol_lookback", 20)),
        ]

        if self.config.sentiment.mode != SentimentMode.DISABLED:
            self.signal_generators.extend(
                [
                    NewsSentimentSignal(),
                    SentimentVelocitySignal(),
                ]
            )

    async def generate_signals(
        self, market_data: dict[str, Any], sentiment_data: dict[str, Any] | None = None
    ) -> list[Signal]:
        all_signals = []
        symbols = self.config.universe or list(market_data.keys())

        for generator in self.signal_generators:
            if generator.signal_type in [
                SignalType.NEWS_SENTIMENT,
                SignalType.SENTIMENT_VELOCITY,
            ]:
                signals = await generator.generate(
                    symbols, market_data, sentiment_data=sentiment_data
                )
            else:
                signals = await generator.generate(symbols, market_data)

            all_signals.extend(signals)

        return all_signals

    async def construct_portfolio(
        self,
        signals: list[Signal],
        current_positions: dict[str, Any] | None = None,
        market_data: dict[str, Any] | None = None,
    ) -> list[Position]:
        """
        Construct vol premium portfolio.

        For equities (without options), this translates to:
        - Long low-vol stocks (they benefit from volatility selling)
        - Short high-vol stocks (optional)

        Note: Full vol premium requires options trading capabilities.
        This implementation focuses on the equity proxy.
        """
        params = self.config.custom_params
        low_vol_only = params.get("low_vol_only", True)
        vol_threshold_pct = params.get("vol_threshold_percentile", 30)  # Bottom 30%
        max_holding = params.get("max_holding_days", 120)  # ~1 quarter for vol prem
        sentiment_filter = params.get("sentiment_crisis_threshold", -50)

        vol_signals: dict[str, Signal] = {}
        sentiment_signals: dict[str, Signal] = {}

        for signal in signals:
            if signal.signal_type == SignalType.REALIZED_VOLATILITY:
                vol_signals[signal.symbol] = signal
            elif signal.signal_type == SignalType.NEWS_SENTIMENT:
                sentiment_signals[signal.symbol] = signal

        if not vol_signals:
            return []

        # Check for crisis mode (very negative aggregate sentiment)
        if self.config.sentiment.mode == SentimentMode.FILTER and sentiment_signals:
            avg_sentiment = np.mean([s.value for s in sentiment_signals.values()])
            if avg_sentiment < sentiment_filter:
                # Crisis mode: don't sell vol
                return []

        # Rank by volatility
        sorted_by_vol = sorted(
            vol_signals.items(),
            key=lambda x: x[1].metadata.get("annualized_volatility", float("inf")),
        )

        n = len(sorted_by_vol)
        n_low = max(1, int(n * vol_threshold_pct / 100))

        positions = []

        # Long low-vol stocks (vol premium proxy)
        for symbol, vol_signal in sorted_by_vol[:n_low]:
            vol = vol_signal.metadata.get("annualized_volatility", 0.2)

            # Size inversely to volatility
            weight = min(
                self.config.risk.target_volatility / vol * 0.1,
                self.config.risk.max_position_size,
            )

            positions.append(
                Position(
                    symbol=symbol,
                    side=PositionSide.LONG,
                    target_weight=weight,
                    signal_strength=vol_signal.value,
                    max_holding_days=max_holding,
                    metadata={
                        "strategy": "volatility_premium",
                        "annualized_volatility": vol,
                        "vol_rank": sorted_by_vol.index((symbol, vol_signal)) + 1,
                    },
                )
            )

        # Optionally short high-vol stocks
        if not low_vol_only:
            n_high = max(1, int(n * vol_threshold_pct / 100))
            for symbol, vol_signal in sorted_by_vol[-n_high:]:
                vol = vol_signal.metadata.get("annualized_volatility", 0.2)

                weight = min(
                    self.config.risk.target_volatility / vol * 0.05,
                    self.config.risk.max_position_size * 0.5,
                )

                positions.append(
                    Position(
                        symbol=symbol,
                        side=PositionSide.SHORT,
                        target_weight=weight,
                        signal_strength=abs(vol_signal.value),
                        metadata={
                            "strategy": "volatility_premium",
                            "annualized_volatility": vol,
                            "vol_rank": sorted_by_vol.index((symbol, vol_signal)) + 1,
                        },
                    )
                )

        # Apply hysteresis — vol premium is a low-turnover strategy
        hysteresis_band = params.get("hysteresis_band", 6.0)
        positions = self._apply_hysteresis(
            positions, current_positions, hysteresis_band
        )

        return positions


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "TrendFollowingStrategy",
    "CrossSectionalFactorStrategy",
    "ShortTermReversalStrategy",
    "StatisticalArbitrageStrategy",
    "VolatilityPremiumStrategy",
]
