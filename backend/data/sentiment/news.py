"""
News Sentiment Analyzer

Fetches news headlines from Google News RSS and analyzes sentiment using FinBERT.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote

import feedparser

from config import get_settings
from data.sentiment.base import SentimentAnalyzer
from data.sentiment.models import NewsItem, SentimentResult, SentimentSource

logger = logging.getLogger(__name__)

# Company name mappings for better news searches
TICKER_TO_COMPANY = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "GOOGL": "Google Alphabet",
    "GOOG": "Google Alphabet",
    "AMZN": "Amazon",
    "META": "Meta Facebook",
    "NVDA": "NVIDIA",
    "TSLA": "Tesla",
    "BRK.B": "Berkshire Hathaway",
    "BRK.A": "Berkshire Hathaway",
    "UNH": "UnitedHealth",
    "JNJ": "Johnson Johnson",
    "JPM": "JPMorgan Chase",
    "V": "Visa",
    "PG": "Procter Gamble",
    "XOM": "Exxon Mobil",
    "HD": "Home Depot",
    "CVX": "Chevron",
    "MA": "Mastercard",
    "ABBV": "AbbVie",
    "PFE": "Pfizer",
    "COST": "Costco",
    "MRK": "Merck",
    "KO": "Coca-Cola",
    "PEP": "PepsiCo",
    "AVGO": "Broadcom",
    "TMO": "Thermo Fisher",
    "WMT": "Walmart",
    "MCD": "McDonald's",
    "CSCO": "Cisco",
    "ACN": "Accenture",
    "ABT": "Abbott",
    "DHR": "Danaher",
    "LLY": "Eli Lilly",
    "ADBE": "Adobe",
    "CRM": "Salesforce",
    "NKE": "Nike",
    "ORCL": "Oracle",
    "NFLX": "Netflix",
    "AMD": "AMD Advanced Micro Devices",
    "INTC": "Intel",
    "QCOM": "Qualcomm",
    "TXN": "Texas Instruments",
    "PYPL": "PayPal",
    "DIS": "Disney",
    "CMCSA": "Comcast",
    "VZ": "Verizon",
    "T": "AT&T",
    "BA": "Boeing",
    "CAT": "Caterpillar",
    "GE": "General Electric",
    "HON": "Honeywell",
    "UPS": "UPS",
    "RTX": "Raytheon",
    "LMT": "Lockheed Martin",
    "GS": "Goldman Sachs",
    "MS": "Morgan Stanley",
    "C": "Citigroup",
    "BAC": "Bank of America",
    "WFC": "Wells Fargo",
    "AXP": "American Express",
    "SPGI": "S&P Global",
    "BLK": "BlackRock",
}


class FinBERTAnalyzer:
    """
    FinBERT-based sentiment analyzer for financial text.

    Uses the ProsusAI/finbert model which is fine-tuned on financial news.
    Outputs: positive, negative, neutral with confidence scores.
    """

    _instance = None
    _model = None
    _tokenizer = None

    def __new__(cls):
        """Singleton pattern - only load model once."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize FinBERT model (lazy loading)."""
        self._settings = get_settings()
        self._model_name = self._settings.finbert_model_name
        self._max_length = self._settings.finbert_max_length
        self._pipeline = None

    def _load_model(self):
        """Lazy load the model on first use."""
        if self._pipeline is not None:
            return

        try:
            from transformers import pipeline

            logger.info(f"Loading FinBERT model: {self._model_name}")
            self._pipeline = pipeline(
                "sentiment-analysis",
                model=self._model_name,
                tokenizer=self._model_name,
                truncation=True,
                max_length=self._max_length,
            )
            logger.info("FinBERT model loaded successfully")

        except ImportError:
            logger.error(
                "transformers library not installed. "
                "Install with: pip install transformers torch"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to load FinBERT model: {e}")
            raise

    def analyze(self, text: str) -> tuple[float, float]:
        """
        Analyze sentiment of text using FinBERT.

        Args:
            text: Text to analyze (headline, article snippet)

        Returns:
            Tuple of (sentiment_score, confidence)
            - sentiment_score: -100 (bearish) to +100 (bullish)
            - confidence: 0.0 to 1.0
        """
        if not text or len(text.strip()) < 5:
            return 0.0, 0.0

        self._load_model()

        try:
            # FinBERT returns: {'label': 'positive/negative/neutral', 'score': 0.0-1.0}
            result = self._pipeline(text[: self._max_length])[0]

            label = result["label"].lower()
            confidence = result["score"]

            # Convert to -100 to +100 scale
            if label == "positive":
                sentiment = confidence * 100
            elif label == "negative":
                sentiment = -confidence * 100
            else:  # neutral
                sentiment = 0.0
                # Lower confidence for neutral (less informative)
                confidence *= 0.5

            return sentiment, confidence

        except Exception as e:
            logger.warning(f"FinBERT analysis failed: {e}")
            return 0.0, 0.0

    def analyze_batch(self, texts: list[str]) -> list[tuple[float, float]]:
        """
        Analyze multiple texts in batch for efficiency.

        Args:
            texts: List of texts to analyze

        Returns:
            List of (sentiment_score, confidence) tuples
        """
        if not texts:
            return []

        self._load_model()

        try:
            # Filter and truncate texts
            valid_texts = [
                t[: self._max_length] for t in texts if t and len(t.strip()) >= 5
            ]

            if not valid_texts:
                return [(0.0, 0.0)] * len(texts)

            results = self._pipeline(valid_texts)

            scores = []
            result_idx = 0

            for text in texts:
                if not text or len(text.strip()) < 5:
                    scores.append((0.0, 0.0))
                else:
                    result = results[result_idx]
                    label = result["label"].lower()
                    confidence = result["score"]

                    if label == "positive":
                        sentiment = confidence * 100
                    elif label == "negative":
                        sentiment = -confidence * 100
                    else:
                        sentiment = 0.0
                        confidence *= 0.5

                    scores.append((sentiment, confidence))
                    result_idx += 1

            return scores

        except Exception as e:
            logger.error(f"FinBERT batch analysis failed: {e}")
            return [(0.0, 0.0)] * len(texts)


class NewsSentimentAnalyzer(SentimentAnalyzer):
    """
    News sentiment analyzer using Google News RSS and FinBERT.

    Fetches recent news headlines for a stock and analyzes sentiment
    using the FinBERT financial sentiment model.
    """

    # Google News RSS base URL
    GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"

    # Number of days to look back for news
    DEFAULT_LOOKBACK_DAYS = 7

    # Maximum headlines to analyze per ticker
    MAX_HEADLINES = 20

    def __init__(
        self,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        max_headlines: int = MAX_HEADLINES,
        **kwargs,
    ):
        """
        Initialize news sentiment analyzer.

        Args:
            lookback_days: How many days back to search for news
            max_headlines: Maximum headlines to analyze per ticker
            **kwargs: Additional args for base SentimentAnalyzer
        """
        super().__init__(source=SentimentSource.NEWS, **kwargs)

        self.lookback_days = lookback_days
        self.max_headlines = max_headlines
        self._finbert = FinBERTAnalyzer()

    def _get_search_query(self, symbol: str) -> str:
        """
        Build search query for a stock symbol.

        Uses company name when available for better results.
        """
        # Get company name if available
        company = TICKER_TO_COMPANY.get(symbol.upper())

        if company:
            # Search for company name + stock
            query = f'"{company}" stock'
        else:
            # Fall back to ticker symbol
            query = f"{symbol} stock"

        return query

    def _parse_rss_date(self, date_str: str) -> datetime | None:
        """Parse RSS date string to datetime."""
        try:
            # feedparser normalizes dates to struct_time
            if hasattr(date_str, "tm_year"):
                return datetime(*date_str[:6])
            # Try parsing common formats
            for fmt in [
                "%a, %d %b %Y %H:%M:%S %Z",
                "%a, %d %b %Y %H:%M:%S %z",
                "%Y-%m-%dT%H:%M:%SZ",
            ]:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            return None
        except Exception:
            return None

    def _clean_headline(self, headline: str) -> str:
        """Clean and normalize headline text."""
        # Remove HTML entities
        headline = re.sub(r"&[a-zA-Z]+;", " ", headline)
        # Remove extra whitespace
        headline = " ".join(headline.split())
        # Remove source suffix (e.g., " - Reuters")
        headline = re.sub(r"\s*-\s*[A-Za-z\s]+$", "", headline)
        return headline.strip()

    async def fetch_data(self, symbol: str) -> list[NewsItem]:
        """
        Fetch news headlines from Google News RSS.

        Args:
            symbol: Stock ticker symbol

        Returns:
            List of NewsItem objects
        """
        symbol = symbol.upper()
        query = self._get_search_query(symbol)

        # Build RSS URL
        encoded_query = quote(query)
        url = f"{self.GOOGLE_NEWS_RSS}?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

        try:
            # feedparser is synchronous, run in executor
            loop = asyncio.get_event_loop()
            feed = await loop.run_in_executor(None, feedparser.parse, url)

            if not feed.entries:
                logger.debug(f"No news found for {symbol}")
                return []

            # Filter and convert entries
            cutoff_date = datetime.utcnow() - timedelta(days=self.lookback_days)
            news_items = []

            for entry in feed.entries[
                : self.max_headlines * 2
            ]:  # Fetch extra for filtering
                # Parse publication date
                pub_date = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, "published"):
                    pub_date = self._parse_rss_date(entry.published)

                # Skip old articles
                if pub_date and pub_date < cutoff_date:
                    continue

                # Extract headline
                title = entry.get("title", "")
                if not title:
                    continue

                # Clean headline
                clean_title = self._clean_headline(title)
                if len(clean_title) < 10:
                    continue

                # Extract source
                source = "Google News"
                if hasattr(entry, "source") and entry.source:
                    source = entry.source.get("title", source)

                news_items.append(
                    NewsItem(
                        title=clean_title,
                        source=source,
                        url=entry.get("link"),
                        published_at=pub_date,
                        symbol=symbol,
                    )
                )

                if len(news_items) >= self.max_headlines:
                    break

            logger.debug(f"Fetched {len(news_items)} headlines for {symbol}")
            return news_items

        except Exception as e:
            logger.error(f"Error fetching news for {symbol}: {e}")
            return []

    async def analyze_item(self, item: Any, symbol: str) -> float | None:
        """
        Analyze sentiment of a single news item.

        Args:
            item: NewsItem to analyze
            symbol: Stock ticker symbol

        Returns:
            Sentiment score (-100 to +100) or None if failed
        """
        if not isinstance(item, NewsItem):
            return None

        try:
            # Run FinBERT analysis
            loop = asyncio.get_event_loop()
            score, confidence = await loop.run_in_executor(
                None, self._finbert.analyze, item.title
            )

            # Store score in item for reference
            item.sentiment_score = score
            item.sentiment_confidence = confidence

            # Return weighted by confidence
            if confidence < 0.3:
                return None  # Skip low confidence

            return score

        except Exception as e:
            logger.warning(f"Error analyzing headline: {e}")
            return None

    def calculate_confidence(self, scores: list[float], sample_size: int) -> float:
        """
        Calculate confidence based on sample size and score consistency.

        Args:
            scores: List of sentiment scores
            sample_size: Number of items analyzed

        Returns:
            Confidence score (0.0 to 1.0)
        """
        if not scores:
            return 0.0

        # Base confidence from sample size
        # More headlines = higher confidence (up to 0.7)
        size_confidence = min(0.7, sample_size / 15)

        # Consistency bonus (low std = higher confidence)
        if len(scores) >= 2:
            std = self._calculate_std(scores)
            # Std of 0 = perfect agreement, std of 100 = max disagreement
            consistency_bonus = max(0, 0.3 * (1 - std / 50))
        else:
            consistency_bonus = 0.0

        return min(1.0, size_confidence + consistency_bonus)

    async def analyze_symbol(
        self, symbol: str, use_cache: bool = True
    ) -> SentimentResult:
        """
        Override to use batch FinBERT analysis for efficiency.
        """
        symbol = symbol.upper()

        # Check cache first
        if use_cache and symbol in self._cache:
            cached_result, cached_time = self._cache[symbol]
            if datetime.utcnow() - cached_time < timedelta(
                minutes=self.cache_ttl_minutes
            ):
                logger.debug(f"Cache hit for {symbol} news sentiment")
                return cached_result

        try:
            # Fetch headlines
            news_items = await self.fetch_data(symbol)

            if not news_items:
                result = SentimentResult(
                    symbol=symbol,
                    source=self.source,
                    score=0.0,
                    confidence=0.0,
                    sample_size=0,
                    metadata={"reason": "no_news", "headlines": []},
                )
                self._cache[symbol] = (result, datetime.utcnow())
                return result

            # Batch analyze headlines with FinBERT
            headlines = [item.title for item in news_items]
            loop = asyncio.get_event_loop()
            sentiment_results = await loop.run_in_executor(
                None, self._finbert.analyze_batch, headlines
            )

            # Process results
            scores = []
            analyzed_items = []

            for item, (score, confidence) in zip(news_items, sentiment_results):
                item.sentiment_score = score
                item.sentiment_confidence = confidence

                if confidence >= 0.3:  # Filter low confidence
                    scores.append(score)
                    analyzed_items.append(item.to_dict())

            if not scores:
                result = SentimentResult(
                    symbol=symbol,
                    source=self.source,
                    score=0.0,
                    confidence=0.0,
                    sample_size=len(news_items),
                    metadata={"reason": "low_confidence", "headlines": []},
                )
            else:
                # Aggregate scores
                aggregated = self._aggregate_scores(scores)
                confidence = self.calculate_confidence(scores, len(news_items))

                result = SentimentResult(
                    symbol=symbol,
                    source=self.source,
                    score=aggregated,
                    confidence=confidence,
                    sample_size=len(scores),
                    metadata={
                        "headlines_fetched": len(news_items),
                        "headlines_analyzed": len(scores),
                        "score_std": round(self._calculate_std(scores), 2),
                        "top_headlines": analyzed_items[:5],
                    },
                )

            # Update cache
            self._cache[symbol] = (result, datetime.utcnow())
            return result

        except Exception as e:
            logger.error(f"Error analyzing news for {symbol}: {e}")
            return SentimentResult(
                symbol=symbol,
                source=self.source,
                score=0.0,
                confidence=0.0,
                sample_size=0,
                metadata={"error": str(e)},
            )

    def _aggregate_scores(self, scores: list[float]) -> float:
        """
        Aggregate scores with recency weighting.

        More recent headlines get slightly higher weight.
        """
        if not scores:
            return 0.0

        if len(scores) == 1:
            return scores[0]

        # Simple mean for now - could add recency weighting
        # if we track publication dates
        return sum(scores) / len(scores)


# Convenience function for direct use
async def analyze_news_sentiment(
    symbols: list[str],
    lookback_days: int = 7,
    max_headlines: int = 20,
) -> dict[str, SentimentResult]:
    """
    Analyze news sentiment for multiple symbols.

    Args:
        symbols: List of stock ticker symbols
        lookback_days: Days to look back for news
        max_headlines: Max headlines per ticker

    Returns:
        Dictionary mapping symbols to SentimentResults
    """
    analyzer = NewsSentimentAnalyzer(
        lookback_days=lookback_days,
        max_headlines=max_headlines,
    )
    return await analyzer.analyze_batch(symbols)
