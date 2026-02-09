"""
Macro Risk Overlay — Cross-Agent Risk Coordinator

This is the meta-layer that sits ABOVE individual agent strategies and
modulates position sizes based on uncorrelated macro signals.  It is the
architectural answer to: "when credit spreads blow out AND the vol curve
inverts, ALL agents should reduce position sizes regardless of their
individual strategy signals."

Design principles:
1. Never override individual strategy DIRECTION (buy/sell decisions)
2. Only scale position SIZES up or down based on macro conditions
3. Multiple signals must confirm before large adjustments (no single-signal overrides)
4. Graceful degradation: if a data source is unavailable, the overlay is neutral

Signal categories and their weights in the overlay:

┌──────────────────────────┬──────────┬─────────────────────────────┐
│ Signal                   │ Weight   │ Effect                      │
├──────────────────────────┼──────────┼─────────────────────────────┤
│ Credit Spread            │ 0.30     │ Widening → reduce risk      │
│ Volatility Regime        │ 0.30     │ VIX spike → reduce risk     │
│ Yield Curve              │ 0.20     │ Inversion → reduce risk     │
│ Seasonality              │ 0.10     │ Bad months → slight caution │
│ Insider Breadth          │ 0.10     │ Broad buying → add risk     │
└──────────────────────────┴──────────┴─────────────────────────────┘

Output: A risk_scale_factor in [0.25, 1.25] that multiplies all position sizes.
- 1.0 = no adjustment (normal conditions)
- 0.25 = maximum risk reduction (crisis: credit + vol + curve all bearish)
- 1.25 = maximum risk addition (all signals confirm low risk)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MacroSignalSnapshot:
    """Current state of all macro signals for risk overlay calculation."""

    # Credit spread signal (-100 to +100)
    credit_spread_signal: float = 0.0
    credit_spread_available: bool = False

    # Volatility regime signal (-100 to +100)
    vol_regime_signal: float = 0.0
    vol_regime_available: bool = False

    # Yield curve signal (-100 to +100)
    yield_curve_signal: float = 0.0
    yield_curve_available: bool = False

    # Seasonality signal (-100 to +100)
    seasonality_signal: float = 0.0
    seasonality_available: bool = False

    # Insider breadth signal (-100 to +100)
    # Aggregate across all stocks — positive = broad insider buying
    insider_breadth_signal: float = 0.0
    insider_breadth_available: bool = False


@dataclass
class OverlayResult:
    """Output of the macro risk overlay calculation."""

    # The primary output: multiply all position sizes by this factor
    risk_scale_factor: float = 1.0

    # Composite risk score: -100 (max danger) to +100 (max safety)
    composite_risk_score: float = 0.0

    # Individual signal contributions (for logging/transparency)
    signal_contributions: dict[str, float] = field(default_factory=dict)

    # Active warning flags for UI/notifications
    warnings: list[str] = field(default_factory=list)

    # Regime label for logging
    regime_label: str = "normal"

    # Raw signal snapshot used
    snapshot: MacroSignalSnapshot | None = None


class MacroRiskOverlay:
    """
    Cross-agent risk coordinator.

    Computes a single risk_scale_factor from macro signals that multiplies
    all agents' position sizes.  When multiple uncorrelated signals agree
    that risk is elevated, positions shrink.  When signals confirm safety,
    positions can be slightly upsized.

    Usage::

        overlay = MacroRiskOverlay()
        result = overlay.compute(macro_data, insider_data)
        # result.risk_scale_factor = 0.65  (reduce all positions by 35%)

    Integration with StrategyEngine::

        # In execute_for_agent():
        overlay_result = self._overlay.compute(macro_data, insider_data)
        for pos in output.positions:
            pos.target_weight *= overlay_result.risk_scale_factor
    """

    # Signal weights in the composite calculation
    SIGNAL_WEIGHTS = {
        "credit_spread": 0.30,
        "vol_regime": 0.30,
        "yield_curve": 0.20,
        "seasonality": 0.10,
        "insider_breadth": 0.10,
    }

    def __init__(self):
        """Initialise overlay with config settings."""
        from config import settings

        self.MIN_SIGNALS_REQUIRED = settings.macro_overlay_min_signals
        self.MIN_SCALE = settings.macro_overlay_min_scale
        self.MAX_SCALE = settings.macro_overlay_max_scale

    def compute(
        self,
        macro_data: dict[str, Any] | None = None,
        insider_data: dict[str, dict[str, Any]] | None = None,
        vol_regime_data: dict[str, Any] | None = None,
    ) -> OverlayResult:
        """
        Compute the risk overlay from available macro data.

        Args:
            macro_data: Output from FredClient.fetch_all() — contains
                credit_spread, yield_curve, treasury data.
            insider_data: Output from InsiderTransactionClient — per-symbol
                insider metrics (aggregated to breadth here).
            vol_regime_data: Output from VolatilityRegimeClient.fetch_regime().

        Returns:
            OverlayResult with risk_scale_factor and diagnostics.
        """
        macro_data = macro_data or {}
        insider_data = insider_data or {}
        vol_regime_data = vol_regime_data or {}

        # Step 1: Build signal snapshot from available data
        snapshot = self._build_snapshot(macro_data, insider_data, vol_regime_data)

        # Step 2: Count available signals
        available_count = sum(
            [
                snapshot.credit_spread_available,
                snapshot.vol_regime_available,
                snapshot.yield_curve_available,
                snapshot.seasonality_available,
                snapshot.insider_breadth_available,
            ]
        )

        # Step 3: If too few signals, return neutral (no adjustment)
        if available_count < self.MIN_SIGNALS_REQUIRED:
            logger.info(
                "MacroRiskOverlay: only %d/%d signals available — neutral",
                available_count,
                self.MIN_SIGNALS_REQUIRED,
            )
            return OverlayResult(
                risk_scale_factor=1.0,
                regime_label="insufficient_data",
                snapshot=snapshot,
            )

        # Step 4: Compute weighted composite risk score
        composite, contributions = self._compute_composite(snapshot)

        # Step 5: Convert composite score to risk scale factor
        risk_scale = self._score_to_scale(composite)

        # Step 6: Generate warning flags
        warnings = self._generate_warnings(snapshot, composite)

        # Step 7: Determine regime label
        if composite < -40:
            regime_label = "high_risk"
        elif composite < -15:
            regime_label = "elevated_risk"
        elif composite > 30:
            regime_label = "low_risk"
        else:
            regime_label = "normal"

        result = OverlayResult(
            risk_scale_factor=round(risk_scale, 4),
            composite_risk_score=round(composite, 2),
            signal_contributions=contributions,
            warnings=warnings,
            regime_label=regime_label,
            snapshot=snapshot,
        )

        logger.info(
            "MacroRiskOverlay: composite=%.1f scale=%.2f regime=%s "
            "signals=%d warnings=%d",
            composite,
            risk_scale,
            regime_label,
            available_count,
            len(warnings),
        )

        return result

    def _build_snapshot(
        self,
        macro_data: dict[str, Any],
        insider_data: dict[str, dict[str, Any]],
        vol_regime_data: dict[str, Any],
    ) -> MacroSignalSnapshot:
        """Extract signal values from raw data into a snapshot."""
        snapshot = MacroSignalSnapshot()

        # Credit spread
        credit = macro_data.get("credit_spread", {})
        if credit.get("current") is not None:
            z = credit.get("z_score", 0.0)
            roc = credit.get("rate_of_change", 0.0)
            # Inverted: high spread = bearish (negative signal)
            snapshot.credit_spread_signal = max(-100, min(100, -z * 30 - roc * 5))
            snapshot.credit_spread_available = True

        # Volatility regime
        if vol_regime_data.get("vix_current") is not None:
            vix_current = vol_regime_data["vix_current"]
            signal = vol_regime_data.get("regime_score", 0.0) * 100

            # Amplify extremes (matching VolatilityRegimeSignal.generate):
            # VIX > 35 is crisis territory, VIX < 12 is extreme calm
            if vix_current > 35:
                signal = min(signal, -80)
            elif vix_current < 12:
                signal = max(signal, 60)

            snapshot.vol_regime_signal = max(-100, min(100, signal))
            snapshot.vol_regime_available = True

        # Yield curve
        yc = macro_data.get("yield_curve", {})
        if yc.get("current") is not None:
            current = yc["current"]
            roc = yc.get("rate_of_change", 0.0)
            snapshot.yield_curve_signal = max(-100, min(100, current * 50 + roc * 20))
            snapshot.yield_curve_available = True

        # Seasonality (always available — purely calendar-based)
        # Computed synchronously since it only uses calendar data.
        from core.strategies.uncorrelated_signals import SeasonalitySignal
        from datetime import datetime, timezone

        import calendar as cal_mod

        now = datetime.now(timezone.utc)
        month = now.month
        day = now.day
        _, days_in_month = cal_mod.monthrange(now.year, month)

        monthly_bias = SeasonalitySignal.MONTHLY_BIAS.get(month, 0.0)
        base_signal = monthly_bias / 0.015 * 60

        # End-of-month effect: last 3 days tend to be positive
        eom_boost = 15.0 if day >= days_in_month - 2 else 0.0

        # End-of-quarter additional boost
        eoq_boost = 10.0 if month in (3, 6, 9, 12) and day >= days_in_month - 2 else 0.0

        snapshot.seasonality_signal = max(
            -100, min(100, base_signal + eom_boost + eoq_boost)
        )
        snapshot.seasonality_available = True

        # Insider breadth: aggregate across all symbols
        if insider_data:
            net_sentiments = [
                d.get("net_sentiment", 0)
                for d in insider_data.values()
                if d.get("net_sentiment") is not None
            ]
            if net_sentiments:
                breadth = float(np.mean(net_sentiments))
                snapshot.insider_breadth_signal = max(-100.0, min(100.0, breadth))
                snapshot.insider_breadth_available = True

        return snapshot

    def _compute_composite(
        self, snapshot: MacroSignalSnapshot
    ) -> tuple[float, dict[str, float]]:
        """
        Compute weighted composite risk score from available signals.

        Re-normalises weights to account for missing signals so that
        available signals don't get diluted.
        """
        signal_map = {
            "credit_spread": (
                snapshot.credit_spread_signal,
                snapshot.credit_spread_available,
            ),
            "vol_regime": (
                snapshot.vol_regime_signal,
                snapshot.vol_regime_available,
            ),
            "yield_curve": (
                snapshot.yield_curve_signal,
                snapshot.yield_curve_available,
            ),
            "seasonality": (
                snapshot.seasonality_signal,
                snapshot.seasonality_available,
            ),
            "insider_breadth": (
                snapshot.insider_breadth_signal,
                snapshot.insider_breadth_available,
            ),
        }

        # Only include available signals
        active_weights: dict[str, float] = {}
        active_signals: dict[str, float] = {}

        for name, (value, available) in signal_map.items():
            if available and value is not None and np.isfinite(value):
                active_weights[name] = self.SIGNAL_WEIGHTS[name]
                active_signals[name] = float(value)

        # Re-normalise weights
        total_weight = sum(active_weights.values())
        if total_weight <= 0:
            return 0.0, {}

        # Cap each renormalized weight at 0.50 to prevent a single
        # weak signal (e.g. seasonality at original weight 0.10) from
        # dominating the composite when stronger signals are unavailable.
        # Excess weight from capped signals is redistributed proportionally
        # to uncapped signals so weights still sum to 1.0.
        MAX_NORM_WEIGHT = 0.50

        norm_weights: dict[str, float] = {}
        for name in active_signals:
            norm_weights[name] = active_weights[name] / total_weight

        # Iteratively cap and redistribute until stable
        for _ in range(5):
            excess = 0.0
            uncapped_total = 0.0
            for name, w in norm_weights.items():
                if w > MAX_NORM_WEIGHT:
                    excess += w - MAX_NORM_WEIGHT
                    norm_weights[name] = MAX_NORM_WEIGHT
                else:
                    uncapped_total += w

            if excess <= 0:
                break

            if uncapped_total > 0:
                for name in norm_weights:
                    if norm_weights[name] < MAX_NORM_WEIGHT:
                        norm_weights[name] += excess * (
                            norm_weights[name] / uncapped_total
                        )
            else:
                break

        contributions: dict[str, float] = {}
        composite = 0.0

        for name in active_signals:
            contribution = active_signals[name] * norm_weights[name]
            contributions[name] = round(contribution, 4)
            composite += contribution

        return composite, contributions

    def _score_to_scale(self, composite: float) -> float:
        """
        Convert composite risk score (-100 to +100) to position scale factor.

        Mapping (with default MIN_SCALE=0.25, MAX_SCALE=1.25):
        - composite = -100 → scale = 0.25 (75% position reduction)
        - composite =  -50 → scale = 0.625 (37.5% reduction)
        - composite =    0 → scale = 1.00 (no change)
        - composite =  +50 → scale = 1.125 (12.5% increase)
        - composite = +100 → scale = 1.25 (25% increase)

        Asymmetric: cutting risk is more aggressive than adding risk.
        This reflects the asymmetry of losses (a 50% loss requires
        a 100% gain to recover).
        """
        # Guard against NaN/Inf propagation from corrupted upstream data
        if not np.isfinite(composite):
            logger.warning("MacroRiskOverlay: composite is NaN/Inf — returning neutral")
            return 1.0

        if composite <= 0:
            # Bearish regime: scale from 1.0 down to MIN_SCALE
            # Linear mapping: -100 → MIN_SCALE, 0 → 1.0
            scale = 1.0 + (composite / 100.0) * (1.0 - self.MIN_SCALE)
        else:
            # Bullish regime: scale from 1.0 up to MAX_SCALE (less aggressively)
            scale = 1.0 + (composite / 100.0) * (self.MAX_SCALE - 1.0)

        return max(self.MIN_SCALE, min(self.MAX_SCALE, scale))

    def _generate_warnings(
        self, snapshot: MacroSignalSnapshot, composite: float
    ) -> list[str]:
        """Generate human-readable warning messages for extreme conditions."""
        warnings = []

        if snapshot.credit_spread_available and snapshot.credit_spread_signal < -50:
            warnings.append(
                "Credit spreads widening significantly — credit markets pricing risk"
            )

        if snapshot.vol_regime_available and snapshot.vol_regime_signal < -50:
            warnings.append(
                "Elevated volatility regime — VIX elevated or term structure inverted"
            )

        if snapshot.yield_curve_available and snapshot.yield_curve_signal < -30:
            warnings.append("Yield curve flat or inverted — recession risk elevated")

        if composite < -60:
            warnings.append(
                "CRITICAL: Multiple macro signals confirm high risk — "
                "position sizes reduced to minimum"
            )
        elif composite < -30:
            warnings.append("WARNING: Macro risk elevated — position sizes reduced")

        # Positive warning for risk-on
        if composite > 40:
            warnings.append(
                "Macro conditions favourable — all signals confirm low risk environment"
            )

        return warnings


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "MacroSignalSnapshot",
    "OverlayResult",
    "MacroRiskOverlay",
]
