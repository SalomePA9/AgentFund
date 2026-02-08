"""
Volatility Regime Detection

Fetches VIX and VIX futures term structure data to determine the current
volatility regime.  This is structurally uncorrelated to equity price
momentum and retail sentiment.

Signals produced:
1. VIX Level — absolute fear gauge
2. VIX Term Structure — contango (calm) vs backwardation (panic)
3. Realized vs Implied Vol Spread — risk premium indicator
4. VIX Rate of Change — velocity of fear

Data sources:
- VIX spot: Yahoo Finance (^VIX)  — free
- VIX futures proxy: VIX 3-month (^VIX3M) vs VIX spot — free via yfinance
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import numpy as np
import yfinance as yf

logger = logging.getLogger(__name__)


class VolatilityRegimeClient:
    """
    Fetches VIX data and computes volatility regime features.

    Usage::

        client = VolatilityRegimeClient()
        regime = await client.fetch_regime(lookback_days=60)
        # regime = {
        #     "vix_current": 18.5,
        #     "vix_term_structure": 0.05,  # positive = contango
        #     "vix_z_score": -0.3,
        #     "vix_percentile": 35.0,
        #     "regime": "calm",  # calm, elevated, crisis
        #     ...
        # }
    """

    VIX_TICKER = "^VIX"
    VIX3M_TICKER = "^VIX3M"
    SPY_TICKER = "SPY"

    async def fetch_regime(self, lookback_days: int = 120) -> dict[str, Any]:
        """Fetch VIX data and compute regime indicators."""
        try:
            vix_data, vix3m_data, spy_data = await asyncio.gather(
                asyncio.to_thread(self._fetch_ticker, self.VIX_TICKER, lookback_days),
                asyncio.to_thread(self._fetch_ticker, self.VIX3M_TICKER, lookback_days),
                asyncio.to_thread(self._fetch_ticker, self.SPY_TICKER, lookback_days),
            )

            result = self._compute_regime(vix_data, vix3m_data, spy_data)
            return result

        except Exception:
            logger.warning("Failed to fetch volatility regime data", exc_info=True)
            return self._default_regime()

    @staticmethod
    def _fetch_ticker(ticker: str, lookback_days: int) -> dict[str, Any]:
        """Fetch historical data for a ticker via yfinance."""
        period = f"{lookback_days}d"
        t = yf.Ticker(ticker)
        hist = t.history(period=period)

        if hist.empty:
            return {"prices": [], "current": None}

        prices = hist["Close"].tolist()
        return {
            "prices": prices,
            "current": prices[-1] if prices else None,
        }

    def _compute_regime(
        self,
        vix_data: dict[str, Any],
        vix3m_data: dict[str, Any],
        spy_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Compute regime features from VIX/VIX3M/SPY data."""
        vix_prices = vix_data.get("prices", [])
        vix_current = vix_data.get("current")
        vix3m_current = vix3m_data.get("current")
        spy_prices = spy_data.get("prices", [])

        if not vix_prices or vix_current is None:
            return self._default_regime()

        vix_arr = np.array(vix_prices)

        # VIX z-score relative to its own recent history
        vix_mean = float(np.mean(vix_arr))
        vix_std = float(np.std(vix_arr))
        vix_z = (vix_current - vix_mean) / vix_std if vix_std > 0 else 0.0

        # VIX percentile in lookback window
        vix_percentile = float(np.sum(vix_arr < vix_current) / len(vix_arr) * 100)

        # VIX term structure: (VIX3M - VIX) / VIX
        # Positive = contango (normal, calm markets)
        # Negative = backwardation (panic, near-term fear exceeds long-term)
        term_structure = 0.0
        if vix3m_current and vix_current > 0:
            term_structure = (vix3m_current - vix_current) / vix_current

        # VIX rate of change (5-day)
        roc_window = min(5, len(vix_prices) - 1)
        vix_roc = (
            (vix_current - vix_prices[-1 - roc_window]) / vix_prices[-1 - roc_window]
            if roc_window > 0 and vix_prices[-1 - roc_window] > 0
            else 0.0
        )

        # Realized vol of SPY (20-day annualized) using log returns
        # to match VIX's log-normal assumption for consistent IV-RV spread
        realized_vol = None
        if len(spy_prices) >= 21:
            spy_arr = np.array(spy_prices[-21:])
            log_returns = np.log(spy_arr[1:] / spy_arr[:-1])
            realized_vol = float(np.std(log_returns, ddof=1) * np.sqrt(252) * 100)

        # Implied vs realized spread
        # VIX is annualized implied vol in %; realized_vol is also annualized %
        iv_rv_spread = None
        if realized_vol is not None:
            iv_rv_spread = vix_current - realized_vol

        # Regime classification
        if vix_current >= 30 or term_structure < -0.05:
            regime_label = "crisis"
        elif vix_current >= 20 or term_structure < 0.0:
            regime_label = "elevated"
        else:
            regime_label = "calm"

        # Regime score: continuous -1 (crisis) to +1 (calm)
        # Based on VIX level and term structure
        vix_component = np.clip(1.0 - (vix_current - 12.0) / 25.0, -1.0, 1.0)
        ts_component = np.clip(term_structure * 5.0, -1.0, 1.0)
        regime_score = float(0.6 * vix_component + 0.4 * ts_component)
        regime_score = max(-1.0, min(1.0, regime_score))

        return {
            "vix_current": round(vix_current, 2),
            "vix3m_current": round(vix3m_current, 2) if vix3m_current else None,
            "vix_mean": round(vix_mean, 2),
            "vix_z_score": round(vix_z, 4),
            "vix_percentile": round(vix_percentile, 2),
            "vix_term_structure": round(term_structure, 4),
            "vix_rate_of_change": round(vix_roc, 4),
            "realized_vol_spy": round(realized_vol, 2) if realized_vol else None,
            "iv_rv_spread": round(iv_rv_spread, 2) if iv_rv_spread else None,
            "regime_label": regime_label,
            "regime_score": round(regime_score, 4),
            "vix_series": vix_prices,
        }

    @staticmethod
    def _default_regime() -> dict[str, Any]:
        """Return neutral defaults when data is unavailable."""
        return {
            "vix_current": None,
            "vix3m_current": None,
            "vix_mean": None,
            "vix_z_score": 0.0,
            "vix_percentile": 50.0,
            "vix_term_structure": 0.0,
            "vix_rate_of_change": 0.0,
            "realized_vol_spy": None,
            "iv_rv_spread": None,
            "regime_label": "calm",
            "regime_score": 0.0,
            "vix_series": [],
        }
