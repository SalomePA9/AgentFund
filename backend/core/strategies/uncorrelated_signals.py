"""
Uncorrelated Signal Generators

Signal generators for data sources that are structurally uncorrelated to the
existing equity momentum, value, quality, and retail sentiment signals.

Organised into three categories:

Cross-Asset / Macro Signals (portfolio-level):
  - CreditSpreadSignal      — HY credit spread z-score
  - YieldCurveSignal        — 10Y-2Y slope and rate of change
  - VolatilityRegimeSignal  — VIX level, term structure, regime score

Alternative Data Signals (stock-level):
  - InsiderTransactionSignal — SEC Form 4 insider buying clusters
  - ShortInterestSignal      — Short % of float + rate of change
  - SeasonalitySignal        — Calendar/monthly return patterns

Fundamental Regime Signals (stock-level):
  - EarningsRevisionsSignal  — Forward EPS revision breadth
  - AccrualsQualitySignal    — Cash flow vs reported earnings divergence

All signals normalised to -100 (strong sell) to +100 (strong buy).
"""

from __future__ import annotations

import calendar
from datetime import datetime, timezone
from typing import Any

import numpy as np

from core.strategies.base import Signal, SignalGenerator, SignalType

# =============================================================================
# Cross-Asset / Macro Signals
# =============================================================================


class CreditSpreadSignal(SignalGenerator):
    """
    Credit spread signal from FRED high-yield OAS.

    When spreads widen (z-score > 0), credit markets are pricing in risk
    that equity markets may not yet reflect.  This is a bearish signal.
    When spreads tighten (z-score < 0), risk appetite is healthy.

    This is a GLOBAL signal applied uniformly to all symbols — it acts
    as a macro risk filter rather than a stock-specific alpha signal.
    """

    @property
    def signal_type(self) -> SignalType:
        return SignalType.CREDIT_SPREAD

    async def generate(
        self,
        symbols: list[str],
        market_data: dict[str, Any],
        macro_data: dict[str, Any] | None = None,
        **kwargs,
    ) -> list[Signal]:
        if not macro_data:
            return []

        credit = macro_data.get("credit_spread", {})
        z_score = credit.get("z_score", 0.0)
        percentile = credit.get("percentile", 50.0)
        roc = credit.get("rate_of_change", 0.0)

        if credit.get("current") is None:
            return []

        # Invert: high spread z-score = bearish (negative signal)
        # Widening spreads = risk increasing
        base_signal = -z_score * 30  # Scale z-score to signal range

        # Rate of change amplifier: rapidly widening spreads are worse
        roc_adjustment = -roc * 5  # Widening RoC adds to bearish signal

        signal_value = max(-100, min(100, base_signal + roc_adjustment))

        # Apply uniformly to all symbols (macro signal)
        signals = []
        for symbol in symbols:
            signals.append(
                Signal(
                    symbol=symbol,
                    signal_type=self.signal_type,
                    value=signal_value,
                    raw_value=credit.get("current"),
                    confidence=min(1.0, abs(z_score) / 2),
                    metadata={
                        "spread_level": credit.get("current"),
                        "z_score": z_score,
                        "percentile": percentile,
                        "rate_of_change": roc,
                        "signal_scope": "macro",
                    },
                )
            )

        return signals


class YieldCurveSignal(SignalGenerator):
    """
    Yield curve signal from the 10Y-2Y Treasury spread.

    Positive slope = normal (growth expectations healthy) = bullish
    Flat/inverted = recession risk = bearish

    Rate of change matters too: a rapidly flattening curve is more
    ominous than a stably inverted one (which markets have priced in).

    This is a GLOBAL signal applied uniformly to all symbols.
    """

    @property
    def signal_type(self) -> SignalType:
        return SignalType.YIELD_CURVE

    async def generate(
        self,
        symbols: list[str],
        market_data: dict[str, Any],
        macro_data: dict[str, Any] | None = None,
        **kwargs,
    ) -> list[Signal]:
        if not macro_data:
            return []

        yc = macro_data.get("yield_curve", {})
        current = yc.get("current")
        z_score = yc.get("z_score", 0.0)
        roc = yc.get("rate_of_change", 0.0)

        if current is None:
            return []

        # Positive spread = normal curve = bullish signal
        # Negative spread = inverted = bearish signal
        # Scale: ±2% spread maps to ±100
        base_signal = current * 50  # 1% spread → +50 signal

        # Rate of change: steepening is bullish, flattening is bearish
        roc_adjustment = roc * 20

        signal_value = max(-100, min(100, base_signal + roc_adjustment))

        signals = []
        for symbol in symbols:
            signals.append(
                Signal(
                    symbol=symbol,
                    signal_type=self.signal_type,
                    value=signal_value,
                    raw_value=current,
                    confidence=min(1.0, abs(z_score) / 2),
                    metadata={
                        "spread_10y2y": current,
                        "z_score": z_score,
                        "rate_of_change": roc,
                        "inverted": current < 0,
                        "signal_scope": "macro",
                    },
                )
            )

        return signals


