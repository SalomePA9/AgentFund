"""
Strategy Presets

Pre-configured strategy configurations for common use cases.
These map to the original 4 strategies from the product spec
plus the 5 advanced quant strategies.

Original Strategies (user-facing, simpler):
1. Momentum - Pure price momentum
2. Quality Value - Value stocks with quality filters
3. Quality Momentum - Momentum with quality overlay
4. Dividend Growth - Dividend yield with quality/growth

Advanced Strategies (for power users):
5. Trend Following - Time-series momentum (managed futures style)
6. Cross-Sectional Factor - Multi-factor with custom weights
7. Short-Term Reversal - Mean reversion (1-5 days)
8. Statistical Arbitrage - Pairs/market-neutral
9. Volatility Premium - Low-vol / vol selling proxy
"""

from core.strategies.base import (
    RiskConfig,
    RiskMode,
    SentimentConfig,
    SentimentMode,
    StrategyConfig,
    StrategyType,
)


# =============================================================================
# Original 4 Strategies (Simple Presets)
# =============================================================================

def momentum_strategy(
    name: str = "Momentum",
    universe: list[str] = None,
    sentiment_mode: SentimentMode = SentimentMode.FILTER,
    allow_short: bool = False,
    top_percentile: int = 20,
) -> StrategyConfig:
    """
    Momentum Strategy

    Buy stocks with strong recent price performance.
    Classic momentum factor - captures trending behavior.

    Benefits:
    - Historically strong risk-adjusted returns
    - Works across asset classes and time periods
    - Easy to understand and explain

    Signal Enhancement:
    - Sentiment FILTER: Only buy momentum winners with positive sentiment
    - Sentiment ALPHA: Boost rankings for stocks with improving sentiment
    - Avoids momentum crashes by filtering negative sentiment

    Best for: Growth-oriented investors, trending markets
    """
    return StrategyConfig(
        name=name,
        strategy_type=StrategyType.CROSS_SECTIONAL_FACTOR,
        universe=universe or [],
        sentiment=SentimentConfig(
            mode=sentiment_mode,
            news_weight=0.4,
            social_weight=0.3,
            velocity_weight=0.3,
            sentiment_filter_threshold=0,  # Require non-negative sentiment
        ),
        risk=RiskConfig(
            mode=RiskMode.VOLATILITY_SCALED,
            max_position_size=0.05,
            target_volatility=0.15,
            stop_loss_atr_multiple=2.0,
        ),
        custom_params={
            "factors": {
                "momentum": 1.0,  # Pure momentum
                "value": 0.0,
                "quality": 0.0,
                "low_vol": 0.0,
            },
            "momentum_lookback": 126,  # 6 months
            "top_percentile": top_percentile,
            "allow_short": allow_short,
            "equal_weight": True,
        }
    )


def quality_value_strategy(
    name: str = "Quality Value",
    universe: list[str] = None,
    sentiment_mode: SentimentMode = SentimentMode.CONFIRMATION,
    allow_short: bool = False,
    top_percentile: int = 20,
) -> StrategyConfig:
    """
    Quality Value Strategy

    Buy cheap stocks (low P/E, P/B) that also have quality characteristics
    (high ROE, stable margins, low debt).

    Benefits:
    - Value provides margin of safety
    - Quality filter avoids "value traps"
    - Lower volatility than pure value
    - Strong long-term compounding

    Signal Enhancement:
    - Sentiment CONFIRMATION: Ensure sentiment isn't deteriorating (value trap signal)
    - Sentiment ALPHA: Favor undervalued stocks with improving sentiment
    - Sentiment velocity helps detect turnaround opportunities

    Best for: Conservative investors, long-term holders
    """
    return StrategyConfig(
        name=name,
        strategy_type=StrategyType.CROSS_SECTIONAL_FACTOR,
        universe=universe or [],
        sentiment=SentimentConfig(
            mode=sentiment_mode,
            news_weight=0.5,
            social_weight=0.2,
            velocity_weight=0.3,  # Velocity important for turnarounds
        ),
        risk=RiskConfig(
            mode=RiskMode.EQUAL_RISK,
            max_position_size=0.05,
            target_volatility=0.12,  # Lower vol target
            stop_loss_atr_multiple=2.5,
        ),
        custom_params={
            "factors": {
                "momentum": 0.0,
                "value": 0.5,
                "quality": 0.5,
                "low_vol": 0.0,
            },
            "top_percentile": top_percentile,
            "allow_short": allow_short,
            "equal_weight": True,
        }
    )


