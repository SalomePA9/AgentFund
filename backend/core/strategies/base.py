"""
Strategy Framework Architecture

This module defines the core abstractions for the quantitative strategy system.
All strategies inherit from BaseStrategy and can integrate multiple signal types.

Architecture:
┌─────────────────────────────────────────────────────────────────────────────┐
│                            STRATEGY FRAMEWORK                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │   SIGNALS    │    │   STRATEGY   │    │    RISK      │                  │
│  │  GENERATORS  │───▶│    LOGIC     │───▶│  MANAGEMENT  │                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│         │                   │                   │                           │
│         ▼                   ▼                   ▼                           │
│  ┌──────────────────────────────────────────────────────┐                  │
│  │              PORTFOLIO CONSTRUCTION                   │                  │
│  │  (Position sizing, constraints, optimization)         │                  │
│  └──────────────────────────────────────────────────────┘                  │
│                            │                                                │
│                            ▼                                                │
│  ┌──────────────────────────────────────────────────────┐                  │
│  │              EXECUTION / ORDERS                       │                  │
│  └──────────────────────────────────────────────────────┘                  │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  SIGNAL TYPES:                                                              │
│  • Price Momentum (time-series, cross-sectional)                           │
│  • Value Factors (P/E, P/B, earnings yield)                                │
│  • Quality Factors (ROE, margins, stability)                               │
│  • Sentiment (news, social, combined)                                      │
│  • Volatility (realized, implied, term structure)                          │
│  • Technical (RSI, MACD, Bollinger, etc.)                                  │
│  • Statistical (z-scores, cointegration, correlations)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  STRATEGY TYPES:                                                            │
│  1. TrendFollowing      - Time-series momentum, managed futures style      │
│  2. CrossSectionalFactor - Multi-factor equity ranking                     │
│  3. ShortTermReversal   - Mean reversion on 1-5 day horizons              │
│  4. StatisticalArbitrage - Pairs trading, market-neutral spreads          │
│  5. VolatilityPremium   - Systematic volatility selling                    │
└─────────────────────────────────────────────────────────────────────────────┘

Sentiment Integration:
- Each strategy can optionally incorporate sentiment signals
- Sentiment can act as: filter, alpha signal, or risk adjustment
- Configurable weights and thresholds per strategy
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

# =============================================================================
# Enums and Constants
# =============================================================================


class StrategyType(str, Enum):
    """Types of trading strategies supported."""

    TREND_FOLLOWING = "trend_following"
    CROSS_SECTIONAL_FACTOR = "cross_sectional_factor"
    SHORT_TERM_REVERSAL = "short_term_reversal"
    STATISTICAL_ARBITRAGE = "statistical_arbitrage"
    VOLATILITY_PREMIUM = "volatility_premium"
    CUSTOM = "custom"


class SignalType(str, Enum):
    """Types of signals that can feed into strategies."""

    PRICE_MOMENTUM = "price_momentum"
    CROSS_SECTIONAL_MOMENTUM = "cross_sectional_momentum"
    VALUE = "value"
    QUALITY = "quality"
    LOW_VOLATILITY = "low_volatility"
    SIZE = "size"
    NEWS_SENTIMENT = "news_sentiment"
    SOCIAL_SENTIMENT = "social_sentiment"
    COMBINED_SENTIMENT = "combined_sentiment"
    SENTIMENT_VELOCITY = "sentiment_velocity"
    REALIZED_VOLATILITY = "realized_volatility"
    IMPLIED_VOLATILITY = "implied_volatility"
    VOLATILITY_TERM_STRUCTURE = "volatility_term_structure"
    TECHNICAL_RSI = "technical_rsi"
    TECHNICAL_MACD = "technical_macd"
    STATISTICAL_ZSCORE = "statistical_zscore"
    COINTEGRATION = "cointegration"
    REVERSAL = "reversal"


class PositionSide(str, Enum):
    """Position direction."""

    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class SentimentMode(str, Enum):
    """How sentiment integrates with the strategy."""

    DISABLED = "disabled"  # Don't use sentiment
    FILTER = "filter"  # Only trade when sentiment aligns
    ALPHA = "alpha"  # Use sentiment as additional signal
    RISK_ADJUSTMENT = "risk_adjust"  # Adjust position size based on sentiment
    CONFIRMATION = "confirmation"  # Require sentiment confirmation for entries


class RiskMode(str, Enum):
    """Risk management approach."""

    FIXED_FRACTION = "fixed_fraction"  # Fixed % of capital per position
    VOLATILITY_SCALED = "volatility_scaled"  # Scale by ATR/volatility
    EQUAL_RISK = "equal_risk"  # Equal risk contribution
    KELLY = "kelly"  # Kelly criterion sizing
    MAX_DRAWDOWN = "max_drawdown"  # Size to limit max drawdown


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class Signal:
    """A trading signal from a signal generator."""

    symbol: str
    signal_type: SignalType
    value: float  # Normalized signal value (-1 to 1 or 0 to 100)
    raw_value: float | None  # Original value before normalization
    confidence: float = 1.0  # Signal confidence (0 to 1)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        # Clamp value to valid range
        if self.value < -100:
            self.value = -100
        elif self.value > 100:
            self.value = 100


@dataclass
class Position:
    """A position recommendation from a strategy."""

    symbol: str
    side: PositionSide
    target_weight: float  # Target portfolio weight (0 to 1)
    signal_strength: float  # Combined signal strength
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    max_holding_days: int | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class StrategyOutput:
    """Output from strategy execution."""

    strategy_name: str
    strategy_type: StrategyType
    timestamp: datetime
    positions: list[Position]
    signals_used: list[Signal]
    risk_metrics: dict
    metadata: dict = field(default_factory=dict)


@dataclass
class SentimentConfig:
    """Configuration for sentiment integration."""

    mode: SentimentMode = SentimentMode.DISABLED
    news_weight: float = 0.4
    social_weight: float = 0.3
    velocity_weight: float = 0.3
    min_sentiment_score: float = -100  # Minimum to go long
    max_sentiment_score: float = 100  # Maximum to go short
    sentiment_filter_threshold: float = 0  # For filter mode
    sentiment_alpha_weight: float = 0.2  # Weight when used as alpha


@dataclass
class RiskConfig:
    """Configuration for risk management."""

    mode: RiskMode = RiskMode.VOLATILITY_SCALED
    max_position_size: float = 0.10  # Max 10% per position
    max_sector_exposure: float = 0.30  # Max 30% per sector
    max_portfolio_leverage: float = 1.0  # No leverage by default
    stop_loss_atr_multiple: float = 2.0  # Stop at 2x ATR
    target_volatility: float = 0.15  # 15% annual vol target
    max_drawdown_limit: float = 0.20  # 20% max drawdown
    correlation_limit: float = 0.7  # Avoid highly correlated positions


@dataclass
class StrategyConfig:
    """Base configuration for all strategies."""

    name: str
    strategy_type: StrategyType
    enabled: bool = True
    universe: list[str] = field(default_factory=list)  # Symbols to trade
    lookback_days: int = 252  # Historical data needed
    rebalance_frequency: str = "daily"  # daily, weekly, monthly
    sentiment: SentimentConfig = field(default_factory=SentimentConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    custom_params: dict = field(default_factory=dict)


# =============================================================================
# Abstract Base Classes
# =============================================================================


class SignalGenerator(ABC):
    """Base class for all signal generators."""

    @property
    @abstractmethod
    def signal_type(self) -> SignalType:
        """Return the type of signal this generator produces."""
        pass

    @abstractmethod
    async def generate(
        self, symbols: list[str], market_data: dict[str, Any], **kwargs
    ) -> list[Signal]:
        """
        Generate signals for the given symbols.

        Args:
            symbols: List of symbols to generate signals for
            market_data: Dictionary of market data keyed by symbol
            **kwargs: Additional parameters

        Returns:
            List of Signal objects
        """
        pass

    def normalize_signal(self, value: float, min_val: float, max_val: float) -> float:
        """Normalize a value to -100 to 100 range."""
        if max_val == min_val:
            return 0
        normalized = ((value - min_val) / (max_val - min_val)) * 200 - 100
        return max(-100, min(100, normalized))

    def percentile_rank(self, value: float, values: list[float]) -> float:
        """Calculate percentile rank (0 to 100)."""
        if not values:
            return 50
        below = sum(1 for v in values if v < value)
        return (below / len(values)) * 100


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    All strategies must implement:
    - generate_signals(): Produce signals from market data
    - construct_portfolio(): Convert signals to position recommendations
    """

    def __init__(self, config: StrategyConfig):
        self.config = config
        self.signal_generators: list[SignalGenerator] = []
        self._setup_signal_generators()

    @property
    @abstractmethod
    def strategy_type(self) -> StrategyType:
        """Return the strategy type."""
        pass

    @abstractmethod
    def _setup_signal_generators(self) -> None:
        """Initialize the signal generators for this strategy."""
        pass

    @abstractmethod
    async def generate_signals(
        self, market_data: dict[str, Any], sentiment_data: dict[str, Any] | None = None
    ) -> list[Signal]:
        """
        Generate trading signals from market and sentiment data.

        Args:
            market_data: Dictionary with price/fundamental data per symbol
            sentiment_data: Optional sentiment data per symbol

        Returns:
            List of Signal objects
        """
        pass

    @abstractmethod
    async def construct_portfolio(
        self,
        signals: list[Signal],
        current_positions: dict[str, Any] | None = None,
        market_data: dict[str, Any] | None = None,
    ) -> list[Position]:
        """
        Convert signals into position recommendations.

        Args:
            signals: List of signals from generate_signals()
            current_positions: Current portfolio positions (for turnover control)
            market_data: Market data dict (may contain integrated_composite scores)

        Returns:
            List of Position recommendations
        """
        pass

    async def execute(
        self,
        market_data: dict[str, Any],
        sentiment_data: dict[str, Any] | None = None,
        current_positions: dict[str, Any] | None = None,
    ) -> StrategyOutput:
        """
        Full strategy execution pipeline.

        Args:
            market_data: Market data for all symbols
            sentiment_data: Sentiment data for all symbols
            current_positions: Current portfolio state

        Returns:
            StrategyOutput with positions and metadata
        """
        # Generate signals
        signals = await self.generate_signals(market_data, sentiment_data)

        # Apply sentiment overlay if configured
        if self.config.sentiment.mode != SentimentMode.DISABLED and sentiment_data:
            signals = self._apply_sentiment_overlay(signals, sentiment_data)

        # Construct portfolio (pass market_data for integrated score access)
        positions = await self.construct_portfolio(
            signals, current_positions, market_data=market_data
        )

        # Apply risk management
        positions = self._apply_risk_management(positions, market_data)

        return StrategyOutput(
            strategy_name=self.config.name,
            strategy_type=self.strategy_type,
            timestamp=datetime.utcnow(),
            positions=positions,
            signals_used=signals,
            risk_metrics=self._calculate_risk_metrics(positions, market_data),
            metadata={
                "config": {
                    "sentiment_mode": self.config.sentiment.mode.value,
                    "risk_mode": self.config.risk.mode.value,
                }
            },
        )

    def _apply_sentiment_overlay(
        self, signals: list[Signal], sentiment_data: dict[str, Any]
    ) -> list[Signal]:
        """Apply sentiment integration based on configured mode."""
        mode = self.config.sentiment.mode
        sentiment_cfg = self.config.sentiment

        adjusted_signals = []

        for signal in signals:
            symbol = signal.symbol
            sentiment = sentiment_data.get(symbol, {})

            # Calculate combined sentiment score
            news = sentiment.get("news_sentiment", 0) or 0
            social = sentiment.get("social_sentiment", 0) or 0
            velocity = sentiment.get("sentiment_velocity", 0) or 0

            combined = (
                news * sentiment_cfg.news_weight
                + social * sentiment_cfg.social_weight
                + velocity * sentiment_cfg.velocity_weight
            )

            if mode == SentimentMode.FILTER:
                # Filter out signals that don't align with sentiment
                if (
                    signal.value > 0
                    and combined < sentiment_cfg.sentiment_filter_threshold
                ):
                    continue  # Skip bullish signal with negative sentiment
                if (
                    signal.value < 0
                    and combined > -sentiment_cfg.sentiment_filter_threshold
                ):
                    continue  # Skip bearish signal with positive sentiment

            elif mode == SentimentMode.ALPHA:
                # Add sentiment as additional signal component
                alpha_adjustment = combined * sentiment_cfg.sentiment_alpha_weight
                signal.value = (
                    signal.value * (1 - sentiment_cfg.sentiment_alpha_weight)
                    + alpha_adjustment
                )
                signal.metadata["sentiment_adjustment"] = alpha_adjustment

            elif mode == SentimentMode.RISK_ADJUSTMENT:
                # Adjust confidence based on sentiment alignment
                alignment = 1 if (signal.value * combined > 0) else -1
                signal.confidence *= 1 + alignment * 0.2  # +/- 20% confidence
                signal.metadata["sentiment_alignment"] = alignment

            elif mode == SentimentMode.CONFIRMATION:
                # Require sentiment confirmation
                if signal.value > 0 and combined <= 0:
                    signal.confidence *= 0.5  # Reduce confidence without confirmation
                elif signal.value < 0 and combined >= 0:
                    signal.confidence *= 0.5

            signal.metadata["combined_sentiment"] = combined
            adjusted_signals.append(signal)

        return adjusted_signals

    def _apply_risk_management(
        self, positions: list[Position], market_data: dict[str, Any]
    ) -> list[Position]:
        """Apply risk management rules to positions."""
        risk_cfg = self.config.risk
        adjusted_positions = []

        # Calculate total exposure
        total_long = sum(
            p.target_weight for p in positions if p.side == PositionSide.LONG
        )
        total_short = sum(
            p.target_weight for p in positions if p.side == PositionSide.SHORT
        )
        gross_exposure = total_long + total_short

        # Scale down if over leverage limit
        scale_factor = 1.0
        if gross_exposure > risk_cfg.max_portfolio_leverage:
            scale_factor = risk_cfg.max_portfolio_leverage / gross_exposure

        for pos in positions:
            # Cap individual position size
            pos.target_weight = min(pos.target_weight, risk_cfg.max_position_size)

            # Apply leverage scaling
            pos.target_weight *= scale_factor

            # Set stop loss based on ATR if available
            symbol_data = market_data.get(pos.symbol, {})
            atr = symbol_data.get("atr")
            price = symbol_data.get("current_price")

            if atr and price and pos.stop_loss is None:
                if pos.side == PositionSide.LONG:
                    pos.stop_loss = price - (atr * risk_cfg.stop_loss_atr_multiple)
                elif pos.side == PositionSide.SHORT:
                    pos.stop_loss = price + (atr * risk_cfg.stop_loss_atr_multiple)

            adjusted_positions.append(pos)

        return adjusted_positions

    def _calculate_risk_metrics(
        self, positions: list[Position], market_data: dict[str, Any]
    ) -> dict:
        """Calculate risk metrics for the portfolio."""
        total_long = sum(
            p.target_weight for p in positions if p.side == PositionSide.LONG
        )
        total_short = sum(
            p.target_weight for p in positions if p.side == PositionSide.SHORT
        )

        return {
            "gross_exposure": total_long + total_short,
            "net_exposure": total_long - total_short,
            "long_count": sum(1 for p in positions if p.side == PositionSide.LONG),
            "short_count": sum(1 for p in positions if p.side == PositionSide.SHORT),
            "avg_signal_strength": (
                sum(p.signal_strength for p in positions) / len(positions)
                if positions
                else 0
            ),
        }