class VolatilityRegimeSignal(SignalGenerator):
    """
    Volatility regime signal from VIX and its term structure.

    Combines:
    - VIX level (high = fearful = bearish)
    - VIX term structure (backwardation = panic = bearish)
    - VIX rate of change (spiking VIX = bearish)
    - Implied-Realised spread (high = expensive insurance = cautious)

    This is a GLOBAL signal that tells all strategies whether the
    environment is safe for risk-taking or calls for caution.
    """

    @property
    def signal_type(self) -> SignalType:
        return SignalType.VOLATILITY_REGIME

    async def generate(
        self,
        symbols: list[str],
        market_data: dict[str, Any],
        macro_data: dict[str, Any] | None = None,
        **kwargs,
    ) -> list[Signal]:
        if not macro_data:
            return []

        vol = macro_data.get("volatility_regime", {})
        regime_score = vol.get("regime_score", 0.0)
        vix_current = vol.get("vix_current")

        if vix_current is None:
            return []

        # regime_score is already -1 (crisis) to +1 (calm)
        # Convert to -100 to +100 signal
        signal_value = regime_score * 100

        # Amplify extremes: VIX > 35 or < 12 should be strong signals
        if vix_current > 35:
            signal_value = min(signal_value, -80)
        elif vix_current < 12:
            signal_value = max(signal_value, 60)

        signal_value = max(-100, min(100, signal_value))

        signals = []
        for symbol in symbols:
            signals.append(
                Signal(
                    symbol=symbol,
                    signal_type=self.signal_type,
                    value=signal_value,
                    raw_value=vix_current,
                    confidence=min(1.0, abs(regime_score)),
                    metadata={
                        "vix_current": vix_current,
                        "vix_z_score": vol.get("vix_z_score"),
                        "term_structure": vol.get("vix_term_structure"),
                        "vix_roc": vol.get("vix_rate_of_change"),
                        "iv_rv_spread": vol.get("iv_rv_spread"),
                        "regime_label": vol.get("regime_label"),
                        "regime_score": regime_score,
                        "signal_scope": "macro",
                    },
                )
            )

        return signals


# =============================================================================
# Alternative Data Signals (stock-level)
# =============================================================================


class InsiderTransactionSignal(SignalGenerator):
    """
    Insider transaction signal from SEC Form 4 filings.

    Insider buying clusters are one of the strongest uncorrelated signals
    in equity markets.  When multiple insiders buy in a short window,
    it strongly predicts outperformance 3-12 months forward.

    Structurally uncorrelated to price momentum because insiders
    buy based on private fundamental knowledge, often against the trend.
    """

    @property
    def signal_type(self) -> SignalType:
        return SignalType.INSIDER_TRANSACTIONS

    async def generate(
        self,
        symbols: list[str],
        market_data: dict[str, Any],
        insider_data: dict[str, Any] | None = None,
        **kwargs,
    ) -> list[Signal]:
        if not insider_data:
            return []

        signals = []
        for symbol in symbols:
            data = insider_data.get(symbol)
            if not data:
                continue

            # net_sentiment is already -100 to +100
            net_sentiment = data.get("net_sentiment", 0)
            cluster_score = data.get("cluster_score", 0)
            filing_count = data.get("filing_count", 0)

            # Weight by cluster strength: isolated filings matter less
            # than coordinated insider activity
            confidence = min(1.0, cluster_score / 50.0)

            # Blend net sentiment with cluster strength
            signal_value = net_sentiment * (0.5 + 0.5 * confidence)
            signal_value = max(-100, min(100, signal_value))

            signals.append(
                Signal(
                    symbol=symbol,
                    signal_type=self.signal_type,
                    value=signal_value,
                    raw_value=data.get("buy_ratio", 0.5),
                    confidence=confidence,
                    metadata={
                        "buy_count": data.get("buy_count"),
                        "sell_count": data.get("sell_count"),
                        "filing_count": filing_count,
                        "buy_ratio": data.get("buy_ratio"),
                        "cluster_score": cluster_score,
                        "signal_scope": "stock",
                    },
                )
            )

        return signals


