"""
Signal Generators

Modular signal generators that can be composed into strategies.
Each generator produces normalized signals (-100 to +100) for ranking and combining.
"""

from typing import Any

import numpy as np

from core.strategies.base import Signal, SignalGenerator, SignalType

# =============================================================================
# Price Momentum Signals
# =============================================================================


class TimeSeriesMomentumSignal(SignalGenerator):
    """
    Time-series momentum (trend following).
    Goes long when price is above trend, short when below.
    """

    def __init__(
        self, lookback_days: int = 252, short_window: int = 20, long_window: int = 60
    ):
        self.lookback_days = lookback_days
        self.short_window = short_window
        self.long_window = long_window

    @property
    def signal_type(self) -> SignalType:
        return SignalType.PRICE_MOMENTUM

    async def generate(
        self, symbols: list[str], market_data: dict[str, Any], **kwargs
    ) -> list[Signal]:
        signals = []

        for symbol in symbols:
            data = market_data.get(symbol, {})
            prices = data.get("price_history", [])
            current_price = data.get("current_price")

            if not prices or not current_price or len(prices) < self.long_window:
                continue

            # Calculate momentum metrics
            returns_short = (current_price - prices[-self.short_window]) / prices[
                -self.short_window
            ]
            returns_long = (current_price - prices[-self.long_window]) / prices[
                -self.long_window
            ]

            # Check if price is above moving averages
            ma_short = np.mean(prices[-self.short_window :])
            ma_long = np.mean(prices[-self.long_window :])

            # Trend strength: +1 if above both MAs, -1 if below both
            trend_score = 0
            if current_price > ma_short:
                trend_score += 1
            else:
                trend_score -= 1

            if current_price > ma_long:
                trend_score += 1
            else:
                trend_score -= 1

            # Combine momentum and trend
            momentum_score = (returns_short * 0.4 + returns_long * 0.6) * 100
            signal_value = momentum_score + (trend_score * 10)

            signals.append(
                Signal(
                    symbol=symbol,
                    signal_type=self.signal_type,
                    value=max(-100, min(100, signal_value)),
                    raw_value=returns_long,
                    confidence=abs(trend_score) / 2,  # Higher confidence when MAs agree
                    metadata={
                        "returns_short": returns_short,
                        "returns_long": returns_long,
                        "trend_score": trend_score,
                        "ma_short": ma_short,
                        "ma_long": ma_long,
                    },
                )
            )

        return signals


class CrossSectionalMomentumSignal(SignalGenerator):
    """
    Cross-sectional momentum.
    Ranks assets by relative performance over lookback period.
    """

    def __init__(self, lookback_days: int = 126):  # 6 months
        self.lookback_days = lookback_days

    @property
    def signal_type(self) -> SignalType:
        return SignalType.CROSS_SECTIONAL_MOMENTUM

    async def generate(
        self, symbols: list[str], market_data: dict[str, Any], **kwargs
    ) -> list[Signal]:
        # Calculate returns for all symbols
        returns = {}
        for symbol in symbols:
            data = market_data.get(symbol, {})
            prices = data.get("price_history", [])
            current_price = data.get("current_price")

            if prices and current_price and len(prices) >= self.lookback_days:
                start_price = prices[-self.lookback_days]
                if start_price > 0:
                    returns[symbol] = (current_price - start_price) / start_price

        if not returns:
            return []

        # Rank by returns (percentile)
        sorted_symbols = sorted(returns.keys(), key=lambda s: returns[s])
        n = len(sorted_symbols)

        signals = []
        for i, symbol in enumerate(sorted_symbols):
            # Convert rank to signal (-100 for worst, +100 for best)
            percentile = (i / (n - 1)) * 200 - 100 if n > 1 else 0

            signals.append(
                Signal(
                    symbol=symbol,
                    signal_type=self.signal_type,
                    value=percentile,
                    raw_value=returns[symbol],
                    metadata={
                        "rank": i + 1,
                        "total": n,
                        "return": returns[symbol],
                    },
                )
            )

        return signals


# =============================================================================
# Value Signals
# =============================================================================