# =============================================================================
# Strategy Registry
# =============================================================================


class StrategyRegistry:
    """
    Registry for strategy classes.
    Allows dynamic registration and instantiation of strategies.
    """

    _strategies: dict[StrategyType, type[BaseStrategy]] = {}

    @classmethod
    def register(cls, strategy_type: StrategyType):
        """Decorator to register a strategy class."""

        def decorator(strategy_cls: type[BaseStrategy]):
            cls._strategies[strategy_type] = strategy_cls
            return strategy_cls

        return decorator

    @classmethod
    def get(cls, strategy_type: StrategyType) -> type[BaseStrategy] | None:
        """Get a strategy class by type."""
        return cls._strategies.get(strategy_type)

    @classmethod
    def create(cls, config: StrategyConfig) -> BaseStrategy:
        """Create a strategy instance from config."""
        strategy_cls = cls._strategies.get(config.strategy_type)
        if not strategy_cls:
            raise ValueError(f"Unknown strategy type: {config.strategy_type}")
        return strategy_cls(config)

    @classmethod
    def list_strategies(cls) -> list[StrategyType]:
        """List all registered strategy types."""
        return list(cls._strategies.keys())


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Enums
    "StrategyType",
    "SignalType",
    "PositionSide",
    "SentimentMode",
    "RiskMode",
    # Data classes
    "Signal",
    "Position",
    "StrategyOutput",
    "SentimentConfig",
    "RiskConfig",
    "StrategyConfig",
    # Base classes
    "SignalGenerator",
    "BaseStrategy",
    # Registry
    "StrategyRegistry",
]