def quality_momentum_strategy(
    name: str = "Quality Momentum",
    universe: list[str] = None,
    sentiment_mode: SentimentMode = SentimentMode.ALPHA,
    allow_short: bool = False,
    top_percentile: int = 20,
) -> StrategyConfig:
    """
    Quality Momentum Strategy

    Buy stocks with strong momentum that also have quality fundamentals.
    Combines trend-following with fundamental validation.

    Benefits:
    - Momentum for timing, quality for safety
    - Avoids low-quality "lottery stocks"
    - Better risk-adjusted returns than pure momentum
    - Quality acts as a momentum crash hedge

    Signal Enhancement:
    - Sentiment ALPHA: Add sentiment as third factor for ranking
    - Sentiment velocity confirms momentum continuation
    - Negative sentiment divergence = early exit signal

    Best for: Active investors, GARP (Growth at Reasonable Price) approach
    """
    return StrategyConfig(
        name=name,
        strategy_type=StrategyType.CROSS_SECTIONAL_FACTOR,
        universe=universe or [],
        sentiment=SentimentConfig(
            mode=sentiment_mode,
            news_weight=0.4,
            social_weight=0.3,
            velocity_weight=0.3,
            sentiment_alpha_weight=0.15,  # 15% weight to sentiment
        ),
        risk=RiskConfig(
            mode=RiskMode.VOLATILITY_SCALED,
            max_position_size=0.05,
            target_volatility=0.15,
            stop_loss_atr_multiple=2.0,
        ),
        custom_params={
            "factors": {
                "momentum": 0.5,
                "value": 0.0,
                "quality": 0.5,
                "low_vol": 0.0,
            },
            "momentum_lookback": 126,
            "top_percentile": top_percentile,
            "allow_short": allow_short,
            "equal_weight": True,
        }
    )


def dividend_growth_strategy(
    name: str = "Dividend Growth",
    universe: list[str] = None,
    sentiment_mode: SentimentMode = SentimentMode.FILTER,
    min_yield: float = 0.02,  # 2% minimum yield
    top_percentile: int = 25,
) -> StrategyConfig:
    """
    Dividend Growth Strategy

    Buy stocks with solid dividend yields that also show
    quality characteristics (sustainable payouts, growing earnings).

    Benefits:
    - Income generation for cash flow
    - Dividend growth compounds returns
    - Quality filter ensures dividend safety
    - Lower volatility, defensive characteristics

    Signal Enhancement:
    - Sentiment FILTER: Avoid dividend stocks with negative sentiment (cut risk)
    - Positive sentiment = less likely to cut dividend
    - Sentiment velocity warns of deteriorating fundamentals

    Best for: Income investors, retirees, conservative portfolios
    """
    return StrategyConfig(
        name=name,
        strategy_type=StrategyType.CROSS_SECTIONAL_FACTOR,
        universe=universe or [],
        sentiment=SentimentConfig(
            mode=sentiment_mode,
            news_weight=0.6,  # News more important for dividend safety
            social_weight=0.2,
            velocity_weight=0.2,
            sentiment_filter_threshold=10,  # Require positive sentiment
        ),
        risk=RiskConfig(
            mode=RiskMode.EQUAL_RISK,
            max_position_size=0.05,
            target_volatility=0.10,  # Lower vol for income
            stop_loss_atr_multiple=3.0,  # Wider stops for income stocks
        ),
        custom_params={
            "factors": {
                "momentum": 0.0,
                "value": 0.2,
                "quality": 0.4,
                "low_vol": 0.2,
                "dividend": 0.2,  # Dividend yield factor
            },
            "min_dividend_yield": min_yield,
            "top_percentile": top_percentile,
            "allow_short": False,  # No shorting for dividend strategy
            "equal_weight": True,
        }
    )