class ValueSignal(SignalGenerator):
    """
    Value factor signal.
    Combines P/E, P/B, and earnings yield for value scoring.
    """

    def __init__(
        self, pe_weight: float = 0.4, pb_weight: float = 0.3, ey_weight: float = 0.3
    ):
        self.pe_weight = pe_weight
        self.pb_weight = pb_weight
        self.ey_weight = ey_weight

    @property
    def signal_type(self) -> SignalType:
        return SignalType.VALUE

    async def generate(
        self, symbols: list[str], market_data: dict[str, Any], **kwargs
    ) -> list[Signal]:
        # Collect metrics for ranking
        metrics = {}
        for symbol in symbols:
            data = market_data.get(symbol, {})
            pe = data.get("pe_ratio")
            pb = data.get("pb_ratio")

            # Calculate earnings yield (inverse P/E)
            ey = (1 / pe) if pe and pe > 0 else None

            if pe or pb or ey:
                metrics[symbol] = {
                    "pe": pe,
                    "pb": pb,
                    "ey": ey,
                }

        if not metrics:
            return []

        # Rank each metric (lower P/E and P/B = better, higher EY = better)
        pe_values = [
            m["pe"] for m in metrics.values() if m["pe"] is not None and m["pe"] > 0
        ]
        pb_values = [
            m["pb"] for m in metrics.values() if m["pb"] is not None and m["pb"] > 0
        ]
        ey_values = [m["ey"] for m in metrics.values() if m["ey"] is not None]

        signals = []
        for symbol, m in metrics.items():
            scores = []

            # P/E score (inverted - low is good)
            if m["pe"] and pe_values:
                pe_rank = self.percentile_rank(m["pe"], pe_values)
                pe_score = 100 - pe_rank  # Invert
                scores.append((pe_score, self.pe_weight))

            # P/B score (inverted - low is good)
            if m["pb"] and pb_values:
                pb_rank = self.percentile_rank(m["pb"], pb_values)
                pb_score = 100 - pb_rank  # Invert
                scores.append((pb_score, self.pb_weight))

            # Earnings yield score (high is good)
            if m["ey"] and ey_values:
                ey_score = self.percentile_rank(m["ey"], ey_values)
                scores.append((ey_score, self.ey_weight))

            if scores:
                # Weighted average
                total_weight = sum(w for _, w in scores)
                combined = (
                    sum(s * w for s, w in scores) / total_weight
                    if total_weight > 0
                    else 50
                )

                # Convert to -100 to 100 range
                signal_value = (combined - 50) * 2

                signals.append(
                    Signal(
                        symbol=symbol,
                        signal_type=self.signal_type,
                        value=signal_value,
                        raw_value=combined,
                        metadata={
                            "pe_ratio": m["pe"],
                            "pb_ratio": m["pb"],
                            "earnings_yield": m["ey"],
                        },
                    )
                )

        return signals


# =============================================================================
# Quality Signals
# =============================================================================


class QualitySignal(SignalGenerator):
    """
    Quality factor signal.
    Combines ROE, profit margins, and financial stability metrics.
    """

    def __init__(
        self,
        roe_weight: float = 0.4,
        margin_weight: float = 0.3,
        stability_weight: float = 0.3,
    ):
        self.roe_weight = roe_weight
        self.margin_weight = margin_weight
        self.stability_weight = stability_weight

    @property
    def signal_type(self) -> SignalType:
        return SignalType.QUALITY

    async def generate(
        self, symbols: list[str], market_data: dict[str, Any], **kwargs
    ) -> list[Signal]:
        metrics = {}
        for symbol in symbols:
            data = market_data.get(symbol, {})

            roe = data.get("roe")  # Return on equity
            margin = data.get("profit_margin")
            de_ratio = data.get("debt_to_equity")
            beta = data.get("beta")

            # Stability score (lower debt and beta = more stable)
            stability = None
            if de_ratio is not None and beta is not None:
                # Invert so lower is better
                stability = 1 / (1 + de_ratio) * (2 - min(beta, 2))

            if any([roe, margin, stability]):
                metrics[symbol] = {
                    "roe": roe,
                    "margin": margin,
                    "stability": stability,
                    "debt_to_equity": de_ratio,
                    "beta": beta,
                }

        if not metrics:
            return []

        # Get value lists for ranking
        roe_values = [m["roe"] for m in metrics.values() if m["roe"] is not None]
        margin_values = [
            m["margin"] for m in metrics.values() if m["margin"] is not None
        ]
        stability_values = [
            m["stability"] for m in metrics.values() if m["stability"] is not None
        ]

        signals = []
        for symbol, m in metrics.items():
            scores = []

            if m["roe"] and roe_values:
                roe_score = self.percentile_rank(m["roe"], roe_values)
                scores.append((roe_score, self.roe_weight))

            if m["margin"] and margin_values:
                margin_score = self.percentile_rank(m["margin"], margin_values)
                scores.append((margin_score, self.margin_weight))

            if m["stability"] and stability_values:
                stability_score = self.percentile_rank(m["stability"], stability_values)
                scores.append((stability_score, self.stability_weight))

            if scores:
                total_weight = sum(w for _, w in scores)
                combined = (
                    sum(s * w for s, w in scores) / total_weight
                    if total_weight > 0
                    else 50
                )
                signal_value = (combined - 50) * 2

                signals.append(
                    Signal(
                        symbol=symbol,
                        signal_type=self.signal_type,
                        value=signal_value,
                        raw_value=combined,
                        metadata={
                            "roe": m["roe"],
                            "profit_margin": m["margin"],
                            "stability": m["stability"],
                        },
                    )
                )

        return signals


