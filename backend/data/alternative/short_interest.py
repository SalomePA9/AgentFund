"""
Short Interest Data

Fetches short interest and its rate of change as an institutional positioning
signal.  Short interest reflects hedge fund and institutional views, making it
structurally uncorrelated to the existing sentiment pipeline (which captures
retail/news sentiment via StockTwits and FinBERT).

Key insight: Rising short interest indicates institutional bears are
building positions, even if retail sentiment is neutral or positive.
Falling short interest = institutional covering = bullish.

Data sources:
- Yahoo Finance shortPercentOfFloat (free via yfinance info)
- Approximate short interest ratio from volume patterns

Signals produced:
- short_pct_float: Current short interest as % of float
- short_interest_score: Normalised -100 to +100 (high short = bearish)
- short_interest_roc: Rate of change in short interest (when historical data available)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)


class ShortInterestClient:
    """
    Fetches short interest data for equities.

    Uses yfinance to get shortPercentOfFloat and sharesShort from
    Yahoo Finance's stock info endpoint.

    Usage::

        client = ShortInterestClient()
        data = await client.fetch_short_interest(["AAPL", "TSLA", "GME"])
        # data["TSLA"] = {
        #     "short_pct_float": 3.2,
        #     "shares_short": 25000000,
        #     "short_ratio": 1.5,
        #     "short_interest_score": -15.0,  # -100 to +100
        # }
    """

    async def fetch_short_interest(
        self,
        symbols: list[str],
        batch_size: int = 20,
    ) -> dict[str, dict[str, Any]]:
        """
        Fetch short interest metrics for a list of symbols.

        Processes in batches to avoid overwhelming the yfinance API.
        """
        results: dict[str, dict[str, Any]] = {}

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]
            batch_results = await asyncio.gather(
                *[self._fetch_single(sym) for sym in batch],
                return_exceptions=True,
            )

            for sym, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    continue
                if result:
                    results[sym] = result

            # Rate limit between batches
            if i + batch_size < len(symbols):
                await asyncio.sleep(1.0)

        logger.info(
            "Short interest: fetched data for %d/%d symbols",
            len(results),
            len(symbols),
        )
        return results

    async def _fetch_single(self, symbol: str) -> dict[str, Any] | None:
        """Fetch short interest for a single symbol."""
        try:
            info = await asyncio.to_thread(self._get_info, symbol)
            if not info:
                return None

            short_pct = info.get("shortPercentOfFloat")
            shares_short = info.get("sharesShort")
            short_ratio = info.get("shortRatio")  # Days to cover
            float_shares = info.get("floatShares")

            if short_pct is None and shares_short is None:
                return None

            # yfinance returns shortPercentOfFloat as a decimal fraction
            # (e.g. 0.03 = 3%). Always convert to percentage.
            if short_pct is not None and float_shares:
                # Validate against shares_short / float_shares if available
                if shares_short and float_shares > 0:
                    computed_pct = (shares_short / float_shares) * 100
                    # If short_pct looks like a decimal fraction (typical yfinance)
                    # and computed_pct is in a similar range, trust computed
                    if abs(computed_pct - short_pct * 100) < abs(
                        computed_pct - short_pct
                    ):
                        short_pct = short_pct * 100
                    # else: short_pct already in percentage form
                else:
                    # No float_shares to validate — yfinance consistently
                    # returns decimal fractions, so multiply
                    short_pct = short_pct * 100

            # Compute short interest score (-100 to +100)
            # High short interest = bearish signal (negative score)
            # Low short interest = neutral/slightly bullish
            # Based on empirical distribution:
            #   <2% = normal → score near 0
            #   2-5% = elevated → score -20 to -40
            #   5-10% = high → score -40 to -70
            #   >10% = extreme → score -70 to -100
            score = 0.0
            if short_pct is not None:
                if short_pct < 2.0:
                    score = 0.0
                elif short_pct < 5.0:
                    score = -(short_pct - 2.0) / 3.0 * 40  # -0 to -40
                elif short_pct < 10.0:
                    score = -40 - (short_pct - 5.0) / 5.0 * 30  # -40 to -70
                else:
                    score = -70 - min(
                        30.0, (short_pct - 10.0) / 10.0 * 30
                    )  # -70 to -100
                score = max(-100.0, min(0.0, score))

            return {
                "short_pct_float": round(short_pct, 2) if short_pct is not None else None,
                "shares_short": shares_short,
                "short_ratio": round(short_ratio, 2) if short_ratio is not None else None,
                "float_shares": float_shares,
                "short_interest_score": round(score, 2),
            }

        except Exception:
            logger.debug("Failed to fetch short interest for %s", symbol, exc_info=True)
            return None

    @staticmethod
    def _get_info(symbol: str) -> dict[str, Any]:
        """Fetch stock info via yfinance (blocking call)."""
        try:
            return yf.Ticker(symbol).info
        except Exception:
            return {}


def compute_short_interest_roc(
    current_si: dict[str, dict[str, Any]],
    previous_si: dict[str, dict[str, Any]],
) -> dict[str, float]:
    """
    Compute rate of change in short interest between two snapshots.

    Returns a dict of symbol → RoC score where:
    - Positive = short interest increasing (bearish)
    - Negative = short interest decreasing (bullish / covering)
    - Normalised to -100 to +100

    This should be called with current and previous bi-weekly SI snapshots.
    """
    roc_scores: dict[str, float] = {}

    for symbol in current_si:
        cur = current_si[symbol].get("short_pct_float")
        prev_data = previous_si.get(symbol)
        prev = prev_data.get("short_pct_float") if prev_data else None

        if cur is None or prev is None or prev == 0:
            continue

        # Rate of change as percentage
        change_pct = (cur - prev) / prev * 100

        # Normalise: ±50% change maps to ±100 score
        score = max(-100.0, min(100.0, change_pct * 2.0))

        roc_scores[symbol] = round(score, 2)

    return roc_scores
