"""
Factor Calculations

Calculates quantitative factor scores (0-100) for stock screening and ranking.
Used by the nightly job to populate factor scores in the database.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import stats


@dataclass
class FactorScores:
    """All factor scores for a single stock."""

    symbol: str
    momentum_score: float
    value_score: float
    quality_score: float
    dividend_score: float
    volatility_score: float
    composite_score: float

    # Sentiment-derived scores (populated when sentiment data is available)
    sentiment_score: float = 50.0  # 0-100, derived from combined_sentiment
    integrated_composite: float | None = None  # Sentiment-factor blended score

    # Component details for debugging/transparency
    momentum_6m: float | None = None
    momentum_12m: float | None = None
    ma_alignment: float | None = None
    relative_strength: float | None = None
    pe_percentile: float | None = None
    pb_percentile: float | None = None
    roe_score: float | None = None
    margin_score: float | None = None
    debt_score: float | None = None
    dividend_yield: float | None = None
    dividend_growth: float | None = None
    atr_percent: float | None = None


class FactorCalculator:
    """
    Calculates factor scores for a universe of stocks.

    All scores are normalized to 0-100 scale where:
    - 100 = Best (highest momentum, cheapest value, highest quality)
    - 0 = Worst

    Uses percentile ranking within the universe for comparability.
    """

    def __init__(self, sector_aware: bool = True):
        """
        Initialize factor calculator.

        Args:
            sector_aware: If True, calculate value/quality percentiles within sectors
        """
        self.sector_aware = sector_aware

    def calculate_all(
        self,
        market_data: dict[str, dict[str, Any]],
        sectors: dict[str, str] | None = None,
        factor_weights: dict[str, float] | None = None,
    ) -> dict[str, FactorScores]:
        """
        Calculate all factor scores for a universe of stocks.

        Args:
            market_data: Dict of symbol -> market data including:
                - price_history: List of historical prices (oldest to newest)
                - pe_ratio: Price to earnings ratio
                - pb_ratio: Price to book ratio
                - roe: Return on equity (as decimal, e.g., 0.15 for 15%)
                - profit_margin: Net profit margin (as decimal)
                - debt_to_equity: Debt to equity ratio
                - dividend_yield: Annual dividend yield (as decimal)
                - dividend_growth_5y: 5-year dividend growth rate
                - ma_30, ma_100, ma_200: Moving averages
                - atr: Average True Range
                - current_price: Current price
            sectors: Optional dict of symbol -> sector for sector-aware calculations
            factor_weights: Optional dict with keys "momentum", "value",
                "quality", "dividend", "volatility" mapping to float weights.
                If None, equal weights (0.2 each) are used.

        Returns:
            Dict of symbol -> FactorScores
        """
        results = {}
        symbols = list(market_data.keys())

        if not symbols:
            return results

        # Calculate raw values for each factor
        momentum_raw = self._calculate_momentum_raw(market_data)
        value_raw = self._calculate_value_raw(market_data, sectors)
        quality_raw = self._calculate_quality_raw(market_data, sectors)
        dividend_raw = self._calculate_dividend_raw(market_data)
        volatility_raw = self._calculate_volatility_raw(market_data)

        # Convert to percentile scores (0-100)
        momentum_scores = self._to_percentiles(momentum_raw)
        value_scores = self._to_percentiles(value_raw)
        quality_scores = self._to_percentiles(quality_raw)
        dividend_scores = self._to_percentiles(dividend_raw)
        volatility_scores = self._to_percentiles(
            volatility_raw, invert=True
        )  # Lower vol = higher score

        # Resolve factor weights for composite calculation.
        # Only use the 5 quant factor keys — ignore any extra keys
        # (e.g. "sentiment") so that the 5 factors properly sum to 1.0.
        _FACTOR_KEYS = ("momentum", "value", "quality", "dividend", "volatility")
        w_m = 0.2
        w_v = 0.2
        w_q = 0.2
        w_d = 0.2
        w_vol = 0.2
        if factor_weights:
            raw = {k: factor_weights.get(k, 0.0) for k in _FACTOR_KEYS}
            total = sum(raw.values()) or 1.0
            w_m = raw["momentum"] / total
            w_v = raw["value"] / total
            w_q = raw["quality"] / total
            w_d = raw["dividend"] / total
            w_vol = raw["volatility"] / total

        # Build results
        for symbol in symbols:
            data = market_data[symbol]

            m_score = momentum_scores.get(symbol, 50.0)
            v_score = value_scores.get(symbol, 50.0)
            q_score = quality_scores.get(symbol, 50.0)
            d_score = dividend_scores.get(symbol, 50.0)
            vol_score = volatility_scores.get(symbol, 50.0)

            # Composite: weighted by strategy-specific factor weights
            composite = (
                m_score * w_m
                + v_score * w_v
                + q_score * w_q
                + d_score * w_d
                + vol_score * w_vol
            )

            # Extract component details
            prices = data.get("price_history", [])
            current = data.get("current_price") or (prices[-1] if prices else None)

            results[symbol] = FactorScores(
                symbol=symbol,
                momentum_score=round(m_score, 2),
                value_score=round(v_score, 2),
                quality_score=round(q_score, 2),
                dividend_score=round(d_score, 2),
                volatility_score=round(vol_score, 2),
                composite_score=round(composite, 2),
                # Component details
                momentum_6m=self._safe_momentum(prices, 126),
                momentum_12m=self._safe_momentum(prices, 252),
                ma_alignment=self._calc_ma_alignment(data, current),
                relative_strength=momentum_raw.get(symbol),
                pe_percentile=self._safe_get(data, "pe_ratio"),
                pb_percentile=self._safe_get(data, "pb_ratio"),
                roe_score=self._safe_get(data, "roe"),
                margin_score=self._safe_get(data, "profit_margin"),
                debt_score=self._safe_get(data, "debt_to_equity"),
                dividend_yield=self._safe_get(data, "dividend_yield"),
                dividend_growth=self._safe_get(data, "dividend_growth_5y"),
                atr_percent=self._calc_atr_percent(data, current),
            )

        return results

    def _calculate_momentum_raw(
        self, market_data: dict[str, dict[str, Any]]
    ) -> dict[str, float]:
        """
        Calculate raw momentum scores.

        Components:
        - 6-month price momentum (40%)
        - 12-month price momentum with 1-month skip (30%)
        - MA alignment score (30%)
        """
        results = {}

        for symbol, data in market_data.items():
            prices = data.get("price_history", [])
            if len(prices) < 126:  # Need at least 6 months
                continue

            current = data.get("current_price") or prices[-1]

            # 6-month momentum
            mom_6m = self._safe_momentum(prices, 126)

            # 12-month momentum with 1-month skip (skip most recent month)
            if len(prices) >= 252:
                price_12m_ago = prices[-252]
                price_1m_ago = prices[-21] if len(prices) >= 21 else prices[-1]
                mom_12m_skip = (
                    (price_1m_ago - price_12m_ago) / price_12m_ago
                    if price_12m_ago > 0
                    else 0
                )
            else:
                mom_12m_skip = mom_6m * 0.5 if mom_6m else 0

            # MA alignment score (-1 to +1)
            ma_align = self._calc_ma_alignment(data, current)

            # Combine: 6m(40%) + 12m_skip(30%) + MA(30%)
            if mom_6m is not None:
                # Normalize MA alignment from [-1,1] to [0,1] scale
                ma_normalized = (ma_align + 1) / 2 if ma_align is not None else 0.5

                raw_score = (
                    0.4 * (mom_6m * 100)  # Convert to percentage
                    + 0.3 * (mom_12m_skip * 100)
                    + 0.3 * (ma_normalized * 100)
                )
                results[symbol] = raw_score

        return results

    def _calculate_value_raw(
        self,
        market_data: dict[str, dict[str, Any]],
        sectors: dict[str, str] | None = None,
    ) -> dict[str, float]:
        """
        Calculate raw value scores.

        Components:
        - P/E ratio (inverted - lower is better) (50%)
        - P/B ratio (inverted - lower is better) (50%)

        Calculated within sectors if sector_aware=True.
        """
        results = {}

        # Group by sector if sector-aware
        if self.sector_aware and sectors:
            sector_groups: dict[str, list[str]] = {}
            for symbol in market_data:
                sector = sectors.get(symbol, "Unknown")
                if sector not in sector_groups:
                    sector_groups[sector] = []
                sector_groups[sector].append(symbol)

            # Calculate within each sector
            for sector, symbols in sector_groups.items():
                sector_results = self._calc_value_for_group(
                    {s: market_data[s] for s in symbols}
                )
                results.update(sector_results)
        else:
            results = self._calc_value_for_group(market_data)

        return results

    def _calc_value_for_group(
        self, group_data: dict[str, dict[str, Any]]
    ) -> dict[str, float]:
        """Calculate value scores for a group of stocks."""
        results = {}

        # Collect P/E and P/B values
        pe_values = {}
        pb_values = {}

        for symbol, data in group_data.items():
            pe = data.get("pe_ratio")
            pb = data.get("pb_ratio")

            # Filter out negative or extreme values
            if pe and 0 < pe < 200:
                pe_values[symbol] = pe
            if pb and 0 < pb < 50:
                pb_values[symbol] = pb

        # Calculate percentiles (inverted - lower ratio = higher score)
        pe_percentiles = self._to_percentiles(pe_values, invert=True)
        pb_percentiles = self._to_percentiles(pb_values, invert=True)

        # Combine scores
        for symbol in group_data:
            pe_score = pe_percentiles.get(symbol, 50)
            pb_score = pb_percentiles.get(symbol, 50)
            results[symbol] = 0.5 * pe_score + 0.5 * pb_score

        return results

    def _calculate_quality_raw(
        self,
        market_data: dict[str, dict[str, Any]],
        sectors: dict[str, str] | None = None,
    ) -> dict[str, float]:
        """
        Calculate raw quality scores.

        Components:
        - ROE (higher is better) (40%)
        - Profit margin (higher is better) (30%)
        - Debt/equity (lower is better) (30%)
        """
        results = {}

        # Collect quality metrics
        roe_values = {}
        margin_values = {}
        debt_values = {}

        for symbol, data in market_data.items():
            roe = data.get("roe")
            margin = data.get("profit_margin")
            debt = data.get("debt_to_equity")

            if roe is not None and -0.5 < roe < 1.0:  # Filter extremes
                roe_values[symbol] = roe
            if margin is not None and -0.5 < margin < 1.0:
                margin_values[symbol] = margin
            if debt is not None and 0 <= debt < 10:
                debt_values[symbol] = debt

        # Calculate percentiles
        roe_percentiles = self._to_percentiles(roe_values)
        margin_percentiles = self._to_percentiles(margin_values)
        debt_percentiles = self._to_percentiles(
            debt_values, invert=True
        )  # Lower debt is better

        # Combine scores
        for symbol in market_data:
            roe_score = roe_percentiles.get(symbol, 50)
            margin_score = margin_percentiles.get(symbol, 50)
            debt_score = debt_percentiles.get(symbol, 50)

            results[symbol] = 0.4 * roe_score + 0.3 * margin_score + 0.3 * debt_score

        return results

    def _calculate_dividend_raw(
        self, market_data: dict[str, dict[str, Any]]
    ) -> dict[str, float]:
        """
        Calculate raw dividend scores.

        Components:
        - Dividend yield (60%)
        - 5-year dividend growth (40%)

        Non-dividend payers get score of 0.
        """
        results = {}

        yield_values = {}
        growth_values = {}

        for symbol, data in market_data.items():
            div_yield = data.get("dividend_yield")
            div_growth = data.get("dividend_growth_5y")

            if div_yield is not None and div_yield > 0:
                yield_values[symbol] = div_yield
            if div_growth is not None:
                growth_values[symbol] = div_growth

        # Calculate percentiles
        yield_percentiles = self._to_percentiles(yield_values)
        growth_percentiles = self._to_percentiles(growth_values)

        # Combine scores (non-dividend payers get 0)
        for symbol in market_data:
            div_yield = market_data[symbol].get("dividend_yield", 0)

            if div_yield and div_yield > 0:
                yield_score = yield_percentiles.get(symbol, 50)
                growth_score = growth_percentiles.get(symbol, 50)
                results[symbol] = 0.6 * yield_score + 0.4 * growth_score
            else:
                results[symbol] = 0  # Non-dividend payers

        return results

    def _calculate_volatility_raw(
        self, market_data: dict[str, dict[str, Any]]
    ) -> dict[str, float]:
        """
        Calculate raw volatility scores.

        Uses ATR as percentage of price.
        Lower volatility = higher score (inverted in percentile calculation).
        """
        results = {}

        for symbol, data in market_data.items():
            current = data.get("current_price")
            atr = data.get("atr")

            if current and atr and current > 0:
                atr_percent = (atr / current) * 100
                results[symbol] = atr_percent
            elif prices := data.get("price_history"):
                # Calculate from price history if ATR not available
                if len(prices) >= 20:
                    returns = np.diff(prices[-20:]) / prices[-21:-1]
                    vol = np.std(returns) * np.sqrt(252) * 100  # Annualized vol %
                    results[symbol] = vol

        return results

    def _to_percentiles(
        self, values: dict[str, float], invert: bool = False
    ) -> dict[str, float]:
        """
        Convert raw values to percentile scores (0-100).

        Args:
            values: Dict of symbol -> raw value
            invert: If True, lower values get higher scores

        Returns:
            Dict of symbol -> percentile score (0-100)
        """
        if not values:
            return {}

        symbols = list(values.keys())
        raw_values = [values[s] for s in symbols]

        # Calculate percentile ranks
        ranks = stats.rankdata(raw_values, method="average")
        percentiles = (
            (ranks - 1) / (len(ranks) - 1) * 100
            if len(ranks) > 1
            else [50.0] * len(ranks)
        )

        if invert:
            percentiles = [100 - p for p in percentiles]

        return dict(zip(symbols, percentiles))

    def _safe_momentum(self, prices: list, days: int) -> float | None:
        """Calculate momentum safely."""
        if not prices or len(prices) < days:
            return None

        old_price = prices[-days]
        new_price = prices[-1]

        if old_price > 0:
            return (new_price - old_price) / old_price
        return None

    def _calc_ma_alignment(
        self, data: dict[str, Any], current_price: float | None
    ) -> float | None:
        """
        Calculate MA alignment score (-1 to +1).

        +1 = Perfect uptrend (price > MA30 > MA100 > MA200)
        -1 = Perfect downtrend
        0 = Mixed/neutral
        """
        if not current_price:
            return None

        ma_30 = data.get("ma_30")
        ma_100 = data.get("ma_100")
        ma_200 = data.get("ma_200")

        if not all([ma_30, ma_100, ma_200]):
            return None

        score = 0

        # Check alignment
        if current_price > ma_30:
            score += 0.25
        else:
            score -= 0.25

        if ma_30 > ma_100:
            score += 0.25
        else:
            score -= 0.25

        if ma_100 > ma_200:
            score += 0.25
        else:
            score -= 0.25

        if current_price > ma_200:
            score += 0.25
        else:
            score -= 0.25

        return score

    def _calc_atr_percent(
        self, data: dict[str, Any], current_price: float | None
    ) -> float | None:
        """Calculate ATR as percentage of price."""
        if not current_price or current_price <= 0:
            return None

        atr = data.get("atr")
        if atr:
            return (atr / current_price) * 100
        return None

    def _safe_get(self, data: dict, key: str) -> float | None:
        """Safely get a value from dict."""
        val = data.get(key)
        if val is not None and not np.isnan(val) and not np.isinf(val):
            return float(val)
        return None


def calculate_atr(
    high_prices: list[float],
    low_prices: list[float],
    close_prices: list[float],
    period: int = 14,
) -> float | None:
    """
    Calculate Average True Range (ATR) for position sizing.

    ATR measures volatility by decomposing the entire range of an asset
    price for that period.

    Args:
        high_prices: List of high prices (oldest to newest)
        low_prices: List of low prices
        close_prices: List of close prices
        period: ATR lookback period (default 14)

    Returns:
        ATR value or None if insufficient data
    """
    if len(high_prices) < period + 1:
        return None

    tr_values = []

    for i in range(1, len(high_prices)):
        high = high_prices[i]
        low = low_prices[i]
        prev_close = close_prices[i - 1]

        # True Range is max of:
        # - Current High - Current Low
        # - |Current High - Previous Close|
        # - |Current Low - Previous Close|
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_values.append(tr)

    if len(tr_values) < period:
        return None

    # Use simple moving average for initial ATR
    return sum(tr_values[-period:]) / period


def calculate_position_size(
    capital: float,
    risk_per_trade: float,
    entry_price: float,
    stop_price: float,
    atr: float | None = None,
    atr_multiplier: float = 2.0,
    max_position_pct: float = 0.10,
) -> dict[str, Any]:
    """
    Calculate position size based on risk parameters.

    Uses ATR-based or fixed stop loss for position sizing.

    Args:
        capital: Total portfolio capital
        risk_per_trade: Risk per trade as decimal (e.g., 0.01 for 1%)
        entry_price: Entry price for the position
        stop_price: Fixed stop loss price (used if ATR not provided)
        atr: Average True Range (optional, for ATR-based sizing)
        atr_multiplier: ATR multiplier for stop distance (default 2x ATR)
        max_position_pct: Maximum position size as % of capital (default 10%)

    Returns:
        Dict with:
        - shares: Number of shares to buy
        - position_value: Total position value
        - position_pct: Position as % of capital
        - stop_price: Calculated stop price
        - risk_amount: Dollar risk on the trade
    """
    risk_amount = capital * risk_per_trade

    # Calculate stop distance
    if atr:
        stop_distance = atr * atr_multiplier
        calculated_stop = entry_price - stop_distance
    else:
        stop_distance = entry_price - stop_price
        calculated_stop = stop_price

    if stop_distance <= 0:
        return {
            "shares": 0,
            "position_value": 0,
            "position_pct": 0,
            "stop_price": calculated_stop,
            "risk_amount": 0,
            "error": "Invalid stop distance",
        }

    # Calculate shares based on risk
    shares_from_risk = int(risk_amount / stop_distance)

    # Check against max position size
    max_position_value = capital * max_position_pct
    max_shares = int(max_position_value / entry_price)

    # Use the smaller of the two
    shares = min(shares_from_risk, max_shares)

    if shares <= 0:
        return {
            "shares": 0,
            "position_value": 0,
            "position_pct": 0,
            "stop_price": calculated_stop,
            "risk_amount": 0,
            "error": "Position size too small",
        }

    position_value = shares * entry_price
    position_pct = position_value / capital
    actual_risk = shares * stop_distance

    return {
        "shares": shares,
        "position_value": round(position_value, 2),
        "position_pct": round(position_pct * 100, 2),
        "stop_price": round(calculated_stop, 2),
        "risk_amount": round(actual_risk, 2),
    }