# =============================================================================
# Sentiment Signals
# =============================================================================


class NewsSentimentSignal(SignalGenerator):
    """News-based sentiment signal."""

    @property
    def signal_type(self) -> SignalType:
        return SignalType.NEWS_SENTIMENT

    async def generate(
        self,
        symbols: list[str],
        market_data: dict[str, Any],
        sentiment_data: dict[str, Any] = None,
        **kwargs,
    ) -> list[Signal]:
        if not sentiment_data:
            return []

        signals = []
        for symbol in symbols:
            data = sentiment_data.get(symbol, {})
            news_sentiment = data.get("news_sentiment")

            if news_sentiment is not None:
                signals.append(
                    Signal(
                        symbol=symbol,
                        signal_type=self.signal_type,
                        value=news_sentiment,  # Already -100 to 100
                        raw_value=news_sentiment,
                        metadata={
                            "source": "news",
                            "headline_count": data.get("headline_count", 0),
                        },
                    )
                )

        return signals


class SocialSentimentSignal(SignalGenerator):
    """Social media sentiment signal (StockTwits, Reddit)."""

    @property
    def signal_type(self) -> SignalType:
        return SignalType.SOCIAL_SENTIMENT

    async def generate(
        self,
        symbols: list[str],
        market_data: dict[str, Any],
        sentiment_data: dict[str, Any] = None,
        **kwargs,
    ) -> list[Signal]:
        if not sentiment_data:
            return []

        signals = []
        for symbol in symbols:
            data = sentiment_data.get(symbol, {})
            social_sentiment = data.get("social_sentiment")

            if social_sentiment is not None:
                signals.append(
                    Signal(
                        symbol=symbol,
                        signal_type=self.signal_type,
                        value=social_sentiment,
                        raw_value=social_sentiment,
                        metadata={
                            "source": "social",
                            "mention_count": data.get("mention_count", 0),
                        },
                    )
                )

        return signals


class SentimentVelocitySignal(SignalGenerator):
    """Sentiment change velocity - captures momentum in sentiment."""

    @property
    def signal_type(self) -> SignalType:
        return SignalType.SENTIMENT_VELOCITY

    async def generate(
        self,
        symbols: list[str],
        market_data: dict[str, Any],
        sentiment_data: dict[str, Any] = None,
        **kwargs,
    ) -> list[Signal]:
        if not sentiment_data:
            return []

        signals = []
        for symbol in symbols:
            data = sentiment_data.get(symbol, {})
            velocity = data.get("sentiment_velocity")

            if velocity is not None:
                # Velocity is change over period, normalize to signal
                signals.append(
                    Signal(
                        symbol=symbol,
                        signal_type=self.signal_type,
                        value=max(-100, min(100, velocity * 10)),  # Scale velocity
                        raw_value=velocity,
                        metadata={
                            "period_days": data.get("velocity_period", 7),
                        },
                    )
                )

        return signals


# =============================================================================
# Volatility Signals
# =============================================================================