class ShortInterestSignal(SignalGenerator):
    """
    Short interest signal reflecting institutional positioning.

    High short interest = institutions are bearish = negative signal.
    Low short interest = no institutional concern = neutral.
    Rapidly DECREASING short interest = covering = bullish.

    Uncorrelated to retail sentiment (StockTwits/news) because it captures
    hedge fund and institutional views that retail doesn't see.
    """

    @property
    def signal_type(self) -> SignalType:
        return SignalType.SHORT_INTEREST

    async def generate(
        self,
        symbols: list[str],
        market_data: dict[str, Any],
        short_interest_data: dict[str, Any] | None = None,
        short_interest_roc: dict[str, float] | None = None,
        **kwargs,
    ) -> list[Signal]:
        if not short_interest_data:
            return []

        roc_data = short_interest_roc or {}

        # Collect scores for cross-sectional ranking
        raw_scores: dict[str, float] = {}
        raw_data: dict[str, dict] = {}

        for symbol in symbols:
            data = short_interest_data.get(symbol)
            if not data:
                continue

            score = data.get("short_interest_score", 0)
            raw_scores[symbol] = score
            raw_data[symbol] = data

        if not raw_scores:
            return []

        # Cross-sectional ranking: compare each stock's SI to the universe
        all_scores = list(raw_scores.values())
        mean_score = float(np.mean(all_scores))
        std_score = float(np.std(all_scores)) if len(all_scores) > 1 else 1.0

        signals = []
        for symbol, score in raw_scores.items():
            data = raw_data[symbol]

            # Z-score relative to universe
            cs_z = (score - mean_score) / std_score if std_score > 0 else 0.0

            # Blend absolute score with cross-sectional ranking
            base_signal = score * 0.6 + cs_z * 15 * 0.2

            # Rate-of-change component: decreasing SI = covering = bullish
            # ROC score is positive when SI is increasing (bearish),
            # negative when SI is decreasing (bullish/covering)
            roc_score = roc_data.get(symbol, 0.0)
            roc_component = -roc_score * 0.2  # Invert: decreasing SI → positive signal

            signal_value = base_signal + roc_component
            signal_value = max(-100, min(100, signal_value))

            signals.append(
                Signal(
                    symbol=symbol,
                    signal_type=self.signal_type,
                    value=signal_value,
                    raw_value=data.get("short_pct_float"),
                    confidence=0.7,  # Moderate confidence (data is bi-weekly)
                    metadata={
                        "short_pct_float": data.get("short_pct_float"),
                        "short_ratio": data.get("short_ratio"),
                        "cross_sectional_z": round(cs_z, 4),
                        "roc_score": round(roc_score, 2),
                        "signal_scope": "stock",
                    },
                )
            )

        return signals


