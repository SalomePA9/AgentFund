"""
Sentiment Data Models

Data classes for sentiment analysis results and scoring.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SentimentSource(str, Enum):
    """Source of sentiment data."""

    NEWS = "news"
    STOCKTWITS = "stocktwits"
    REDDIT = "reddit"
    COMBINED = "combined"


class SentimentStrength(str, Enum):
    """Qualitative sentiment strength classification."""

    VERY_BEARISH = "very_bearish"  # -100 to -60
    BEARISH = "bearish"  # -60 to -20
    NEUTRAL = "neutral"  # -20 to +20
    BULLISH = "bullish"  # +20 to +60
    VERY_BULLISH = "very_bullish"  # +60 to +100


@dataclass
class SentimentResult:
    """
    Individual sentiment analysis result from a single source.

    Attributes:
        symbol: Stock ticker symbol
        source: Where the sentiment came from (news, social, etc.)
        score: Sentiment score from -100 (very bearish) to +100 (very bullish)
        confidence: Confidence level of the score (0.0 to 1.0)
        sample_size: Number of data points used in calculation
        timestamp: When this sentiment was calculated
        metadata: Additional source-specific data
    """

    symbol: str
    source: SentimentSource
    score: float  # -100 to +100
    confidence: float = 0.5  # 0.0 to 1.0
    sample_size: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate and normalize score."""
        # Clamp score to valid range
        self.score = max(-100.0, min(100.0, self.score))
        self.confidence = max(0.0, min(1.0, self.confidence))

    @property
    def strength(self) -> SentimentStrength:
        """Get qualitative strength classification."""
        if self.score <= -60:
            return SentimentStrength.VERY_BEARISH
        elif self.score <= -20:
            return SentimentStrength.BEARISH
        elif self.score <= 20:
            return SentimentStrength.NEUTRAL
        elif self.score <= 60:
            return SentimentStrength.BULLISH
        else:
            return SentimentStrength.VERY_BULLISH

    @property
    def is_bullish(self) -> bool:
        """Check if sentiment is bullish (score > 20)."""
        return self.score > 20

    @property
    def is_bearish(self) -> bool:
        """Check if sentiment is bearish (score < -20)."""
        return self.score < -20

    @property
    def is_neutral(self) -> bool:
        """Check if sentiment is neutral (-20 <= score <= 20)."""
        return -20 <= self.score <= 20

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "source": self.source.value,
            "score": round(self.score, 2),
            "confidence": round(self.confidence, 3),
            "sample_size": self.sample_size,
            "strength": self.strength.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class SentimentScore:
    """
    Combined sentiment score for a stock across all sources.

    Attributes:
        symbol: Stock ticker symbol
        news_sentiment: Sentiment from news sources
        social_sentiment: Sentiment from social media
        combined_sentiment: Weighted combination of all sources
        velocity: 7-day change in sentiment (positive = improving)
        news_sample_size: Number of news articles analyzed
        social_sample_size: Number of social posts analyzed
        last_updated: When scores were last calculated
    """

    symbol: str
    news_sentiment: float | None = None  # -100 to +100
    social_sentiment: float | None = None  # -100 to +100
    combined_sentiment: float | None = None  # -100 to +100
    velocity: float | None = None  # Change per day
    news_sample_size: int = 0
    social_sample_size: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Validate and normalize scores."""
        if self.news_sentiment is not None:
            self.news_sentiment = max(-100.0, min(100.0, self.news_sentiment))
        if self.social_sentiment is not None:
            self.social_sentiment = max(-100.0, min(100.0, self.social_sentiment))
        if self.combined_sentiment is not None:
            self.combined_sentiment = max(-100.0, min(100.0, self.combined_sentiment))

    @property
    def strength(self) -> SentimentStrength | None:
        """Get qualitative strength of combined sentiment."""
        if self.combined_sentiment is None:
            return None
        if self.combined_sentiment <= -60:
            return SentimentStrength.VERY_BEARISH
        elif self.combined_sentiment <= -20:
            return SentimentStrength.BEARISH
        elif self.combined_sentiment <= 20:
            return SentimentStrength.NEUTRAL
        elif self.combined_sentiment <= 60:
            return SentimentStrength.BULLISH
        else:
            return SentimentStrength.VERY_BULLISH

    @property
    def velocity_direction(self) -> str | None:
        """Get direction of sentiment change."""
        if self.velocity is None:
            return None
        if self.velocity > 5:
            return "improving"
        elif self.velocity < -5:
            return "declining"
        else:
            return "stable"

    @property
    def total_sample_size(self) -> int:
        """Get total number of data points analyzed."""
        return self.news_sample_size + self.social_sample_size

    @property
    def has_sufficient_data(self) -> bool:
        """Check if we have enough data for reliable sentiment."""
        return self.total_sample_size >= 5

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "news_sentiment": (
                round(self.news_sentiment, 2) if self.news_sentiment else None
            ),
            "social_sentiment": (
                round(self.social_sentiment, 2) if self.social_sentiment else None
            ),
            "combined_sentiment": (
                round(self.combined_sentiment, 2) if self.combined_sentiment else None
            ),
            "velocity": round(self.velocity, 2) if self.velocity else None,
            "velocity_direction": self.velocity_direction,
            "strength": self.strength.value if self.strength else None,
            "news_sample_size": self.news_sample_size,
            "social_sample_size": self.social_sample_size,
            "total_sample_size": self.total_sample_size,
            "has_sufficient_data": self.has_sufficient_data,
            "last_updated": self.last_updated.isoformat(),
        }

    def to_db_row(self) -> dict[str, Any]:
        """Convert to database row format for stocks table update."""
        return {
            "news_sentiment": self.news_sentiment,
            "social_sentiment": self.social_sentiment,
            "combined_sentiment": self.combined_sentiment,
            "sentiment_velocity": self.velocity,
        }


@dataclass
class NewsItem:
    """
    A news article or headline for sentiment analysis.

    Attributes:
        title: Article headline
        source: News source name
        url: Link to article
        published_at: Publication timestamp
        symbol: Associated stock ticker
        sentiment_score: Calculated sentiment (-100 to +100)
        sentiment_confidence: Confidence in the score
    """

    title: str
    source: str
    url: str | None = None
    published_at: datetime | None = None
    symbol: str | None = None
    sentiment_score: float | None = None
    sentiment_confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "source": self.source,
            "url": self.url,
            "published_at": (
                self.published_at.isoformat() if self.published_at else None
            ),
            "symbol": self.symbol,
            "sentiment_score": (
                round(self.sentiment_score, 2) if self.sentiment_score else None
            ),
            "sentiment_confidence": (
                round(self.sentiment_confidence, 3)
                if self.sentiment_confidence
                else None
            ),
        }


@dataclass
class SocialPost:
    """
    A social media post for sentiment analysis.

    Attributes:
        content: Post text content
        source: Platform (stocktwits, reddit)
        author: Username
        created_at: Post timestamp
        symbol: Associated stock ticker
        engagement: Likes, upvotes, etc.
        sentiment_score: Calculated sentiment
        sentiment_confidence: Confidence in the score
    """

    content: str
    source: SentimentSource
    author: str | None = None
    created_at: datetime | None = None
    symbol: str | None = None
    engagement: int = 0
    sentiment_score: float | None = None
    sentiment_confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content": (
                self.content[:200] + "..." if len(self.content) > 200 else self.content
            ),
            "source": self.source.value,
            "author": self.author,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "symbol": self.symbol,
            "engagement": self.engagement,
            "sentiment_score": (
                round(self.sentiment_score, 2) if self.sentiment_score else None
            ),
            "sentiment_confidence": (
                round(self.sentiment_confidence, 3)
                if self.sentiment_confidence
                else None
            ),
        }


@dataclass
class SentimentHistoryRecord:
    """
    Historical sentiment record for tracking over time.

    Used for calculating sentiment velocity and trends.
    """

    symbol: str
    recorded_at: datetime
    news_sentiment: float | None = None
    social_sentiment: float | None = None
    combined_sentiment: float | None = None
    news_sample_size: int = 0
    social_sample_size: int = 0

    def to_db_row(self) -> dict[str, Any]:
        """Convert to database row format for sentiment_history table."""
        return {
            "symbol": self.symbol,
            "recorded_at": self.recorded_at.isoformat(),
            "news_sentiment": self.news_sentiment,
            "social_sentiment": self.social_sentiment,
            "combined_sentiment": self.combined_sentiment,
            "news_sample_size": self.news_sample_size,
            "social_sample_size": self.social_sample_size,
        }
