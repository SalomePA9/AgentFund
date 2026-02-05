"""
Sentiment Analysis Module

Provides sentiment analysis from multiple sources:
- News: Google News RSS + FinBERT analysis
- Social: StockTwits API + Reddit PRAW

Exports:
- SentimentAnalyzer: Abstract base class
- CombinedSentimentCalculator: Combines multiple sources
- Data models: SentimentResult, SentimentScore, etc.
"""

from data.sentiment.base import (
    CombinedSentimentCalculator,
    SentimentAnalyzer,
)
from data.sentiment.models import (
    NewsItem,
    SentimentHistoryRecord,
    SentimentResult,
    SentimentScore,
    SentimentSource,
    SentimentStrength,
    SocialPost,
)

__all__ = [
    # Base classes
    "SentimentAnalyzer",
    "CombinedSentimentCalculator",
    # Models
    "SentimentResult",
    "SentimentScore",
    "SentimentSource",
    "SentimentStrength",
    "NewsItem",
    "SocialPost",
    "SentimentHistoryRecord",
]
