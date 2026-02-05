"""
Strategy Framework

Extensible framework for implementing quantitative trading strategies.

Usage:
    from core.strategies import (
        StrategyRegistry,
        StrategyConfig,
        StrategyType,
        SentimentMode,
        SentimentConfig,
    )

    # Create a trend following strategy with sentiment filtering
    config = StrategyConfig(
        name="My Trend Strategy",
        strategy_type=StrategyType.TREND_FOLLOWING,
        universe=["AAPL", "MSFT", "GOOGL"],
        sentiment=SentimentConfig(
            mode=SentimentMode.FILTER,
            news_weight=0.5,
            social_weight=0.3,
            velocity_weight=0.2,
        ),
        custom_params={
            "lookback_days": 200,
            "allow_short": False,
        }
    )

    # Create strategy instance
    strategy = StrategyRegistry.create(config)

    # Execute strategy
    output = await strategy.execute(market_data, sentiment_data)

Available Strategies:
    1. TREND_FOLLOWING - Time-series momentum
    2. CROSS_SECTIONAL_FACTOR - Multi-factor equity ranking
    3. SHORT_TERM_REVERSAL - Mean reversion (1-5 days)
    4. STATISTICAL_ARBITRAGE - Pairs/spread trading
    5. VOLATILITY_PREMIUM - Systematic vol selling

Sentiment Integration Modes:
    - DISABLED: No sentiment integration
    - FILTER: Only trade when sentiment aligns
    - ALPHA: Use sentiment as additional signal factor
    - RISK_ADJUSTMENT: Adjust position size based on sentiment
    - CONFIRMATION: Require sentiment confirmation for entries
"""

# Base classes and types
from core.strategies.base import (
    # Enums
    StrategyType,
    SignalType,
    PositionSide,
    SentimentMode,
    RiskMode,
    # Data classes
    Signal,
    Position,
    StrategyOutput,
    SentimentConfig,
    RiskConfig,
    StrategyConfig,
    # Base classes
    SignalGenerator,
    BaseStrategy,
    # Registry
    StrategyRegistry,
)

# Signal generators
from core.strategies.signals import (
    TimeSeriesMomentumSignal,
    CrossSectionalMomentumSignal,
    ValueSignal,
    QualitySignal,
    DividendYieldSignal,
    NewsSentimentSignal,
    SocialSentimentSignal,
    SentimentVelocitySignal,
    RealizedVolatilitySignal,
    ShortTermReversalSignal,
    ZScoreSignal,
    SignalCombiner,
)

# Strategy implementations
from core.strategies.implementations import (
    TrendFollowingStrategy,
    CrossSectionalFactorStrategy,
    ShortTermReversalStrategy,
    StatisticalArbitrageStrategy,
    VolatilityPremiumStrategy,
)

# Strategy presets (pre-configured strategies)
from core.strategies.presets import (
    # Original 4 strategies
    momentum_strategy,
    quality_value_strategy,
    quality_momentum_strategy,
    dividend_growth_strategy,
    # Advanced 5 strategies
    trend_following_strategy,
    short_term_reversal_strategy,
    statistical_arbitrage_strategy,
    volatility_premium_strategy,
    # Registry
    STRATEGY_PRESETS,
    get_preset,
    list_presets,
)


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
    "StrategyRegistry",
    # Signal generators
    "TimeSeriesMomentumSignal",
    "CrossSectionalMomentumSignal",
    "ValueSignal",
    "QualitySignal",
    "DividendYieldSignal",
    "NewsSentimentSignal",
    "SocialSentimentSignal",
    "SentimentVelocitySignal",
    "RealizedVolatilitySignal",
    "ShortTermReversalSignal",
    "ZScoreSignal",
    "SignalCombiner",
    # Strategy implementations
    "TrendFollowingStrategy",
    "CrossSectionalFactorStrategy",
    "ShortTermReversalStrategy",
    "StatisticalArbitrageStrategy",
    "VolatilityPremiumStrategy",
    # Strategy presets
    "momentum_strategy",
    "quality_value_strategy",
    "quality_momentum_strategy",
    "dividend_growth_strategy",
    "trend_following_strategy",
    "short_term_reversal_strategy",
    "statistical_arbitrage_strategy",
    "volatility_premium_strategy",
    "STRATEGY_PRESETS",
    "get_preset",
    "list_presets",
]
