"""
Sentiment Scoring Job

Analyzes sentiment for all stocks from multiple sources.
Runs as part of the nightly job pipeline after market data update.
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports when running as script
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from data.sentiment.combined import SentimentOrchestrator
from database import get_supabase_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


async def get_stock_symbols() -> list[str]:
    """Fetch all stock symbols from database."""
    try:
        supabase = get_supabase_client()
        result = supabase.table("stocks").select("symbol").execute()
        return [row["symbol"] for row in result.data]
    except Exception as e:
        logger.error(f"Error fetching stock symbols: {e}")
        return []


async def run_sentiment_job(
    symbols: list[str] | None = None,
    save_to_db: bool = True,
) -> dict:
    """
    Main entry point for sentiment scoring job.

    Args:
        symbols: Optional list of specific symbols (default: all stocks)
        save_to_db: Whether to save results to database

    Returns:
        Job summary dictionary
    """
    logger.info("=" * 60)
    logger.info("SENTIMENT SCORING JOB STARTED")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)

    start_time = datetime.utcnow()
    supabase = get_supabase_client()

    try:
        # Get symbols to process
        if symbols is None:
            logger.info("Fetching stock symbols from database...")
            symbols = await get_stock_symbols()

        if not symbols:
            logger.warning("No symbols to process")
            return {
                "status": "warning",
                "message": "No symbols to process",
                "stocks_processed": 0,
            }

        logger.info(f"Processing {len(symbols)} symbols")

        # Initialize orchestrator with database client
        orchestrator = SentimentOrchestrator(db_client=supabase)

        try:
            # Analyze sentiment for all symbols
            logger.info("Analyzing sentiment from all sources...")
            results = await orchestrator.analyze_batch(
                symbols=symbols,
                fetch_historical=True,
            )

            # Calculate statistics
            total = len(results)
            with_news = sum(1 for r in results.values() if r.news_sentiment is not None)
            with_social = sum(1 for r in results.values() if r.social_sentiment is not None)
            with_combined = sum(1 for r in results.values() if r.combined_sentiment is not None)
            with_velocity = sum(1 for r in results.values() if r.velocity is not None)

            # Calculate average sentiments
            news_scores = [r.news_sentiment for r in results.values() if r.news_sentiment is not None]
            social_scores = [r.social_sentiment for r in results.values() if r.social_sentiment is not None]
            combined_scores = [r.combined_sentiment for r in results.values() if r.combined_sentiment is not None]

            avg_news = sum(news_scores) / len(news_scores) if news_scores else 0
            avg_social = sum(social_scores) / len(social_scores) if social_scores else 0
            avg_combined = sum(combined_scores) / len(combined_scores) if combined_scores else 0

            logger.info(f"Coverage: news={with_news}, social={with_social}, combined={with_combined}")
            logger.info(f"Averages: news={avg_news:.1f}, social={avg_social:.1f}, combined={avg_combined:.1f}")

            # Save to database
            db_success = 0
            db_failures = 0
            if save_to_db:
                logger.info("Saving sentiment scores to database...")
                db_success, db_failures = await orchestrator.save_to_database(results)
                logger.info(f"Database: {db_success} success, {db_failures} failures")

            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            summary = {
                "status": "success" if db_failures == 0 else "partial",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": round(duration, 2),
                "symbols_processed": total,
                "coverage": {
                    "news": with_news,
                    "social": with_social,
                    "combined": with_combined,
                    "velocity": with_velocity,
                },
                "averages": {
                    "news": round(avg_news, 2),
                    "social": round(avg_social, 2),
                    "combined": round(avg_combined, 2),
                },
                "database": {
                    "success": db_success,
                    "failures": db_failures,
                },
            }

            logger.info("=" * 60)
            logger.info("JOB SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Status: {summary['status']}")
            logger.info(f"Duration: {summary['duration_seconds']}s")
            logger.info(f"Symbols: {summary['symbols_processed']}")
            logger.info(f"Coverage: {summary['coverage']}")
            logger.info(f"Averages: {summary['averages']}")

            return summary

        finally:
            await orchestrator.close()

    except Exception as e:
        logger.exception(f"JOB FAILED WITH EXCEPTION: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "duration_seconds": (datetime.utcnow() - start_time).total_seconds(),
        }


async def run_quick_sentiment(
    symbols: list[str] | None = None,
) -> dict:
    """
    Run a quick sentiment check for specific symbols.
    Useful for testing or on-demand analysis.

    Args:
        symbols: List of symbols to analyze (default: top 10)

    Returns:
        Dictionary mapping symbols to sentiment data
    """
    if symbols is None:
        # Default to top 10 popular stocks
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "JPM", "V", "UNH"]

    logger.info(f"Running quick sentiment analysis for {len(symbols)} symbols")

    supabase = get_supabase_client()
    orchestrator = SentimentOrchestrator(db_client=supabase)

    try:
        results = await orchestrator.analyze_batch(
            symbols=symbols,
            fetch_historical=True,
        )

        # Format results for display
        formatted = {}
        for symbol, score in results.items():
            formatted[symbol] = {
                "news": round(score.news_sentiment, 1) if score.news_sentiment else None,
                "social": round(score.social_sentiment, 1) if score.social_sentiment else None,
                "combined": round(score.combined_sentiment, 1) if score.combined_sentiment else None,
                "velocity": round(score.velocity, 2) if score.velocity else None,
                "direction": score.velocity_direction,
            }

        return formatted

    finally:
        await orchestrator.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sentiment Scoring Job Runner")
    parser.add_argument("--full", action="store_true", help="Run full sentiment analysis for all stocks")
    parser.add_argument("--quick", action="store_true", help="Run quick analysis (top 10 stocks)")
    parser.add_argument("--symbols", nargs="+", help="Specific symbols to analyze")
    parser.add_argument("--no-save", action="store_true", help="Don't save to database")

    args = parser.parse_args()

    if args.full:
        summary = asyncio.run(run_sentiment_job(save_to_db=not args.no_save))
        print(f"\nSentiment job complete: {summary['status']}")
    elif args.quick:
        results = asyncio.run(run_quick_sentiment())
        print("\nQuick sentiment analysis:")
        for symbol, data in results.items():
            print(f"  {symbol}: combined={data['combined']}, velocity={data['velocity']} ({data['direction']})")
    elif args.symbols:
        summary = asyncio.run(run_sentiment_job(symbols=args.symbols, save_to_db=not args.no_save))
        print(f"\nSentiment job complete: {summary}")
    else:
        print("Usage:")
        print("  python sentiment_job.py --full           # Full analysis for all stocks")
        print("  python sentiment_job.py --quick          # Quick analysis (top 10)")
        print("  python sentiment_job.py --symbols AAPL MSFT  # Specific symbols")
        print("  python sentiment_job.py --full --no-save # Don't save to database")
