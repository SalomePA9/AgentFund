"""
Sentiment Analyzer Base Class

Abstract base class for all sentiment analyzers.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any

from data.sentiment.models import (
    SentimentHistoryRecord,
    SentimentResult,
    SentimentScore,
    SentimentSource,
)

logger = logging.getLogger(__name__)


class SentimentAnalyzer(ABC):
    """
    Abstract base class for sentiment analyzers.

    Subclasses implement specific data source fetching and analysis:
    - NewsSentimentAnalyzer: News headlines via RSS
    - SocialSentimentAnalyzer: StockTwits, Reddit

    All analyzers normalize scores to -100 (bearish) to +100 (bullish).
    """

    def __init__(
        self,
        source: SentimentSource,
        cache_ttl_minutes: int = 30,
        batch_size: int = 10,
        rate_limit_delay: float = 0.5,
    ):
        """
        Initialize sentiment analyzer.

        Args:
            source: The data source this analyzer handles
            cache_ttl_minutes: How long to cache results
            batch_size: Number of symbols to process in parallel
            rate_limit_delay: Delay between API calls in seconds
        """
        self.source = source
        self.cache_ttl_minutes = cache_ttl_minutes
        self.batch_size = batch_size
        self.rate_limit_delay = rate_limit_delay

        # Simple in-memory cache: {symbol: (result, timestamp)}
        self._cache: dict[str, tuple[SentimentResult, datetime]] = {}

    @abstractmethod
    async def fetch_data(self, symbol: str) -> list[Any]:
        """
        Fetch raw data for a symbol from the source.

        Args:
            symbol: Stock ticker symbol

        Returns:
            List of raw data items (articles, posts, etc.)
        """
        pass

    @abstractmethod
    async def analyze_item(self, item: Any, symbol: str) -> float | None:
        """
        Analyze a single item and return sentiment score.

        Args:
            item: Raw data item (article, post)
            symbol: Stock ticker symbol

        Returns:
            Sentiment score (-100 to +100) or None if analysis fails
        """
        pass

    @abstractmethod
    def calculate_confidence(self, scores: list[float], sample_size: int) -> float:
        """
        Calculate confidence level for the aggregated score.

        Args:
            scores: List of individual sentiment scores
            sample_size: Number of items analyzed

        Returns:
            Confidence score (0.0 to 1.0)
        """
        pass

    async def analyze_symbol(
        self, symbol: str, use_cache: bool = True
    ) -> SentimentResult:
        """
        Analyze sentiment for a single symbol.

        Args:
            symbol: Stock ticker symbol
            use_cache: Whether to use cached results

        Returns:
            SentimentResult with aggregated score
        """
        symbol = symbol.upper()

        # Check cache
        if use_cache and symbol in self._cache:
            cached_result, cached_time = self._cache[symbol]
            if datetime.utcnow() - cached_time < timedelta(
                minutes=self.cache_ttl_minutes
            ):
                logger.debug(
                    f"Cache hit for {symbol} sentiment from {self.source.value}"
                )
                return cached_result

        try:
            # Fetch raw data
            items = await self.fetch_data(symbol)

            if not items:
                logger.debug(f"No {self.source.value} data found for {symbol}")
                return SentimentResult(
                    symbol=symbol,
                    source=self.source,
                    score=0.0,  # Neutral when no data
                    confidence=0.0,
                    sample_size=0,
                    metadata={"reason": "no_data"},
                )

            # Analyze each item
            scores = []
            for item in items:
                try:
                    score = await self.analyze_item(item, symbol)
                    if score is not None:
                        scores.append(score)
                except Exception as e:
                    logger.warning(f"Error analyzing item for {symbol}: {e}")
                    continue

            if not scores:
                return SentimentResult(
                    symbol=symbol,
                    source=self.source,
                    score=0.0,
                    confidence=0.0,
                    sample_size=len(items),
                    metadata={"reason": "analysis_failed"},
                )

            # Aggregate scores
            aggregated_score = self._aggregate_scores(scores)
            confidence = self.calculate_confidence(scores, len(items))

            result = SentimentResult(
                symbol=symbol,
                source=self.source,
                score=aggregated_score,
                confidence=confidence,
                sample_size=len(scores),
                metadata={
                    "items_fetched": len(items),
                    "items_analyzed": len(scores),
                    "score_std": self._calculate_std(scores),
                },
            )

            # Update cache
            self._cache[symbol] = (result, datetime.utcnow())

            return result

        except Exception as e:
            logger.error(
                f"Error analyzing {symbol} sentiment from {self.source.value}: {e}"
            )
            return SentimentResult(
                symbol=symbol,
                source=self.source,
                score=0.0,
                confidence=0.0,
                sample_size=0,
                metadata={"error": str(e)},
            )

    async def analyze_batch(
        self,
        symbols: list[str],
        use_cache: bool = True,
    ) -> dict[str, SentimentResult]:
        """
        Analyze sentiment for multiple symbols with rate limiting.

        Args:
            symbols: List of stock ticker symbols
            use_cache: Whether to use cached results

        Returns:
            Dictionary mapping symbols to SentimentResults
        """
        results = {}

        # Process in batches to avoid overwhelming APIs
        for i in range(0, len(symbols), self.batch_size):
            batch = symbols[i : i + self.batch_size]

            # Process batch concurrently
            tasks = [self.analyze_symbol(symbol, use_cache) for symbol in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for symbol, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error processing {symbol}: {result}")
                    results[symbol] = SentimentResult(
                        symbol=symbol,
                        source=self.source,
                        score=0.0,
                        confidence=0.0,
                        sample_size=0,
                        metadata={"error": str(result)},
                    )
                else:
                    results[symbol] = result

            # Rate limiting between batches
            if i + self.batch_size < len(symbols):
                await asyncio.sleep(self.rate_limit_delay)

        logger.info(
            f"Analyzed {len(results)} symbols from {self.source.value}, "
            f"avg score: {sum(r.score for r in results.values()) / len(results):.1f}"
        )

        return results

    def _aggregate_scores(self, scores: list[float]) -> float:
        """
        Aggregate multiple sentiment scores into a single score.

        Uses mean by default. Subclasses can override for weighted averaging.

        Args:
            scores: List of individual sentiment scores

        Returns:
            Aggregated sentiment score
        """
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    def _calculate_std(self, scores: list[float]) -> float:
        """Calculate standard deviation of scores."""
        if len(scores) < 2:
            return 0.0
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        return variance**0.5

    def clear_cache(self, symbol: str | None = None):
        """
        Clear cached results.

        Args:
            symbol: Specific symbol to clear, or None to clear all
        """
        if symbol:
            self._cache.pop(symbol.upper(), None)
        else:
            self._cache.clear()


class CombinedSentimentCalculator:
    """
    Combines sentiment from multiple sources into a single score.

    Weighting:
    - News sentiment: 40%
    - Social sentiment: 30%
    - Velocity (trend): 30%
    """

    # Default weights for combining sentiments
    NEWS_WEIGHT = 0.4
    SOCIAL_WEIGHT = 0.3
    VELOCITY_WEIGHT = 0.3

    def __init__(
        self,
        news_weight: float = NEWS_WEIGHT,
        social_weight: float = SOCIAL_WEIGHT,
        velocity_weight: float = VELOCITY_WEIGHT,
    ):
        """
        Initialize with custom weights.

        Args:
            news_weight: Weight for news sentiment (0-1)
            social_weight: Weight for social sentiment (0-1)
            velocity_weight: Weight for velocity/trend (0-1)
        """
        # Normalize weights to sum to 1
        total = news_weight + social_weight + velocity_weight
        self.news_weight = news_weight / total
        self.social_weight = social_weight / total
        self.velocity_weight = velocity_weight / total

    def calculate_combined(
        self,
        news_result: SentimentResult | None,
        social_result: SentimentResult | None,
        historical_scores: list[SentimentHistoryRecord] | None = None,
    ) -> SentimentScore:
        """
        Calculate combined sentiment score from multiple sources.

        Args:
            news_result: Sentiment from news analysis
            social_result: Sentiment from social media
            historical_scores: Past sentiment records for velocity calculation

        Returns:
            SentimentScore with combined metrics
        """
        symbol = (
            news_result.symbol
            if news_result
            else social_result.symbol if social_result else "UNKNOWN"
        )

        # Extract individual sentiments
        news_sentiment = (
            news_result.score if news_result and news_result.confidence > 0 else None
        )
        social_sentiment = (
            social_result.score
            if social_result and social_result.confidence > 0
            else None
        )

        # Calculate velocity from historical data
        velocity = (
            self._calculate_velocity(historical_scores) if historical_scores else None
        )

        # Calculate combined sentiment
        combined = self._weighted_combine(news_sentiment, social_sentiment, velocity)

        return SentimentScore(
            symbol=symbol,
            news_sentiment=news_sentiment,
            social_sentiment=social_sentiment,
            combined_sentiment=combined,
            velocity=velocity,
            news_sample_size=news_result.sample_size if news_result else 0,
            social_sample_size=social_result.sample_size if social_result else 0,
            last_updated=datetime.utcnow(),
        )

    def _weighted_combine(
        self,
        news: float | None,
        social: float | None,
        velocity: float | None,
    ) -> float | None:
        """
        Combine sentiments using weighted average.

        Adjusts weights dynamically when some sources are missing.
        """
        components = []
        weights = []

        if news is not None:
            components.append(news)
            weights.append(self.news_weight)

        if social is not None:
            components.append(social)
            weights.append(self.social_weight)

        if velocity is not None:
            # Convert velocity to sentiment-like scale
            # Positive velocity = bullish signal, negative = bearish
            velocity_sentiment = max(-100, min(100, velocity * 10))
            components.append(velocity_sentiment)
            weights.append(self.velocity_weight)

        if not components:
            return None

        # Normalize weights
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]

        # Weighted average
        combined = sum(c * w for c, w in zip(components, normalized_weights))
        return max(-100.0, min(100.0, combined))

    def _calculate_velocity(
        self,
        historical: list[SentimentHistoryRecord],
        days: int = 7,
    ) -> float | None:
        """
        Calculate sentiment velocity (rate of change) over time.

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

        velocity = (
            newest.combined_sentiment - oldest.combined_sentiment
        ) / days_elapsed
        return velocity

    def create_history_record(
        self,
        score: SentimentScore,
    ) -> SentimentHistoryRecord:
        """
        Create a history record from a sentiment score.

        Args:
            score: Current sentiment score

        Returns:
            SentimentHistoryRecord for storage
        """
        return SentimentHistoryRecord(
            symbol=score.symbol,
            recorded_at=score.last_updated,
            news_sentiment=score.news_sentiment,
            social_sentiment=score.social_sentiment,
            combined_sentiment=score.combined_sentiment,
            news_sample_size=score.news_sample_size,
            social_sample_size=score.social_sample_size,
        )
