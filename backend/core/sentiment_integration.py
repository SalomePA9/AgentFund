"""
Sentiment-Factor Integration Engine

Proprietary techniques for combining sentiment signals with quantitative
factor scores to amplify strategy accuracy and upside.

Seven integration layers:
1. Convergence Amplification — reward agreement between factors and sentiment
2. Velocity-Momentum Resonance — sentiment acceleration confirms price trends
3. Cross-Source Triangulation — news/social agreement boosts confidence
4. Sentiment Dispersion Risk — news vs social spread signals uncertainty
5. Regime-Aware Factor Tilting — aggregate sentiment shifts factor weights
6. Temporal Persistence — sustained multi-day sentiment weighs more than noise
7. MA-Sentiment Confluence — price above MA200 + persistent bullish sentiment
                              triggers a strong buy signal (and vice versa)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SentimentInput:
    """Sentiment data for a single stock, sourced from the stocks table."""

    symbol: str
    news_sentiment: float | None = None  # -100 to +100
    social_sentiment: float | None = None  # -100 to +100
    combined_sentiment: float | None = None  # -100 to +100
    velocity: float | None = None  # daily rate of change

    # Temporal features (populated by TemporalSentimentAnalyzer)
    streak_days: int = 0  # consecutive days positive (>0) or negative (<0)
    trend_slope: float | None = None  # linear regression slope over window
    persistence: float | None = None  # 0-1, low variance = high persistence
    is_breakout: bool = False  # sudden sentiment regime change


@dataclass
class IntegratedScore:
    """Output of the sentiment-factor integration for a single stock."""

    symbol: str

    # Original factor scores (0-100 percentile)
    momentum_score: float
    value_score: float
    quality_score: float
    dividend_score: float
    volatility_score: float

    # Sentiment-derived scores (0-100 normalised)
    sentiment_score: float = 50.0

    # Proprietary integration outputs
    convergence_bonus: float = 0.0  # [-15, +15] — added to composite
    resonance_multiplier: float = 1.0  # [0.8, 1.2] — scales momentum
    triangulation_confidence: float = 1.0  # [0.5, 1.0]
    dispersion_risk: float = 0.0  # [0, 1] — higher = more uncertain
    temporal_bonus: float = 0.0  # [-10, +10] — persistence reward/penalty
    confluence_bonus: float = 0.0  # [-12, +12] — MA+sentiment alignment

    # Final blended composite
    composite_score: float = 50.0

    # Regime-tilted factor weights used for this stock
    factor_weights: dict[str, float] = field(default_factory=dict)


@dataclass
class MarketRegime:
    """Detected market regime from aggregate sentiment."""

    label: str  # "risk_on", "neutral", "risk_off"
    aggregate_sentiment: float  # average combined_sentiment across universe
    breadth: float  # fraction of stocks with positive sentiment
    regime_strength: float = 0.0  # continuous [-1, +1]: -1=risk_off, +1=risk_on
    momentum_tilt: float = 0.0
    value_tilt: float = 0.0
    quality_tilt: float = 0.0
    dividend_tilt: float = 0.0
    volatility_tilt: float = 0.0


# ---------------------------------------------------------------------------
# Temporal Sentiment Analyzer
# ---------------------------------------------------------------------------


class TemporalSentimentAnalyzer:
    """
    Computes temporal features from the sentiment_history table and enriches
    SentimentInput objects with streak, trend, persistence, and breakout data.

    Usage::

        analyzer = TemporalSentimentAnalyzer(db_client=supabase)
        enriched = await analyzer.enrich(sentiment_data, lookback_days=30)
    """

    def __init__(self, db_client: Any = None):
        self._db = db_client

    async def enrich(
        self,
        sentiment_data: dict[str, SentimentInput],
        lookback_days: int = 30,
    ) -> dict[str, SentimentInput]:
        """
        Fetch sentiment history and compute temporal features for all symbols.

        Modifies SentimentInput objects in-place and returns the same dict.
        """
        if not self._db:
            logger.warning("No DB client — skipping temporal enrichment")
            return sentiment_data

        cutoff = (datetime.utcnow() - timedelta(days=lookback_days)).isoformat()
        history_by_symbol = await self._fetch_history(cutoff)

        for symbol, sent in sentiment_data.items():
            records = history_by_symbol.get(symbol, [])
            if len(records) < 2:
                continue

            # Records are ordered oldest → newest
            combined_series = [
                r["combined_sentiment"]
                for r in records
                if r.get("combined_sentiment") is not None
            ]
            if len(combined_series) < 2:
                continue

            sent.streak_days = self._calc_streak(combined_series)
            sent.trend_slope = self._calc_trend_slope(combined_series)
            sent.persistence = self._calc_persistence(combined_series)
            sent.is_breakout = self._calc_breakout(combined_series)

        enriched_count = sum(1 for s in sentiment_data.values() if s.streak_days != 0)
        logger.info(
            "Temporal enrichment: %d/%d symbols with history",
            enriched_count,
            len(sentiment_data),
        )
        return sentiment_data

    async def _fetch_history(self, cutoff_iso: str) -> dict[str, list[dict]]:
        """Fetch sentiment_history rows since cutoff, grouped by symbol."""
        try:
            result = (
                self._db.table("sentiment_history")
                .select("symbol, combined_sentiment, recorded_at")
                .gte("recorded_at", cutoff_iso)
                .order("recorded_at", desc=False)
                .execute()
            )
            grouped: dict[str, list[dict]] = {}
            for row in result.data:
                sym = row.get("symbol")
                if sym:
                    grouped.setdefault(sym, []).append(row)
            return grouped
        except Exception:
            logger.warning("Failed to fetch sentiment_history", exc_info=True)
            return {}

    # ------------------------------------------------------------------
    # Feature calculations
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_streak(series: list[float]) -> int:
        """
        Count consecutive days at the end of the series where sentiment
        stays on the same side of zero.

        Returns positive int for bullish streaks, negative for bearish.
        """
        if not series:
            return 0

        last_sign = 1 if series[-1] >= 0 else -1
        streak = 0
        for val in reversed(series):
            current_sign = 1 if val >= 0 else -1
            if current_sign == last_sign:
                streak += 1
            else:
                break
        return streak * last_sign

    @staticmethod
    def _calc_trend_slope(series: list[float]) -> float:
        """
        Linear regression slope of combined sentiment over the window.

        Positive slope = sentiment improving over time.
        Normalised to roughly [-5, +5] range (points per day).
        """
        n = len(series)
        if n < 3:
            return 0.0
        x = np.arange(n, dtype=float)
        y = np.array(series, dtype=float)
        # Simple least-squares slope: Σ(x-x̄)(y-ȳ) / Σ(x-x̄)²
        x_mean = x.mean()
        y_mean = y.mean()
        numerator = float(np.sum((x - x_mean) * (y - y_mean)))
        denominator = float(np.sum((x - x_mean) ** 2))
        if denominator == 0:
            return 0.0
        return numerator / denominator

    @staticmethod
    def _calc_persistence(series: list[float]) -> float:
        """
        Measures how stable/persistent sentiment has been.

        Low standard deviation → high persistence (conviction).
        Returns 0-1 where 1 = perfectly stable, 0 = extremely noisy.
        """
        if len(series) < 3:
            return 0.5
        std = float(np.std(series))
        # Normalise: std of 0 → persistence 1.0, std of 50+ → persistence ~0
        return 1.0 / (1.0 + (std / 20.0) ** 1.5)

    @staticmethod
    def _calc_breakout(series: list[float], recent_days: int = 3) -> bool:
        """
        Detect a sentiment regime change: the recent window diverges
        significantly from the prior baseline.

        A breakout occurs when the average of the last `recent_days`
        differs from the prior average by more than 30 points and
        crosses zero.
        """
        if len(series) < recent_days + 5:
            return False

        recent_avg = float(np.mean(series[-recent_days:]))
        prior_avg = float(np.mean(series[:-recent_days]))

        # Must cross zero and differ by ≥30 points
        crossed_zero = (recent_avg >= 0) != (prior_avg >= 0)
        large_move = abs(recent_avg - prior_avg) >= 30.0

        return crossed_zero and large_move


# ---------------------------------------------------------------------------
# Default factor weights by strategy type
# ---------------------------------------------------------------------------

DEFAULT_FACTOR_WEIGHTS: dict[str, dict[str, float]] = {
    "momentum": {
        "momentum": 0.55,
        "value": 0.00,
        "quality": 0.10,
        "dividend": 0.00,
        "volatility": 0.10,
        "sentiment": 0.25,
    },
    "quality_value": {
        "momentum": 0.00,
        "value": 0.30,
        "quality": 0.30,
        "dividend": 0.05,
        "volatility": 0.10,
        "sentiment": 0.25,
    },
    "quality_momentum": {
        "momentum": 0.30,
        "value": 0.00,
        "quality": 0.25,
        "dividend": 0.00,
        "volatility": 0.10,
        "sentiment": 0.35,
    },
    "dividend_growth": {
        "momentum": 0.00,
        "value": 0.15,
        "quality": 0.25,
        "dividend": 0.25,
        "volatility": 0.15,
        "sentiment": 0.20,
    },
}

# Regime tilt deltas applied on top of base weights
_RISK_ON_TILTS = {
    "momentum": +0.08,
    "value": -0.04,
    "quality": -0.04,
    "dividend": -0.02,
    "volatility": -0.04,
    "sentiment": +0.06,
}
_RISK_OFF_TILTS = {
    "momentum": -0.08,
    "value": +0.04,
    "quality": +0.06,
    "dividend": +0.04,
    "volatility": +0.04,
    "sentiment": -0.10,
}


# ---------------------------------------------------------------------------
# Core integrator
# ---------------------------------------------------------------------------


class SentimentFactorIntegrator:
    """
    Combines quantitative factor scores with sentiment signals using seven
    proprietary integration techniques.

    Usage::

        integrator = SentimentFactorIntegrator(strategy_type="momentum")
        results = integrator.integrate(factor_data, sentiment_data, market_data)
        # results: dict[symbol, IntegratedScore]
    """

    def __init__(
        self,
        strategy_type: str = "momentum",
        sentiment_weight: float = 0.25,
        convergence_strength: float = 1.0,
        resonance_strength: float = 1.0,
    ):
        self.strategy_type = strategy_type
        self.sentiment_weight = max(0.0, min(0.5, sentiment_weight))
        self.convergence_strength = convergence_strength
        self.resonance_strength = resonance_strength

        # Resolve base factor weights
        base = DEFAULT_FACTOR_WEIGHTS.get(
            strategy_type, DEFAULT_FACTOR_WEIGHTS["momentum"]
        )
        # Override sentiment weight if caller specifies
        self._base_weights = {**base, "sentiment": self.sentiment_weight}
        self._normalise_weights(self._base_weights)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def integrate(
        self,
        factor_data: dict[str, dict[str, float]],
        sentiment_data: dict[str, SentimentInput],
        market_data: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, IntegratedScore]:
        """
        Run all seven integration layers and return blended scores.

        Args:
            factor_data: symbol → {momentum_score, value_score, ...} (0-100)
            sentiment_data: symbol → SentimentInput (with temporal fields)
            market_data: symbol → {current_price, ma_200, ...} for confluence

        Returns:
            symbol → IntegratedScore
        """
        market_data = market_data or {}

        # Step 0 — detect market regime from aggregate sentiment
        regime = self._detect_regime(sentiment_data)
        tilted_weights = self._apply_regime_tilts(regime)

        results: dict[str, IntegratedScore] = {}

        for symbol, factors in factor_data.items():
            sent = sentiment_data.get(symbol, SentimentInput(symbol=symbol))
            mkt = market_data.get(symbol, {})

            # Normalise sentiment to 0-100 scale (from -100..+100)
            sentiment_score = self._normalise_sentiment(sent)

            # Layer 1: Convergence amplification
            convergence = self._calc_convergence(factors, sent)

            # Layer 2: Velocity-momentum resonance
            resonance = self._calc_resonance(factors.get("momentum_score", 50.0), sent)

            # Layer 3: Cross-source triangulation
            triangulation = self._calc_triangulation(sent)

            # Layer 4: Sentiment dispersion risk
            dispersion = self._calc_dispersion(sent)

            # Layer 5: Regime tilting (already applied via tilted_weights)

            # Layer 6: Temporal persistence bonus
            temporal = self._calc_temporal_bonus(sent)

            # Layer 7: MA-sentiment confluence
            confluence = self._calc_ma_confluence(sent, mkt)

            # Apply resonance to momentum before blending
            adjusted_momentum = factors.get("momentum_score", 50.0) * resonance

            # Build weighted composite with regime-tilted weights
            raw_factors = {
                "momentum": adjusted_momentum,
                "value": factors.get("value_score", 50.0),
                "quality": factors.get("quality_score", 50.0),
                "dividend": factors.get("dividend_score", 50.0),
                "volatility": factors.get("volatility_score", 50.0),
                "sentiment": sentiment_score,
            }
            composite = sum(raw_factors[k] * tilted_weights[k] for k in tilted_weights)

            # Add convergence bonus
            composite += convergence * self.convergence_strength

            # Add temporal persistence bonus
            composite += temporal

            # Add MA-sentiment confluence bonus
            composite += confluence

            # Scale by triangulation confidence and dispersion risk
            confidence_scale = triangulation * (1.0 - 0.3 * dispersion)
            composite = 50.0 + (composite - 50.0) * confidence_scale

            # Clamp to [0, 100]
            composite = max(0.0, min(100.0, composite))

            results[symbol] = IntegratedScore(
                symbol=symbol,
                momentum_score=factors.get("momentum_score", 50.0),
                value_score=factors.get("value_score", 50.0),
                quality_score=factors.get("quality_score", 50.0),
                dividend_score=factors.get("dividend_score", 50.0),
                volatility_score=factors.get("volatility_score", 50.0),
                sentiment_score=round(sentiment_score, 2),
                convergence_bonus=round(convergence, 4),
                resonance_multiplier=round(resonance, 4),
                triangulation_confidence=round(triangulation, 4),
                dispersion_risk=round(dispersion, 4),
                temporal_bonus=round(temporal, 4),
                confluence_bonus=round(confluence, 4),
                composite_score=round(composite, 2),
                factor_weights=tilted_weights,
            )

        logger.info(
            "Integrated %d stocks | regime=%s (agg=%.1f) | strategy=%s",
            len(results),
            regime.label,
            regime.aggregate_sentiment,
            self.strategy_type,
        )
        return results

    # ------------------------------------------------------------------
    # Layer 1 — Convergence Amplification
    # ------------------------------------------------------------------

    def _calc_convergence(
        self, factors: dict[str, float], sent: SentimentInput
    ) -> float:
        """
        Reward when sentiment direction agrees with the dominant factor signal.

        A stock in the top factor quintile with bullish sentiment gets a bonus.
        Disagreement (strong factors + bearish sentiment) applies a penalty.

        Returns a value in [-15, +15].
        """
        combined = sent.combined_sentiment
        if combined is None:
            return 0.0

        # Compute a "factor direction" from the average factor percentile.
        # >50 = bullish factor signal, <50 = bearish.
        avg_factor = np.mean(
            [
                factors.get("momentum_score", 50.0),
                factors.get("quality_score", 50.0),
                factors.get("value_score", 50.0),
            ]
        )
        factor_z = (avg_factor - 50.0) / 50.0  # [-1, +1]
        sentiment_z = combined / 100.0  # [-1, +1]

        # Product captures agreement: both positive → positive, mixed → negative
        raw = factor_z * sentiment_z

        # Scale to [-15, +15] range
        return raw * 15.0

    # ------------------------------------------------------------------
    # Layer 2 — Velocity-Momentum Resonance
    # ------------------------------------------------------------------

    def _calc_resonance(self, momentum_score: float, sent: SentimentInput) -> float:
        """
        Sentiment velocity aligned with momentum direction amplifies the
        momentum signal; opposing velocity dampens it.

        Returns a multiplier in [0.8, 1.2].
        """
        velocity = sent.velocity
        if velocity is None:
            return 1.0

        # Momentum direction: >50 = bullish, <50 = bearish
        mom_direction = 1.0 if momentum_score >= 50.0 else -1.0

        # Normalise velocity: typical range roughly -10..+10 pts/day
        norm_velocity = max(-1.0, min(1.0, velocity / 10.0))

        # Agreement multiplier
        alignment = mom_direction * norm_velocity  # [-1, +1]

        # Map to [0.8, 1.2]
        return 1.0 + alignment * 0.2 * self.resonance_strength

    # ------------------------------------------------------------------
    # Layer 3 — Cross-Source Triangulation
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_triangulation(sent: SentimentInput) -> float:
        """
        Confidence is highest when news and social sentiment agree in sign
        and magnitude. Disagreement reduces confidence.

        Returns a value in [0.5, 1.0].
        """
        news = sent.news_sentiment
        social = sent.social_sentiment

        if news is None or social is None:
            return 0.75  # Partial data → moderate confidence

        # Same sign = agreement
        if (news >= 0) == (social >= 0):
            # Scale by how close they are in magnitude
            diff = abs(news - social) / 200.0  # 0..1
            return 1.0 - diff * 0.3  # [0.7, 1.0]
        else:
            # Opposite signs — significant disagreement
            spread = abs(news - social) / 200.0
            return max(0.5, 0.7 - spread * 0.4)

    # ------------------------------------------------------------------
    # Layer 4 — Sentiment Dispersion Risk
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_dispersion(sent: SentimentInput) -> float:
        """
        Measures divergence between news and social sentiment as a proxy
        for information uncertainty.

        Returns a value in [0, 1]. Higher = more uncertain.
        """
        news = sent.news_sentiment
        social = sent.social_sentiment

        if news is None or social is None:
            return 0.3  # Partial data → moderate uncertainty

        spread = abs(news - social)  # 0..200
        # Sigmoid-like mapping: 0 at spread=0, ~0.5 at spread=50, ~0.9 at spread=150
        return 1.0 - 1.0 / (1.0 + (spread / 60.0) ** 1.5)

    # ------------------------------------------------------------------
    # Layer 5 — Regime-Aware Factor Tilting
    # ------------------------------------------------------------------

    def _detect_regime(self, sentiment_data: dict[str, SentimentInput]) -> MarketRegime:
        """
        Detect market regime from aggregate sentiment across the universe.

        Uses continuous interpolation instead of hard thresholds so the
        regime transitions smoothly.  A ``regime_strength`` in [0, 1]
        indicates how strongly the regime leans risk-on or risk-off,
        which is used by ``_apply_regime_tilts`` to scale the tilt
        proportionally rather than applying full tilts at a binary edge.
        """
        scores = [
            s.combined_sentiment
            for s in sentiment_data.values()
            if s.combined_sentiment is not None
        ]

        if not scores:
            return MarketRegime(label="neutral", aggregate_sentiment=0.0, breadth=0.5)

        agg = float(np.mean(scores))
        breadth = sum(1 for s in scores if s > 0) / len(scores)

        # Continuous regime strength via sigmoid-like mapping.
        # Maps aggregate sentiment to [-1, +1] where:
        #   +1 = strong risk-on, -1 = strong risk-off, 0 = neutral.
        # The sigmoid saturates around ±40 so very extreme sentiment
        # doesn't produce unbounded values.
        regime_strength = float(np.tanh(agg / 25.0))

        # Also incorporate breadth (fraction of positive stocks)
        # Breadth of 0.5 = neutral, 0.7+ = risk-on, 0.3- = risk-off
        breadth_signal = (breadth - 0.5) * 2.0  # [-1, +1]
        regime_strength = 0.6 * regime_strength + 0.4 * breadth_signal
        regime_strength = max(-1.0, min(1.0, regime_strength))

        # Label for logging (still useful for human-readable output)
        if regime_strength > 0.2:
            label = "risk_on"
        elif regime_strength < -0.2:
            label = "risk_off"
        else:
            label = "neutral"

        regime = MarketRegime(label=label, aggregate_sentiment=agg, breadth=breadth)
        # Store the continuous strength for proportional tilt scaling
        regime.regime_strength = regime_strength
        return regime

    def _apply_regime_tilts(self, regime: MarketRegime) -> dict[str, float]:
        """
        Adjust base factor weights based on the detected regime.

        Uses the continuous ``regime_strength`` to scale tilts
        proportionally.  A strength of +1.0 applies the full risk-on
        tilt; +0.3 applies 30% of the tilt; 0.0 leaves weights
        unchanged; -0.5 applies 50% of the risk-off tilt; etc.
        """
        weights = dict(self._base_weights)
        strength = regime.regime_strength

        if abs(strength) < 0.05:
            return weights  # near-neutral: no tilt needed

        # Pick tilt direction based on sign; scale by magnitude
        tilts = _RISK_ON_TILTS if strength > 0 else _RISK_OFF_TILTS
        scale = abs(strength)

        for factor, delta in tilts.items():
            weights[factor] = weights.get(factor, 0.0) + delta * scale

        # Ensure no negative weights, then renormalise
        for k in weights:
            weights[k] = max(0.0, weights[k])
        self._normalise_weights(weights)

        return weights

    # ------------------------------------------------------------------
    # Layer 6 — Temporal Persistence
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_temporal_bonus(sent: SentimentInput) -> float:
        """
        Reward sustained sentiment (multi-day streaks) and penalise noisy
        single-day signals.

        A stock with a 10-day bullish streak and high persistence gets a
        bonus of up to +10.  A 1-day blip with low persistence gets ~0.
        Breakout events receive an extra kick.

        Returns a value in [-10, +10].
        """
        streak = sent.streak_days
        persistence = sent.persistence
        is_breakout = sent.is_breakout
        trend_slope = sent.trend_slope

        if persistence is None:
            persistence = 0.5

        # Streak contribution: log-scaled so marginal gains diminish
        # abs(streak)=1 → ~0, =5 → ~3.2, =10 → ~4.6, =20 → ~6.0
        if streak == 0:
            streak_component = 0.0
        else:
            sign = 1.0 if streak > 0 else -1.0
            streak_component = sign * np.log1p(abs(streak)) * 2.0

        # Persistence multiplier: high persistence amplifies, low dampens
        # persistence=1.0 → 1.3x, persistence=0.0 → 0.4x
        persistence_mult = 0.4 + 0.9 * persistence

        # Trend slope contribution: adds up to ±2 points
        slope_component = 0.0
        if trend_slope is not None:
            slope_component = max(-2.0, min(2.0, trend_slope * 0.5))

        # Breakout bonus: a regime change gets an extra ±2 points
        breakout_bonus = 0.0
        if is_breakout and sent.combined_sentiment is not None:
            breakout_bonus = 2.0 if sent.combined_sentiment >= 0 else -2.0

        raw = (streak_component * persistence_mult) + slope_component + breakout_bonus
        return max(-10.0, min(10.0, raw))

    # ------------------------------------------------------------------
    # Layer 7 — MA-Sentiment Confluence
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_ma_confluence(sent: SentimentInput, market: dict[str, Any]) -> float:
        """
        Generates a strong buy/sell signal when price position relative to
        the 200-day moving average aligns with sustained sentiment.

        Price above MA200 + multi-day bullish sentiment → buy bonus.
        Price below MA200 + multi-day bearish sentiment → sell penalty.
        Misalignment or missing data → no effect.

        Returns a value in [-12, +12].
        """
        price = market.get("current_price")
        ma_200 = market.get("ma_200")

        if price is None or ma_200 is None:
            return 0.0

        try:
            price = float(price)
            ma_200 = float(ma_200)
        except (TypeError, ValueError):
            return 0.0

        if ma_200 <= 0:
            return 0.0

        streak = sent.streak_days

        # Price position: how far above/below MA200 (as fraction)
        ma_deviation = (price - ma_200) / ma_200  # e.g., +0.05 = 5% above

        # Check for alignment
        price_bullish = ma_deviation > 0.0
        sentiment_bullish = streak > 0
        price_bearish = ma_deviation < 0.0
        sentiment_bearish = streak < 0

        if price_bullish and sentiment_bullish:
            # Both bullish — strength scales with streak length and MA distance
            streak_factor = min(1.0, abs(streak) / 10.0)  # saturates at 10 days
            ma_factor = min(1.0, abs(ma_deviation) / 0.10)  # saturates at 10% above
            return 12.0 * streak_factor * ma_factor

        if price_bearish and sentiment_bearish:
            # Both bearish — penalty scales similarly
            streak_factor = min(1.0, abs(streak) / 10.0)
            ma_factor = min(1.0, abs(ma_deviation) / 0.10)
            return -12.0 * streak_factor * ma_factor

        if (price_bullish and sentiment_bearish) or (
            price_bearish and sentiment_bullish
        ):
            # Divergence — mild penalty for conflicting signals
            streak_factor = min(1.0, abs(streak) / 10.0)
            return -3.0 * streak_factor

        return 0.0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_sentiment(sent: SentimentInput) -> float:
        """Convert combined sentiment (-100..+100) to 0..100 scale."""
        combined = sent.combined_sentiment
        if combined is None:
            return 50.0  # neutral
        return max(0.0, min(100.0, (combined + 100.0) / 2.0))

    @staticmethod
    def _normalise_weights(weights: dict[str, float]) -> None:
        """Normalise weight dict in-place to sum to 1.0."""
        total = sum(weights.values())
        if total > 0:
            for k in weights:
                weights[k] = round(weights[k] / total, 4)
