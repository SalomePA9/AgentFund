"""
Combined Sentiment Orchestrator

Coordinates sentiment analysis from all sources and calculates
combined scores with velocity tracking.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from config import get_settings
from data.sentiment.base import CombinedSentimentCalculator
from data.sentiment.models import SentimentHistoryRecord, SentimentScore
from data.sentiment.news import NewsSentimentAnalyzer
from data.sentiment.social import SocialSentimentAnalyzer

logger = logging.getLogger(__name__)


class SentimentOrchestrator:
    """
    Orchestrates sentiment analysis from all sources.

    Coordinates:
    - News sentiment (Google News + FinBERT)
    - Social sentiment (StockTwits + Alpha Vantage)
    - Combined scoring with configurable weights
    - Velocity tracking from historical data

    Default weights (configurable):
    - News: 40%
    - Social: 30%
    - Velocity: 30%
    """

    def __init__(
        self,
        news_weight: float | None = None,
        social_weight: float | None = None,
        velocity_weight: float | None = None,
        db_client: Any = None,
    ):
        """
        Initialize sentiment orchestrator.

        Args:
            news_weight: Weight for news sentiment (default from config)
            social_weight: Weight for social sentiment (default from config)
            velocity_weight: Weight for velocity (default from config)
            db_client: Supabase client for historical data
        """
        settings = get_settings()

        # Get weights from config or use provided values
        self.news_weight = news_weight or settings.sentiment_news_weight
        self.social_weight = social_weight or settings.sentiment_social_weight
        self.velocity_weight = velocity_weight or settings.sentiment_velocity_weight

        # Normalize weights to sum to 1.0
        total = self.news_weight + self.social_weight + self.velocity_weight
        self.news_weight /= total
        self.social_weight /= total
        self.velocity_weight /= total

        # Initialize analyzers
        self._news_analyzer = NewsSentimentAnalyzer(
            cache_ttl_minutes=settings.sentiment_cache_ttl_minutes,
        )
        self._social_analyzer = SocialSentimentAnalyzer(
            cache_ttl_minutes=settings.sentiment_cache_ttl_minutes,
        )
        self._combiner = CombinedSentimentCalculator(
            news_weight=self.news_weight,
            social_weight=self.social_weight,
            velocity_weight=self.velocity_weight,
        )

        # Database client for historical data
        self._db = db_client

    async def analyze_symbol(
        self,
        symbol: str,
        historical_records: list[SentimentHistoryRecord] | None = None,
    ) -> SentimentScore:
        """
        Analyze sentiment for a single symbol from all sources.

        Args:
            symbol: Stock ticker symbol
            historical_records: Optional pre-fetched historical data

        Returns:
            SentimentScore with combined metrics
        """
        symbol = symbol.upper()

        # Fetch sentiment from all sources concurrently
        news_task = self._news_analyzer.analyze_symbol(symbol)
        social_task = self._social_analyzer.analyze_symbol(symbol)

        news_result, social_result = await asyncio.gather(
            news_task, social_task, return_exceptions=True
        )

        # Handle exceptions
        if isinstance(news_result, Exception):
            logger.warning(f"News sentiment error for {symbol}: {news_result}")
            news_result = None
        if isinstance(social_result, Exception):
            logger.warning(f"Social sentiment error for {symbol}: {social_result}")
            social_result = None

        # Fetch historical data if not provided and db available
        if historical_records is None and self._db:
            historical_records = await self._fetch_historical(symbol)

        # Combine all sources
        combined = self._combiner.calculate_combined(
            news_result=news_result,
            social_result=social_result,
            historical_scores=historical_records,
        )

        return combined

    async def analyze_batch(
        self,
        symbols: list[str],
        fetch_historical: bool = True,
    ) -> dict[str, SentimentScore]:
        """
        Analyze sentiment for multiple symbols.

        Args:
            symbols: List of stock ticker symbols
            fetch_historical: Whether to fetch historical data for velocity

        Returns:
            Dictionary mapping symbols to SentimentScores
        """
        results = {}
        settings = get_settings()

        # Fetch historical data for all symbols if needed
        historical_map = {}
        if fetch_historical and self._db:
            historical_map = await self._fetch_historical_batch(symbols)

        # Process in batches
        batch_size = settings.sentiment_batch_size
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]

            # Process batch concurrently
            tasks = [
                self.analyze_symbol(s, historical_map.get(s.upper())) for s in batch
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for symbol, result in zip(batch, batch_results):
                symbol = symbol.upper()
                if isinstance(result, Exception):
                    logger.error(f"Error analyzing {symbol}: {result}")
                    results[symbol] = SentimentScore(
                        symbol=symbol,
                        combined_sentiment=None,
                        last_updated=datetime.utcnow(),
                    )
                else:
                    results[symbol] = result

            # Rate limiting between batches
            if i + batch_size < len(symbols):
                await asyncio.sleep(settings.sentiment_rate_limit_delay)

            # Progress logging
            progress = min(i + batch_size, len(symbols))
            logger.info(f"Sentiment analysis progress: {progress}/{len(symbols)}")

        return results

    async def _fetch_historical(
        self,
        symbol: str,
        days: int = 7,
    ) -> list[SentimentHistoryRecord]:
        """Fetch historical sentiment records for a symbol."""
        if not self._db:
            return []

        try:
            cutoff = datetime.utcnow() - timedelta(days=days)

            result = (
                self._db.table("sentiment_history")
                .select("*")
                .eq("symbol", symbol.upper())
                .gte("recorded_at", cutoff.isoformat())
                .order("recorded_at", desc=True)
                .execute()
            )

            records = []
            for row in result.data:
                records.append(
                    SentimentHistoryRecord(
                        symbol=row["symbol"],
                        recorded_at=datetime.fromisoformat(
                            row["recorded_at"].replace("Z", "+00:00")
                        ),
                        news_sentiment=row.get("news_sentiment"),
                        social_sentiment=row.get("social_sentiment"),
                        combined_sentiment=row.get("combined_sentiment"),
                        news_sample_size=row.get("news_sample_size", 0),
                        social_sample_size=row.get("social_sample_size", 0),
                    )
                )

            return records

        except Exception as e:
            logger.warning(f"Error fetching historical sentiment for {symbol}: {e}")
            return []

    async def _fetch_historical_batch(
        self,
        symbols: list[str],
        days: int = 7,
    ) -> dict[str, list[SentimentHistoryRecord]]:
        """Fetch historical sentiment records for multiple symbols."""
        if not self._db:
            return {}

        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            symbols_upper = [s.upper() for s in symbols]

            result = (
                self._db.table("sentiment_history")
                .select("*")
                .in_("symbol", symbols_upper)
                .gte("recorded_at", cutoff.isoformat())
                .order("recorded_at", desc=True)
                .execute()
            )

            # Group by symbol
            historical_map: dict[str, list[SentimentHistoryRecord]] = {
                s: [] for s in symbols_upper
            }

            for row in result.data:
                symbol = row["symbol"]
                if symbol in historical_map:
                    historical_map[symbol].append(
                        SentimentHistoryRecord(
                            symbol=symbol,
                            recorded_at=datetime.fromisoformat(
                                row["recorded_at"].replace("Z", "+00:00")
                            ),
                            news_sentiment=row.get("news_sentiment"),
                            social_sentiment=row.get("social_sentiment"),
                            combined_sentiment=row.get("combined_sentiment"),
                            news_sample_size=row.get("news_sample_size", 0),
                            social_sample_size=row.get("social_sample_size", 0),
                        )
                    )

            return historical_map

        except Exception as e:
            logger.warning(f"Error fetching historical sentiment batch: {e}")
            return {}

    async def save_to_database(
        self,
        scores: dict[str, SentimentScore],
    ) -> tuple[int, int]:
        """
        Save sentiment scores to database.

        Updates stocks table and creates sentiment_history records.

        Args:
            scores: Dictionary mapping symbols to SentimentScores

        Returns:
            Tuple of (success_count, failure_count)
        """
        if not self._db:
            logger.warning("No database client - cannot save sentiment scores")
            return 0, len(scores)

        success = 0
        failures = 0

        for symbol, score in scores.items():
            try:
                # Update stocks table with current sentiment
                self._db.table("stocks").update(
                    {
                        "news_sentiment": score.news_sentiment,
                        "social_sentiment": score.social_sentiment,
                        "combined_sentiment": score.combined_sentiment,
                        "sentiment_velocity": score.velocity,
                    }
                ).eq("symbol", symbol).execute()

                # Create history record
                history_record = self._combiner.create_history_record(score)
                self._db.table("sentiment_history").insert(
                    history_record.to_db_row()
                ).execute()

                success += 1

            except Exception as e:
                logger.error(f"Error saving sentiment for {symbol}: {e}")
                failures += 1

        logger.info(f"Saved sentiment: {success} success, {failures} failures")
        return success, failures

    def clear_cache(self):
        """Clear all analyzer caches."""
        self._news_analyzer.clear_cache()
        self._social_analyzer.clear_cache()

    async def close(self):
        """Close all HTTP clients."""
        await self._social_analyzer.close()


def calculate_velocity(
    historical: list[SentimentHistoryRecord],
    days: int = 7,
) -> float | None:
    """
    Calculate sentiment velocity (rate of change) from historical data.

    Args:
        historical: List of historical sentiment records
        days: Number of days to consider

    Returns:
        Daily change in sentiment, or None if insufficient data
    """
    if not historical or len(historical) < 2:
        return None

    # Sort by date, most recent first
    sorted_records = sorted(
        historical,
        key=lambda r: r.recorded_at,
        reverse=True,
    )

    # Filter to last N days
    cutoff = datetime.utcnow() - timedelta(days=days)
    recent = [r for r in sorted_records if r.recorded_at >= cutoff]

    if len(recent) < 2:
        return None

    # Get oldest and newest combined sentiments
    newest = recent[0]
    oldest = recent[-1]

    if newest.combined_sentiment is None or oldest.combined_sentiment is None:
        return None

    # Calculate daily change
    days_elapsed = (newest.recorded_at - oldest.recorded_at).days
    if days_elapsed == 0:
        days_elapsed = 1

    velocity = (newest.combined_sentiment - oldest.combined_sentiment) / days_elapsed
    return velocity


def interpret_velocity(velocity: float | None) -> dict[str, Any]:
    """
    Interpret sentiment velocity into actionable insights.

    Args:
        velocity: Daily change in sentiment

    Returns:
        Dictionary with interpretation
    """
    if velocity is None:
        return {
            "direction": "unknown",
            "strength": "unknown",
            "signal": "neutral",
            "description": "Insufficient historical data",
        }

    # Determine direction
    if velocity > 2:
        direction = "improving"
        signal = "bullish"
    elif velocity > 0.5:
        direction = "slightly_improving"
        signal = "slightly_bullish"
    elif velocity < -2:
        direction = "declining"
        signal = "bearish"
    elif velocity < -0.5:
        direction = "slightly_declining"
        signal = "slightly_bearish"
    else:
        direction = "stable"
        signal = "neutral"

    # Determine strength
    abs_velocity = abs(velocity)
    if abs_velocity > 5:
        strength = "strong"
    elif abs_velocity > 2:
        strength = "moderate"
    elif abs_velocity > 0.5:
        strength = "weak"
    else:
        strength = "minimal"

    return {
        "direction": direction,
        "strength": strength,
        "signal": signal,
        "daily_change": round(velocity, 2),
        "description": f"Sentiment {direction} at {abs_velocity:.1f} points/day",
    }


# Convenience function for direct use
async def analyze_all_sentiment(
    symbols: list[str],
    db_client: Any = None,
    save_to_db: bool = False,
) -> dict[str, SentimentScore]:
    """
    Analyze sentiment for multiple symbols from all sources.

    Args:
        symbols: List of stock ticker symbols
        db_client: Optional Supabase client for historical data and saving
        save_to_db: Whether to save results to database

    Returns:
        Dictionary mapping symbols to SentimentScores
    """
    orchestrator = SentimentOrchestrator(db_client=db_client)

    try:
        results = await orchestrator.analyze_batch(symbols)

        if save_to_db and db_client:
            await orchestrator.save_to_database(results)

        return results

    finally:
        await orchestrator.close()