# =============================================================================
# Advanced 5 Strategies (Power User Presets)
# =============================================================================

def trend_following_strategy(
    name: str = "Trend Following",
    universe: list[str] = None,
    sentiment_mode: SentimentMode = SentimentMode.RISK_ADJUSTMENT,
    allow_short: bool = True,
    lookback_days: int = 200,
) -> StrategyConfig:
    """
    Trend Following / Time-Series Momentum

    Go long assets in uptrends, short assets in downtrends.
    Classic managed futures / CTA style.

    Benefits:
    - Crisis alpha: Performs well in extended drawdowns
    - Works across all asset classes
    - Uncorrelated to traditional long-only
    - Systematic, removes emotion

    Signal Enhancement:
    - Sentiment RISK_ADJUSTMENT: Reduce size when sentiment diverges from trend
    - Extreme negative sentiment + downtrend = larger short
    - Sentiment momentum confirms trend persistence

    Best for: Tactical allocation, crisis hedging, diversification
    """
    return StrategyConfig(
        name=name,
        strategy_type=StrategyType.TREND_FOLLOWING,
        universe=universe or [],
        sentiment=SentimentConfig(
            mode=sentiment_mode,
            news_weight=0.4,
            social_weight=0.3,
            velocity_weight=0.3,
        ),
        risk=RiskConfig(
            mode=RiskMode.VOLATILITY_SCALED,
            max_position_size=0.10,
            max_portfolio_leverage=1.5,
            target_volatility=0.15,
            stop_loss_atr_multiple=2.5,
        ),
        custom_params={
            "lookback_days": lookback_days,
            "short_window": 20,
            "long_window": 60,
            "allow_short": allow_short,
            "min_signal_strength": 20,
        }
    )


def short_term_reversal_strategy(
    name: str = "Short-Term Reversal",
    universe: list[str] = None,
    sentiment_mode: SentimentMode = SentimentMode.CONFIRMATION,
    lookback_days: int = 5,
    holding_days: int = 5,
) -> StrategyConfig:
    """
    Short-Term Reversal / Mean Reversion

    Buy recent losers, sell recent winners on 1-5 day horizons.
    Captures liquidity shocks and overreaction.

    Benefits:
    - High Sharpe when executed well
    - Market-neutral reduces beta exposure
    - Profits from short-term noise
    - Diversifying to momentum

    Signal Enhancement:
    - Sentiment CONFIRMATION: Only trade reversals where sentiment also reverting
    - Avoids "falling knives" - stocks dropping on fundamental news
    - Sentiment velocity helps distinguish noise from signal

    Best for: Active traders, market-neutral portfolios, high turnover tolerance
    """
    return StrategyConfig(
        name=name,
        strategy_type=StrategyType.SHORT_TERM_REVERSAL,
        universe=universe or [],
        sentiment=SentimentConfig(
            mode=sentiment_mode,
            news_weight=0.3,
            social_weight=0.3,
            velocity_weight=0.4,  # Velocity most important for reversal
        ),
        risk=RiskConfig(
            mode=RiskMode.VOLATILITY_SCALED,
            max_position_size=0.03,  # Smaller positions, more names
            target_volatility=0.10,
            stop_loss_atr_multiple=1.5,  # Tighter stops
        ),
        custom_params={
            "lookback_days": lookback_days,
            "holding_days": holding_days,
            "min_zscore": 1.5,
            "market_neutral": True,
        }
    )


