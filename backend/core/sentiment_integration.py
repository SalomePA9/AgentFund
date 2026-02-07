"""
Sentiment-Factor Integration Engine

Proprietary techniques for combining sentiment signals with quantitative
factor scores to amplify strategy accuracy and upside.

Five integration layers:
1. Convergence Amplification — reward agreement between factors and sentiment
2. Velocity-Momentum Resonance — sentiment acceleration confirms price trends
3. Cross-Source Triangulation — news/social agreement boosts confidence
4. Sentiment Dispersion Risk — news vs social spread signals uncertainty
5. Regime-Aware Factor Tilting — aggregate sentiment shifts factor weights
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
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
    momentum_tilt: float = 0.0
    value_tilt: float = 0.0
    quality_tilt: float = 0.0
    dividend_tilt: float = 0.0
    volatility_tilt: float = 0.0


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
    Combines quantitative factor scores with sentiment signals using five
    proprietary integration techniques.

    Usage::

        integrator = SentimentFactorIntegrator(strategy_type="momentum")
        results = integrator.integrate(factor_data, sentiment_data)
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
    ) -> dict[str, IntegratedScore]:
        """
        Run all five integration layers and return blended scores.

        Args:
            factor_data: symbol → {momentum_score, value_score, ...} (0-100)
            sentiment_data: symbol → SentimentInput

        Returns:
            symbol → IntegratedScore
        """
        # Step 0 — detect market regime from aggregate sentiment
        regime = self._detect_regime(sentiment_data)
        tilted_weights = self._apply_regime_tilts(regime)

        results: dict[str, IntegratedScore] = {}

        for symbol, factors in factor_data.items():
            sent = sentiment_data.get(symbol, SentimentInput(symbol=symbol))

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

            # Add convergence bonus (clamped)
            composite += convergence * self.convergence_strength

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

        if agg > 15 and breadth > 0.55:
            label = "risk_on"
        elif agg < -15 and breadth < 0.45:
            label = "risk_off"
        else:
            label = "neutral"

        return MarketRegime(label=label, aggregate_sentiment=agg, breadth=breadth)

    def _apply_regime_tilts(self, regime: MarketRegime) -> dict[str, float]:
        """
        Adjust base factor weights based on the detected regime.

        Risk-on: tilt toward momentum and sentiment.
        Risk-off: tilt toward quality, value, and low-vol.
        Neutral: use base weights unchanged.
        """
        weights = dict(self._base_weights)

        if regime.label == "risk_on":
            tilts = _RISK_ON_TILTS
        elif regime.label == "risk_off":
            tilts = _RISK_OFF_TILTS
        else:
            return weights

        for factor, delta in tilts.items():
            weights[factor] = weights.get(factor, 0.0) + delta

        # Ensure no negative weights, then renormalise
        for k in weights:
            weights[k] = max(0.0, weights[k])
        self._normalise_weights(weights)

        return weights

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