class RealizedVolatilitySignal(SignalGenerator):
    """Realized volatility signal (low vol = positive signal)."""

    def __init__(self, lookback_days: int = 20):
        self.lookback_days = lookback_days

    @property
    def signal_type(self) -> SignalType:
        return SignalType.REALIZED_VOLATILITY

    async def generate(
        self, symbols: list[str], market_data: dict[str, Any], **kwargs
    ) -> list[Signal]:
        vol_data = {}

        for symbol in symbols:
            data = market_data.get(symbol, {})
            prices = data.get("price_history", [])

            if len(prices) >= self.lookback_days + 1:
                # Calculate daily returns
                returns = []
                for i in range(1, self.lookback_days + 1):
                    r = (
                        (prices[-i] - prices[-i - 1]) / prices[-i - 1]
                        if prices[-i - 1] > 0
                        else 0
                    )
                    returns.append(r)

                # Annualized volatility (sample std, ddof=1)
                vol = (
                    float(np.std(returns, ddof=1)) * np.sqrt(252)
                    if len(returns) > 1
                    else 0.0
                )
                vol_data[symbol] = vol

        if not vol_data:
            return []

        # Rank by volatility (low vol = high score for defensive strategy)
        vol_values = list(vol_data.values())

        signals = []
        for symbol, vol in vol_data.items():
            # Low volatility factor: invert ranking
            vol_rank = self.percentile_rank(vol, vol_values)
            signal_value = (100 - vol_rank - 50) * 2  # Low vol = positive signal

            signals.append(
                Signal(
                    symbol=symbol,
                    signal_type=self.signal_type,
                    value=signal_value,
                    raw_value=vol,
                    metadata={
                        "annualized_volatility": vol,
                        "lookback_days": self.lookback_days,
                    },
                )
            )

        return signals


# =============================================================================
# Reversal Signals
# =============================================================================


class ShortTermReversalSignal(SignalGenerator):
    """
    Short-term reversal signal.
    Identifies oversold/overbought conditions for mean reversion.
    """

    def __init__(self, lookback_days: int = 5):
        self.lookback_days = lookback_days

    @property
    def signal_type(self) -> SignalType:
        return SignalType.REVERSAL

    async def generate(
        self, symbols: list[str], market_data: dict[str, Any], **kwargs
    ) -> list[Signal]:
        returns = {}

        for symbol in symbols:
            data = market_data.get(symbol, {})
            prices = data.get("price_history", [])
            current_price = data.get("current_price")

            if prices and current_price and len(prices) >= self.lookback_days:
                start_price = prices[-self.lookback_days]
                if start_price > 0:
                    ret = (current_price - start_price) / start_price
                    returns[symbol] = ret

        if not returns:
            return []

        # Calculate z-scores for reversal
        ret_values = list(returns.values())
        mean_ret = np.mean(ret_values)
        std_ret = float(np.std(ret_values, ddof=1)) if len(ret_values) > 1 else 1.0

        signals = []
        for symbol, ret in returns.items():
            if std_ret > 0:
                z_score = (ret - mean_ret) / std_ret
            else:
                z_score = 0

            # Reversal: negative z-score = buy signal (oversold)
            # Positive z-score = sell signal (overbought)
            signal_value = -z_score * 30  # Scale to reasonable range

            signals.append(
                Signal(
                    symbol=symbol,
                    signal_type=self.signal_type,
                    value=max(-100, min(100, signal_value)),
                    raw_value=ret,
                    metadata={
                        "return": ret,
                        "z_score": z_score,
                        "lookback_days": self.lookback_days,
                    },
                )
            )

        return signals


# =============================================================================
# Statistical Signals
# =============================================================================


