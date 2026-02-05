"""
Sentiment Analysis Module

Provides sentiment analysis from multiple sources:
- News: Google News RSS + FinBERT analysis
- Social: StockTwits API + Reddit PRAW

Exports:
- SentimentAnalyzer: Abstract base class
- CombinedSentimentCalculator: Combines multiple sources
- NewsSentimentAnalyzer: News headlines via FinBERT
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
from data.sentiment.news import (
    FinBERTAnalyzer,
    NewsSentimentAnalyzer,
    analyze_news_sentiment,
)

__all__ = [
    # Base classes
    "SentimentAnalyzer",
    "CombinedSentimentCalculator",
    # News sentiment
    "NewsSentimentAnalyzer",
    "FinBERTAnalyzer",
    "analyze_news_sentiment",
    # Models
    "SentimentResult",
    "SentimentScore",
    "SentimentSource",
    "SentimentStrength",
    "NewsItem",
    "SocialPost",
    "SentimentHistoryRecord",
]