class SeasonalitySignal(SignalGenerator):
    """
    Calendar/seasonality signal based on monthly return patterns.

    Well-documented effects:
    - January effect (small caps outperform)
    - Sell in May (May-Oct underperformance)
    - End-of-month/quarter window dressing
    - Santa Claus rally (late December)

    Purely time-based and structurally uncorrelated to everything else.
    """

    # Historical average monthly excess returns for S&P 500
    # Based on long-run (1950-2024) seasonal patterns
    MONTHLY_BIAS: dict[int, float] = {
        1: 0.012,  # January: +1.2% (January effect)
        2: -0.002,  # February: -0.2%
        3: 0.010,  # March: +1.0%
        4: 0.015,  # April: +1.5% (strong)
        5: -0.001,  # May: flat (sell in May)
        6: -0.002,  # June: -0.2%
        7: 0.008,  # July: +0.8%
        8: -0.005,  # August: -0.5%
        9: -0.010,  # September: -1.0% (worst month)
        10: 0.005,  # October: +0.5% (turnaround)
        11: 0.015,  # November: +1.5% (strong)
        12: 0.013,  # December: +1.3% (Santa rally)
    }

    @property
    def signal_type(self) -> SignalType:
        return SignalType.SEASONALITY

    async def generate(
        self, symbols: list[str], market_data: dict[str, Any], **kwargs
    ) -> list[Signal]:
        now = datetime.now(timezone.utc)
        month = now.month
        day = now.day
        _, days_in_month = calendar.monthrange(now.year, month)

        # Base seasonal signal for current month
        monthly_bias = self.MONTHLY_BIAS.get(month, 0.0)

        # Scale: ±1.5% monthly bias maps to ±100 signal
        base_signal = monthly_bias / 0.015 * 60  # Max ±60 from monthly

        # End-of-month effect: last 3 days tend to be positive (window dressing)
        eom_boost = 0.0
        if day >= days_in_month - 2:
            eom_boost = 15.0  # +15 boost in last 3 days

        # End-of-quarter additional boost
        eoq_boost = 0.0
        if month in (3, 6, 9, 12) and day >= days_in_month - 2:
            eoq_boost = 10.0  # Additional +10 for quarter-end

        signal_value = base_signal + eom_boost + eoq_boost
        signal_value = max(-100, min(100, signal_value))

        # Low confidence: seasonality is a weak but diversifying signal
        confidence = 0.3

        signals = []
        for symbol in symbols:
            signals.append(
                Signal(
                    symbol=symbol,
                    signal_type=self.signal_type,
                    value=signal_value,
                    raw_value=monthly_bias,
                    confidence=confidence,
                    metadata={
                        "month": month,
                        "day_of_month": day,
                        "monthly_bias": monthly_bias,
                        "eom_boost": eom_boost,
                        "eoq_boost": eoq_boost,
                        "signal_scope": "macro",
                    },
                )
            )

        return signals


# =============================================================================
# Fundamental Regime Signals (stock-level)
# =============================================================================


class EarningsRevisionsSignal(SignalGenerator):
    """
    Earnings revision breadth signal.

    Measures the direction of analyst EPS estimate changes.  When forward
    estimates are being revised upward, the stock tends to outperform —
    and this is forward-looking and uncorrelated to backward-looking
    momentum (which uses past returns).

    Approximated from Yahoo Finance data:
    - Compare forward EPS to trailing EPS
    - Stocks where forward > trailing = positive revisions
    - Cross-sectional ranking of revision magnitude

    A more precise implementation would use IBES or FactSet revision data.
    """

    @property
    def signal_type(self) -> SignalType:
        return SignalType.EARNINGS_REVISIONS

    async def generate(
        self, symbols: list[str], market_data: dict[str, Any], **kwargs
    ) -> list[Signal]:
        # Compute earnings revision proxy for each symbol
        revision_data: dict[str, float] = {}

        for symbol in symbols:
            data = market_data.get(symbol, {})
            pe_ratio = data.get("pe_ratio")
            eps = data.get("eps")
            price = data.get("current_price")

            if not pe_ratio or not price or pe_ratio <= 0:
                continue

            # Trailing EPS from trailing P/E (pe_ratio > 0 guaranteed by guard above)
            trailing_eps = price / pe_ratio

            # Forward EPS proxy: if the stock has a lower forward P/E,
            # analysts expect higher earnings.  We approximate this from
            # the relationship between current estimates and trailing.
            # A stock with improving margins + revenue growth will have
            # forward EPS > trailing EPS
            forward_eps_proxy = data.get("forward_eps")

            if forward_eps_proxy and trailing_eps and trailing_eps > 0:
                revision = (forward_eps_proxy - trailing_eps) / abs(trailing_eps)
                revision_data[symbol] = revision
            elif trailing_eps and trailing_eps > 0:
                # Fallback: use profit margin as an earnings quality proxy.
                # High margin relative to trailing EPS suggests earnings
                # sustainability; low margin suggests downward revision risk.
                margin = data.get("profit_margin")
                if margin is not None:
                    # Compare margin to a baseline (10%): above = positive revision.
                    # Clamp to [-0.5, 0.5] to match the forward-EPS path's
                    # typical range and prevent margin-based stocks from
                    # dominating the cross-sectional z-score ranking.
                    revision = max(-0.5, min(0.5, (margin - 0.10) / 0.10))
                    revision_data[symbol] = revision

        if not revision_data:
            return []

        # Cross-sectional percentile ranking
        all_revisions = list(revision_data.values())
        mean_rev = float(np.mean(all_revisions))
        std_rev = float(np.std(all_revisions)) if len(all_revisions) > 1 else 1.0

        signals = []
        for symbol, revision in revision_data.items():
            z = (revision - mean_rev) / std_rev if std_rev > 0 else 0.0
            signal_value = z * 30  # Scale to reasonable range
            signal_value = max(-100, min(100, signal_value))

            signals.append(
                Signal(
                    symbol=symbol,
                    signal_type=self.signal_type,
                    value=signal_value,
                    raw_value=revision,
                    confidence=0.5,  # Moderate: proxy rather than actual revisions
                    metadata={
                        "revision_pct": round(revision, 4),
                        "z_score": round(z, 4),
                        "signal_scope": "stock",
                    },
                )
            )

        return signals