def statistical_arbitrage_strategy(
    name: str = "Statistical Arbitrage",
    universe: list[str] = None,
    pairs: list[tuple[str, str]] = None,
    sentiment_mode: SentimentMode = SentimentMode.ALPHA,
) -> StrategyConfig:
    """
    Statistical Arbitrage / Pairs Trading

    Trade relative mispricings between related securities.
    Market-neutral by design.

    Benefits:
    - Market-neutral: No directional beta
    - Captures relative value
    - Consistent returns in range-bound markets
    - Low correlation to indices

    Signal Enhancement:
    - Sentiment ALPHA: Sentiment divergence as additional spread signal
    - If spread widens AND sentiment diverges, stronger signal
    - Sentiment helps identify fundamental vs. technical dislocations

    Best for: Market-neutral mandates, relative value, quant-focused investors
    """
    return StrategyConfig(
        name=name,
        strategy_type=StrategyType.STATISTICAL_ARBITRAGE,
        universe=universe or [],
        sentiment=SentimentConfig(
            mode=sentiment_mode,
            news_weight=0.5,
            social_weight=0.3,
            velocity_weight=0.2,
            sentiment_alpha_weight=0.20,
        ),
        risk=RiskConfig(
            mode=RiskMode.EQUAL_RISK,
            max_position_size=0.05,
            target_volatility=0.08,  # Lower vol target
            stop_loss_atr_multiple=3.0,
        ),
        custom_params={
            "pairs": pairs or [],
            "zscore_lookback": 60,
            "min_zscore": 2.0,
            "max_zscore": 4.0,
        }
    )


def volatility_premium_strategy(
    name: str = "Volatility Premium",
    universe: list[str] = None,
    sentiment_mode: SentimentMode = SentimentMode.FILTER,
    low_vol_only: bool = True,
) -> StrategyConfig:
    """
    Volatility Risk Premium

    Equity proxy for volatility selling - own low-vol stocks.
    (Full implementation requires options trading.)

    Benefits:
    - Earns volatility risk premium
    - Lower drawdowns than market
    - Defensive characteristics
    - Outperforms in calm markets

    Signal Enhancement:
    - Sentiment FILTER: Don't sell vol (own low-vol stocks) during crisis
    - Extreme negative sentiment = potential vol spike
    - Sentiment acts as regime filter

    Best for: Defensive allocation, volatility-aware investors, income focus
    """
    return StrategyConfig(
        name=name,
        strategy_type=StrategyType.VOLATILITY_PREMIUM,
        universe=universe or [],
        sentiment=SentimentConfig(
            mode=sentiment_mode,
            news_weight=0.5,
            social_weight=0.2,
            velocity_weight=0.3,
            sentiment_filter_threshold=-30,  # Exit on very negative sentiment
        ),
        risk=RiskConfig(
            mode=RiskMode.VOLATILITY_SCALED,
            max_position_size=0.05,
            target_volatility=0.10,
            stop_loss_atr_multiple=2.0,
        ),
        custom_params={
            "low_vol_only": low_vol_only,
            "vol_threshold_percentile": 30,
            "sentiment_crisis_threshold": -50,
        }
    )


# =============================================================================
# Preset Registry
# =============================================================================

STRATEGY_PRESETS = {
    # Original 4 (simple)
    "momentum": momentum_strategy,
    "quality_value": quality_value_strategy,
    "quality_momentum": quality_momentum_strategy,
    "dividend_growth": dividend_growth_strategy,
    # Advanced 5 (power user)
    "trend_following": trend_following_strategy,
    "short_term_reversal": short_term_reversal_strategy,
    "statistical_arbitrage": statistical_arbitrage_strategy,
    "volatility_premium": volatility_premium_strategy,
}


def get_preset(name: str, **kwargs) -> StrategyConfig:
    """
    Get a strategy preset by name.

    Args:
        name: Preset name (momentum, quality_value, etc.)
        **kwargs: Override default parameters

    Returns:
        StrategyConfig instance
    """
    if name not in STRATEGY_PRESETS:
        raise ValueError(f"Unknown preset: {name}. Available: {list(STRATEGY_PRESETS.keys())}")

    return STRATEGY_PRESETS[name](**kwargs)


def list_presets() -> list[str]:
    """List all available strategy presets."""
    return list(STRATEGY_PRESETS.keys())


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Original 4
    "momentum_strategy",
    "quality_value_strategy",
    "quality_momentum_strategy",
    "dividend_growth_strategy",
    # Advanced 5
    "trend_following_strategy",
    "short_term_reversal_strategy",
    "statistical_arbitrage_strategy",
    "volatility_premium_strategy",
    # Registry
    "STRATEGY_PRESETS",
    "get_preset",
    "list_presets",
]
