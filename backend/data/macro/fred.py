"""
FRED (Federal Reserve Economic Data) Client

Fetches macroeconomic indicators from the FRED API that are structurally
uncorrelated to equity price momentum and retail sentiment:

1. Credit Spreads — ICE BofA High Yield OAS (BAMLH0A0HYM2)
   - Measures risk appetite in credit markets
   - Leads equity drawdowns by days/weeks
   - Free via FRED API

2. Yield Curve — 10Y-2Y Treasury Spread (T10Y2Y)
   - Macro regime indicator
   - Inversions predict recessions 6-18 months ahead
   - Uncorrelated to momentum/value on short horizons

3. Rate of Change — 2Y Treasury Yield (DGS2)
   - Captures rate shock risk
   - Rising rates compress equity multiples

Data source: https://fred.stlouisfed.org/
API docs: https://fred.stlouisfed.org/docs/api/fred/
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import httpx
import numpy as np

logger = logging.getLogger(__name__)

# FRED series IDs
CREDIT_SPREAD_SERIES = "BAMLH0A0HYM2"  # ICE BofA US High Yield OAS
YIELD_CURVE_SERIES = "T10Y2Y"  # 10-Year minus 2-Year Treasury
TREASURY_2Y_SERIES = "DGS2"  # 2-Year Treasury Constant Maturity
TREASURY_10Y_SERIES = "DGS10"  # 10-Year Treasury Constant Maturity

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


class FredClient:
    """
    Fetches macroeconomic time series from FRED.

    Usage::

        client = FredClient(api_key="your_key")
        data = await client.fetch_all(lookback_days=90)
        # data = {
        #     "credit_spread": {"current": 3.82, "series": [...], ...},
        #     "yield_curve": {"current": 0.45, "series": [...], ...},
        #     "treasury_2y": {"current": 4.21, "series": [...], ...},
        # }

    If no API key is provided, returns empty data gracefully.
    FRED API key is free: https://fred.stlouisfed.org/docs/api/api_key.html
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    async def fetch_all(self, lookback_days: int = 90) -> dict[str, dict[str, Any]]:
        """Fetch all macro series and return processed data."""
        if not self.api_key:
            logger.warning("No FRED API key configured — skipping macro data")
            return {}

        results = {}

        series_map = {
            "credit_spread": CREDIT_SPREAD_SERIES,
            "yield_curve": YIELD_CURVE_SERIES,
            "treasury_2y": TREASURY_2Y_SERIES,
            "treasury_10y": TREASURY_10Y_SERIES,
        }

        for name, series_id in series_map.items():
            try:
                raw = await self._fetch_series(series_id, lookback_days)
                if raw:
                    results[name] = self._process_series(raw, name)
            except Exception:
                logger.warning(
                    "Failed to fetch FRED series %s", series_id, exc_info=True
                )

        return results

    async def _fetch_series(
        self, series_id: str, lookback_days: int
    ) -> list[dict[str, str]]:
        """Fetch a single FRED series."""
        start_date = (datetime.utcnow() - timedelta(days=lookback_days)).strftime(
            "%Y-%m-%d"
        )

        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start_date,
            "sort_order": "asc",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(FRED_BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("observations", [])

    @staticmethod
    def _process_series(
        observations: list[dict[str, str]], name: str
    ) -> dict[str, Any]:
        """
        Process raw FRED observations into a structured dict with:
        - current: latest value
        - series: list of floats
        - dates: list of date strings
        - z_score: current value relative to series mean/std
        - rate_of_change: recent change (5-day)
        - percentile: current value's percentile in the lookback window
        """
        values = []
        dates = []
        for obs in observations:
            try:
                val = float(obs["value"])
                values.append(val)
                dates.append(obs["date"])
            except (ValueError, KeyError):
                continue  # FRED uses "." for missing values

        if not values:
            return {"current": None, "series": [], "dates": []}

        current = values[-1]
        arr = np.array(values)
        mean = float(np.mean(arr))
        std = float(np.std(arr))

        z_score = (current - mean) / std if std > 0 else 0.0

        # Rate of change (5-observation)
        roc_window = min(5, len(values) - 1)
        roc = (current - values[-1 - roc_window]) if roc_window > 0 else 0.0

        # Percentile rank in the lookback window
        percentile = float(np.sum(arr < current) / len(arr) * 100)

        return {
            "current": current,
            "mean": round(mean, 4),
            "std": round(std, 4),
            "z_score": round(z_score, 4),
            "rate_of_change": round(roc, 4),
            "percentile": round(percentile, 2),
            "series": values,
            "dates": dates,
            "name": name,
        }