class AccrualsQualitySignal(SignalGenerator):
    """
    Accruals quality signal: cash flow vs reported earnings divergence.

    When a company's reported earnings significantly exceed its operating
    cash flow (high accruals), future returns tend to be poor.  This is
    the "accruals anomaly" documented by Sloan (1996).

    Low accruals (cash earnings ≈ reported earnings) = high quality.
    High accruals (reported >> cash) = earnings manipulation risk.

    Uncorrelated to momentum and value individually, making it a strong
    diversifier in multi-factor portfolios.

    Approximation: (Net Income - Operating Cash Flow) / Total Assets
    Using available data: profit_margin as proxy for earnings quality
    combined with debt changes as proxy for accruals.
    """

    @property
    def signal_type(self) -> SignalType:
        return SignalType.ACCRUALS_QUALITY

    async def generate(
        self, symbols: list[str], market_data: dict[str, Any], **kwargs
    ) -> list[Signal]:
        accrual_data: dict[str, float] = {}

        for symbol in symbols:
            data = market_data.get(symbol, {})
            profit_margin = data.get("profit_margin")
            roe = data.get("roe")
            debt_to_equity = data.get("debt_to_equity")

            if profit_margin is None or roe is None:
                continue

            # Accruals proxy: high ROE with low profit margins suggests
            # earnings are being boosted by non-cash items or leverage.
            # Also, rapidly increasing debt suggests non-operating earnings.
            #
            # Low accruals score = high quality (cash earnings match reported)
            # High accruals score = low quality (reported > cash)
            accrual_proxy = 0.0
            if profit_margin > 0:
                # ROE/margin ratio: high ratio with high debt = red flag.
                # Clamped to [0, 3.0] to prevent extreme outliers (e.g.
                # margin=0.50 / roe=0.05 = 10.0) from dominating the
                # cross-sectional z-score ranking in small universes.
                earnings_quality = min(
                    3.0,
                    profit_margin / max(0.05, abs(roe)) if roe != 0 else 1.0,
                )

                # Debt-adjusted: high leverage amplifies accruals risk
                debt_penalty = 0.0
                if debt_to_equity is not None and debt_to_equity > 1.0:
                    debt_penalty = min(0.3, (debt_to_equity - 1.0) * 0.1)

                # Low quality ratio + high debt = high accruals (bad)
                accrual_proxy = earnings_quality - debt_penalty
            else:
                # Negative margins: heavily penalise
                accrual_proxy = -0.5

            accrual_data[symbol] = accrual_proxy

        if not accrual_data:
            return []

        # Cross-sectional ranking: high quality (low accruals) = positive signal
        all_values = list(accrual_data.values())
        mean_val = float(np.mean(all_values))
        std_val = float(np.std(all_values)) if len(all_values) > 1 else 1.0

        signals = []
        for symbol, accrual in accrual_data.items():
            z = (accrual - mean_val) / std_val if std_val > 0 else 0.0
            # Positive z = high quality (good) = bullish signal
            signal_value = z * 25
            signal_value = max(-100, min(100, signal_value))

            signals.append(
                Signal(
                    symbol=symbol,
                    signal_type=self.signal_type,
                    value=signal_value,
                    raw_value=accrual,
                    confidence=0.4,  # Lower confidence: proxy metric
                    metadata={
                        "accrual_proxy": round(accrual, 4),
                        "z_score": round(z, 4),
                        "signal_scope": "stock",
                    },
                )
            )

        return signals


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Cross-Asset / Macro
    "CreditSpreadSignal",
    "YieldCurveSignal",
    "VolatilityRegimeSignal",
    # Alternative Data
    "InsiderTransactionSignal",
    "ShortInterestSignal",
    "SeasonalitySignal",
    # Fundamental Regime
    "EarningsRevisionsSignal",
    "AccrualsQualitySignal",
]
