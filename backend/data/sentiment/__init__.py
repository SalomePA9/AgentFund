"""
Sentiment Analysis Module

Provides sentiment analysis from multiple sources:
- News: Google News RSS + FinBERT analysis
- Social: StockTwits API + Alpha Vantage

Exports:
- SentimentAnalyzer: Abstract base class
- CombinedSentimentCalculator: Combines multiple sources
- SentimentOrchestrator: Full pipeline orchestration
- NewsSentimentAnalyzer: News headlines via FinBERT
- SocialSentimentAnalyzer: StockTwits + Alpha Vantage
- Data models: SentimentResult, SentimentScore, etc.
"""

from data.sentiment.base import (
    CombinedSentimentCalculator,
    SentimentAnalyzer,
)
from data.sentiment.combined import (
    SentimentOrchestrator,
    analyze_all_sentiment,
    calculate_velocity,
    interpret_velocity,
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
from data.sentiment.social import (
    AlphaVantageSentimentAnalyzer,
    SocialSentimentAnalyzer,
    StockTwitsSentimentAnalyzer,
    analyze_social_sentiment,
)

__all__ = [
    # Base classes
    "SentimentAnalyzer",
    "CombinedSentimentCalculator",
    # Orchestrator
    "SentimentOrchestrator",
    "analyze_all_sentiment",
    "calculate_velocity",
    "interpret_velocity",
    # News sentiment
    "NewsSentimentAnalyzer",
    "FinBERTAnalyzer",
    "analyze_news_sentiment",
    # Social sentiment
    "SocialSentimentAnalyzer",
    "StockTwitsSentimentAnalyzer",
    "AlphaVantageSentimentAnalyzer",
    "analyze_social_sentiment",
    # Models
    "SentimentResult",
    "SentimentScore",
    "SentimentSource",
    "SentimentStrength",
    "NewsItem",
    "SocialPost",
    "SentimentHistoryRecord",
]
