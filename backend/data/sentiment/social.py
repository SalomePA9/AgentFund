"""
Social Sentiment Analyzer

Fetches social sentiment from StockTwits and Alpha Vantage.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from config import get_settings
from data.sentiment.base import SentimentAnalyzer
from data.sentiment.models import SentimentResult, SentimentSource, SocialPost

logger = logging.getLogger(__name__)


class StockTwitsSentimentAnalyzer(SentimentAnalyzer):
    """
    StockTwits sentiment analyzer.

    Uses the public StockTwits API (no authentication required) to fetch
    recent messages about a stock and analyze sentiment.

    StockTwits provides user-labeled sentiment (bullish/bearish) on messages,
    which we aggregate with engagement weighting.
    """

    # StockTwits API endpoint
    API_BASE = "https://api.stocktwits.com/api/2"

    # Maximum messages to fetch per request
    MAX_MESSAGES = 30

    def __init__(
        self,
        max_messages: int = MAX_MESSAGES,
        **kwargs,
    ):
        """
        Initialize StockTwits analyzer.

        Args:
            max_messages: Maximum messages to analyze per ticker
            **kwargs: Additional args for base SentimentAnalyzer
        """
        super().__init__(source=SentimentSource.STOCKTWITS, **kwargs)
        self.max_messages = max_messages
        self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "User-Agent": "AgentFund/1.0",
                    "Accept": "application/json",
                },
            )
        return self._client

    async def fetch_data(self, symbol: str) -> list[SocialPost]:
        """
        Fetch recent messages from StockTwits.

        Args:
            symbol: Stock ticker symbol

        Returns:
            List of SocialPost objects
        """
        symbol = symbol.upper()
        url = f"{self.API_BASE}/streams/symbol/{symbol}.json"

        try:
            client = self._get_client()
            response = await client.get(url, params={"limit": self.max_messages})

            if response.status_code == 404:
                logger.debug(f"No StockTwits data for {symbol}")
                return []

            if response.status_code == 429:
                logger.warning("StockTwits rate limit hit")
                return []

            response.raise_for_status()
            data = response.json()

            messages = data.get("messages", [])
            if not messages:
                return []

            posts = []
            for msg in messages:
                # Extract sentiment label if provided by user
                sentiment_label = None
                if msg.get("entities", {}).get("sentiment"):
                    sentiment_label = msg["entities"]["sentiment"].get("basic")

                # Parse creation time
                created_at = None
                if msg.get("created_at"):
                    try:
                        created_at = datetime.strptime(
                            msg["created_at"], "%Y-%m-%dT%H:%M:%SZ"
                        )
                    except ValueError:
                        pass

                # Calculate engagement (likes)
                engagement = msg.get("likes", {}).get("total", 0)

                posts.append(
                    SocialPost(
                        content=msg.get("body", ""),
                        source=SentimentSource.STOCKTWITS,
                        author=msg.get("user", {}).get("username"),
                        created_at=created_at,
                        symbol=symbol,
                        engagement=engagement,
                        sentiment_score=self._label_to_score(sentiment_label),
                        sentiment_confidence=0.8 if sentiment_label else 0.0,
                    )
                )

            logger.debug(f"Fetched {len(posts)} StockTwits messages for {symbol}")
            return posts

        except httpx.HTTPError as e:
            logger.error(f"StockTwits API error for {symbol}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching StockTwits for {symbol}: {e}")
            return []

    def _label_to_score(self, label: str | None) -> float | None:
        """Convert StockTwits sentiment label to score."""
        if not label:
            return None
        label = label.lower()
        if label == "bullish":
            return 75.0  # Strong positive
        elif label == "bearish":
            return -75.0  # Strong negative
        return None

    async def analyze_item(self, item: Any, symbol: str) -> float | None:
        """
        Get sentiment score from a StockTwits post.

        StockTwits posts may have user-provided sentiment labels.
        If no label, we skip the post (don't try to infer sentiment from text).
        """
        if not isinstance(item, SocialPost):
            return None

        # Use user-provided sentiment if available
        if item.sentiment_score is not None:
            return item.sentiment_score

        # Skip posts without explicit sentiment
        return None

    def calculate_confidence(self, scores: list[float], sample_size: int) -> float:
        """
        Calculate confidence based on sample size and label availability.
        """
        if not scores:
            return 0.0

        # Base confidence from labeled sample size
        labeled_ratio = len(scores) / max(sample_size, 1)
        size_confidence = min(0.6, len(scores) / 20)

        # Bonus for having many labeled posts
        label_bonus = min(0.3, labeled_ratio * 0.4)

        return min(1.0, size_confidence + label_bonus)

    def _aggregate_scores(self, scores: list[float]) -> float:
        """
        Aggregate scores - simple mean for StockTwits.

        Could add engagement weighting in the future.
        """
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class AlphaVantageSentimentAnalyzer(SentimentAnalyzer):
    """
    Alpha Vantage News Sentiment analyzer.

    Uses Alpha Vantage's News Sentiment API which provides pre-analyzed
    sentiment scores for news articles about stocks.

    Free tier: 25 requests/day (sufficient for nightly batch job)
    """

    # Alpha Vantage API endpoint
    API_BASE = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str | None = None, **kwargs):
        """
        Initialize Alpha Vantage analyzer.

        Args:
            api_key: Alpha Vantage API key (from settings if not provided)
            **kwargs: Additional args for base SentimentAnalyzer
        """
        super().__init__(source=SentimentSource.STOCKTWITS, **kwargs)  # Reuse source enum

        settings = get_settings()
        self.api_key = api_key or settings.alphavantage_api_key
        self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"User-Agent": "AgentFund/1.0"},
            )
        return self._client

    async def fetch_data(self, symbol: str) -> list[dict]:
        """
        Fetch news sentiment from Alpha Vantage.

        Args:
            symbol: Stock ticker symbol

        Returns:
            List of news items with sentiment scores
        """
        if not self.api_key:
            logger.warning("Alpha Vantage API key not configured")
            return []

        symbol = symbol.upper()

        try:
            client = self._get_client()
            response = await client.get(
                self.API_BASE,
                params={
                    "function": "NEWS_SENTIMENT",
                    "tickers": symbol,
                    "apikey": self.api_key,
                    "limit": 50,
                },
            )

            if response.status_code != 200:
                logger.error(f"Alpha Vantage API error: {response.status_code}")
                return []

            data = response.json()

            # Check for API limit message
            if "Note" in data or "Information" in data:
                logger.warning(f"Alpha Vantage API limit: {data.get('Note') or data.get('Information')}")
                return []

            feed = data.get("feed", [])
            if not feed:
                logger.debug(f"No Alpha Vantage news for {symbol}")
                return []

            # Filter for articles about this specific ticker
            relevant_items = []
            for item in feed:
                ticker_sentiments = item.get("ticker_sentiment", [])
                for ts in ticker_sentiments:
                    if ts.get("ticker") == symbol:
                        relevant_items.append({
                            "title": item.get("title", ""),
                            "source": item.get("source", ""),
                            "url": item.get("url", ""),
                            "time_published": item.get("time_published", ""),
                            "sentiment_score": float(ts.get("ticker_sentiment_score", 0)),
                            "relevance_score": float(ts.get("relevance_score", 0)),
                            "sentiment_label": ts.get("ticker_sentiment_label", ""),
                        })
                        break

            logger.debug(f"Fetched {len(relevant_items)} Alpha Vantage items for {symbol}")
            return relevant_items

        except httpx.HTTPError as e:
            logger.error(f"Alpha Vantage API error for {symbol}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching Alpha Vantage for {symbol}: {e}")
            return []

    async def analyze_item(self, item: Any, symbol: str) -> float | None:
        """
        Extract sentiment from Alpha Vantage item.

        Alpha Vantage provides pre-calculated sentiment scores.
        Score range: -1 to 1, we convert to -100 to +100.
        """
        if not isinstance(item, dict):
            return None

        score = item.get("sentiment_score", 0)
        relevance = item.get("relevance_score", 0)

        # Skip low relevance items
        if relevance < 0.3:
            return None

        # Convert -1 to 1 range to -100 to +100
        return score * 100

    def calculate_confidence(self, scores: list[float], sample_size: int) -> float:
        """
        Calculate confidence based on sample size.
        """
        if not scores:
            return 0.0

        # Alpha Vantage provides high-quality pre-analyzed sentiment
        size_confidence = min(0.8, len(scores) / 10)

        return min(1.0, size_confidence + 0.1)

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class SocialSentimentAnalyzer:
    """
    Combined social sentiment analyzer.

    Aggregates sentiment from multiple social sources:
    - StockTwits (user-labeled sentiment)
    - Alpha Vantage (pre-analyzed news sentiment)

    Returns a weighted combination of all available sources.
    """

    # Weights for combining sources
    STOCKTWITS_WEIGHT = 0.6
    ALPHAVANTAGE_WEIGHT = 0.4

    def __init__(
        self,
        stocktwits_weight: float = STOCKTWITS_WEIGHT,
        alphavantage_weight: float = ALPHAVANTAGE_WEIGHT,
        cache_ttl_minutes: int = 30,
    ):
        """
        Initialize combined social analyzer.

        Args:
            stocktwits_weight: Weight for StockTwits sentiment
            alphavantage_weight: Weight for Alpha Vantage sentiment
            cache_ttl_minutes: Cache TTL in minutes
        """
        settings = get_settings()

        # Normalize weights
        total = stocktwits_weight + alphavantage_weight
        self.stocktwits_weight = stocktwits_weight / total
        self.alphavantage_weight = alphavantage_weight / total

        # Initialize individual analyzers
        self._stocktwits = StockTwitsSentimentAnalyzer(
            cache_ttl_minutes=cache_ttl_minutes
        ) if settings.stocktwits_enabled else None

        self._alphavantage = AlphaVantageSentimentAnalyzer(
            cache_ttl_minutes=cache_ttl_minutes
        ) if settings.alphavantage_api_key else None

        # Combined cache
        self._cache: dict[str, tuple[SentimentResult, datetime]] = {}
        self.cache_ttl_minutes = cache_ttl_minutes

    async def analyze_symbol(self, symbol: str, use_cache: bool = True) -> SentimentResult:
        """
        Analyze social sentiment for a symbol from all sources.

        Args:
            symbol: Stock ticker symbol
            use_cache: Whether to use cached results

        Returns:
            Combined SentimentResult
        """
        symbol = symbol.upper()

        # Check cache
        if use_cache and symbol in self._cache:
            cached_result, cached_time = self._cache[symbol]
            if datetime.utcnow() - cached_time < timedelta(minutes=self.cache_ttl_minutes):
                return cached_result

        results = []
        weights = []
        total_sample_size = 0

        # Fetch from StockTwits
        if self._stocktwits:
            try:
                st_result = await self._stocktwits.analyze_symbol(symbol, use_cache)
                if st_result.confidence > 0:
                    results.append(st_result.score)
                    weights.append(self.stocktwits_weight * st_result.confidence)
                    total_sample_size += st_result.sample_size
            except Exception as e:
                logger.warning(f"StockTwits error for {symbol}: {e}")

        # Fetch from Alpha Vantage
        if self._alphavantage:
            try:
                av_result = await self._alphavantage.analyze_symbol(symbol, use_cache)
                if av_result.confidence > 0:
                    results.append(av_result.score)
                    weights.append(self.alphavantage_weight * av_result.confidence)
                    total_sample_size += av_result.sample_size
            except Exception as e:
                logger.warning(f"Alpha Vantage error for {symbol}: {e}")

        # Combine results
        if not results:
            result = SentimentResult(
                symbol=symbol,
                source=SentimentSource.STOCKTWITS,  # Generic social
                score=0.0,
                confidence=0.0,
                sample_size=0,
                metadata={"reason": "no_data", "sources": []},
            )
        else:
            # Weighted average
            total_weight = sum(weights)
            combined_score = sum(s * w for s, w in zip(results, weights)) / total_weight
            combined_confidence = min(1.0, total_weight)

            sources_used = []
            if self._stocktwits:
                sources_used.append("stocktwits")
            if self._alphavantage:
                sources_used.append("alphavantage")

            result = SentimentResult(
                symbol=symbol,
                source=SentimentSource.STOCKTWITS,
                score=combined_score,
                confidence=combined_confidence,
                sample_size=total_sample_size,
                metadata={
                    "sources": sources_used,
                    "individual_scores": results,
                    "weights": weights,
                },
            )

        # Update cache
        self._cache[symbol] = (result, datetime.utcnow())
        return result

    async def analyze_batch(
        self,
        symbols: list[str],
        use_cache: bool = True,
    ) -> dict[str, SentimentResult]:
        """
        Analyze social sentiment for multiple symbols.

        Args:
            symbols: List of stock ticker symbols
            use_cache: Whether to use cached results

        Returns:
            Dictionary mapping symbols to SentimentResults
        """
        results = {}

        # Process in batches to avoid rate limits
        batch_size = 5
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]

            # Process batch concurrently
            tasks = [self.analyze_symbol(s, use_cache) for s in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for symbol, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error processing {symbol}: {result}")
                    results[symbol] = SentimentResult(
                        symbol=symbol,
                        source=SentimentSource.STOCKTWITS,
                        score=0.0,
                        confidence=0.0,
                        sample_size=0,
                        metadata={"error": str(result)},
                    )
                else:
                    results[symbol] = result

            # Rate limiting between batches
            if i + batch_size < len(symbols):
                await asyncio.sleep(1.0)

        return results

    def clear_cache(self, symbol: str | None = None):
        """Clear cached results."""
        if symbol:
            self._cache.pop(symbol.upper(), None)
            if self._stocktwits:
                self._stocktwits.clear_cache(symbol)
            if self._alphavantage:
                self._alphavantage.clear_cache(symbol)
        else:
            self._cache.clear()
            if self._stocktwits:
                self._stocktwits.clear_cache()
            if self._alphavantage:
                self._alphavantage.clear_cache()

    async def close(self):
        """Close all HTTP clients."""
        if self._stocktwits:
            await self._stocktwits.close()
        if self._alphavantage:
            await self._alphavantage.close()


# Convenience function for direct use
async def analyze_social_sentiment(
    symbols: list[str],
    use_cache: bool = True,
) -> dict[str, SentimentResult]:
    """
    Analyze social sentiment for multiple symbols.

    Args:
        symbols: List of stock ticker symbols
        use_cache: Whether to use cached results

    Returns:
        Dictionary mapping symbols to SentimentResults
    """
    analyzer = SocialSentimentAnalyzer()
    try:
        return await analyzer.analyze_batch(symbols, use_cache)
    finally:
        await analyzer.close()