class ZScoreSignal(SignalGenerator):
    """
    Z-score signal for statistical arbitrage.
    Measures deviation from rolling mean.
    """

    def __init__(self, lookback_days: int = 60):
        self.lookback_days = lookback_days

    @property
    def signal_type(self) -> SignalType:
        return SignalType.STATISTICAL_ZSCORE

    async def generate(
        self, symbols: list[str], market_data: dict[str, Any], **kwargs
    ) -> list[Signal]:
        signals = []

        for symbol in symbols:
            data = market_data.get(symbol, {})
            prices = data.get("price_history", [])
            current_price = data.get("current_price")

            if prices and current_price and len(prices) >= self.lookback_days:
                window = prices[-self.lookback_days :]
                mean = np.mean(window)
                std = float(np.std(window, ddof=1)) if len(window) > 1 else 0.0

                if std > 0:
                    z_score = (current_price - mean) / std

                    # Mean reversion: buy when below mean, sell when above
                    signal_value = -z_score * 25

                    signals.append(
                        Signal(
                            symbol=symbol,
                            signal_type=self.signal_type,
                            value=max(-100, min(100, signal_value)),
                            raw_value=z_score,
                            metadata={
                                "z_score": z_score,
                                "mean": mean,
                                "std": std,
                                "lookback_days": self.lookback_days,
                            },
                        )
                    )

        return signals


# =============================================================================
# Dividend Signals
# =============================================================================


class DividendYieldSignal(SignalGenerator):
    """
    Dividend yield signal.
    Ranks stocks by dividend yield for income strategies.
    """

    def __init__(self, min_yield: float = 0.0):
        self.min_yield = min_yield

    @property
    def signal_type(self) -> SignalType:
        return SignalType.DIVIDEND_YIELD

    async def generate(
        self, symbols: list[str], market_data: dict[str, Any], **kwargs
    ) -> list[Signal]:
        yields = {}

        for symbol in symbols:
            data = market_data.get(symbol, {})
            div_yield = data.get("dividend_yield")

            if div_yield is not None and div_yield >= self.min_yield:
                yields[symbol] = div_yield

        if not yields:
            return []

        # Rank by dividend yield (higher = better)
        yield_values = list(yields.values())

        signals = []
        for symbol, div_yield in yields.items():
            yield_score = self.percentile_rank(div_yield, yield_values)
            # Convert to -100 to 100 (higher yield = higher signal)
            signal_value = (yield_score - 50) * 2

            signals.append(
                Signal(
                    symbol=symbol,
                    signal_type=self.signal_type,
                    value=signal_value,
                    raw_value=div_yield,
                    metadata={
                        "dividend_yield": div_yield,
                        "yield_percentile": yield_score,
                    },
                )
            )

        return signals


# =============================================================================
# Signal Combiner
# =============================================================================


class SignalCombiner:
    """
    Combines multiple signals with configurable weights.
    Useful for multi-factor strategies.
    """

    def __init__(self, weights: dict[SignalType, float] | None = None):
        self.weights = weights or {}

    def combine(
        self, signals: list[Signal], method: str = "weighted_average"
    ) -> dict[str, float]:
        """
        Combine signals for each symbol.

        Args:
            signals: List of signals from various generators
            method: "weighted_average", "rank_average", or "equal_weight"

        Returns:
            Dictionary of symbol -> combined signal value
        """
        # Group signals by symbol
        by_symbol: dict[str, list[Signal]] = {}
        for signal in signals:
            if signal.symbol not in by_symbol:
                by_symbol[signal.symbol] = []
            by_symbol[signal.symbol].append(signal)

        combined = {}
        for symbol, symbol_signals in by_symbol.items():
            if method == "weighted_average":
                total_weight = 0
                weighted_sum = 0
                for s in symbol_signals:
                    weight = self.weights.get(s.signal_type, 1.0) * s.confidence
                    weighted_sum += s.value * weight
                    total_weight += weight
                combined[symbol] = (
                    weighted_sum / total_weight if total_weight > 0 else 0
                )

            elif method == "rank_average":
                # Simple average of all signals
                combined[symbol] = np.mean([s.value for s in symbol_signals])

            else:  # equal_weight
                combined[symbol] = np.mean([s.value for s in symbol_signals])

        return combined


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Momentum
    "TimeSeriesMomentumSignal",
    "CrossSectionalMomentumSignal",
    # Value
    "ValueSignal",
    # Quality
    "QualitySignal",
    # Dividend
    "DividendYieldSignal",
    # Sentiment
    "NewsSentimentSignal",
    "SocialSentimentSignal",
    "SentimentVelocitySignal",
    # Volatility
    "RealizedVolatilitySignal",
    # Reversal
    "ShortTermReversalSignal",
    # Statistical
    "ZScoreSignal",
    # Utilities
    "SignalCombiner",
]
