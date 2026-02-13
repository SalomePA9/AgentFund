"""
Market Data Scheduled Job
Runs daily to update stock prices, moving averages, fundamentals, and factor scores.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports when running as script
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from data.market_data import get_stock_universe, run_market_data_update  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


async def run_daily_market_update():
    """
    Main entry point for daily market data update.
    Designed to be run by GitHub Actions at 6 AM ET.
    """
    logger.info("=" * 60)
    logger.info("MARKET DATA UPDATE JOB STARTED")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)

    try:
        # Get stock universe
        tickers = get_stock_universe()
        logger.info(f"Stock universe size: {len(tickers)}")

        # Run the update
        summary = await run_market_data_update(tickers=tickers, batch_size=50)

        # Log summary
        logger.info("=" * 60)
        logger.info("JOB SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Duration: {summary['duration_seconds']} seconds")
        logger.info(f"Total tickers: {summary['total_tickers']}")
        logger.info(f"Fetch success: {summary['fetch_success']}")
        logger.info(f"Fetch failed: {summary['fetch_failed']}")
        logger.info(f"Database success: {summary['db_success']}")
        logger.info(f"Database failed: {summary['db_failed']}")
        logger.info(f"History stored: {summary['history_stored']}")

        if summary["failed_tickers"]:
            logger.warning(
                f"Failed tickers (first 20): {summary['failed_tickers'][:20]}"
            )

        # Calculate success rate
        success_rate = (summary["fetch_success"] / summary["total_tickers"]) * 100
        logger.info(f"Success rate: {success_rate:.1f}%")

        # Run factor scoring job after market data update
        logger.info("")
        logger.info("=" * 60)
        logger.info("STARTING FACTOR SCORING JOB")
        logger.info("=" * 60)

        try:
            from jobs.factor_scoring_job import run_factor_scoring_job

            factor_summary = await run_factor_scoring_job()
        except Exception as e:
            logger.error(f"Factor scoring job failed: {e}")
            factor_summary = {"status": "error", "error": str(e)}

        logger.info("")
        logger.info("=" * 60)
        logger.info("FACTOR SCORING SUMMARY")
        logger.info("=" * 60)
        for key, value in factor_summary.items():
            logger.info(f"{key}: {value}")

        # Run sentiment analysis job
        logger.info("")
        logger.info("=" * 60)
        logger.info("STARTING SENTIMENT ANALYSIS JOB")
        logger.info("=" * 60)

        try:
            from jobs.sentiment_job import run_sentiment_job

            sentiment_summary = await run_sentiment_job()
        except Exception as e:
            logger.error(f"Sentiment job failed: {e}")
            sentiment_summary = {"status": "error", "error": str(e)}

        logger.info("")
        logger.info("=" * 60)
        logger.info("SENTIMENT ANALYSIS SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Status: {sentiment_summary.get('status')}")
        logger.info(
            f"Symbols processed: {sentiment_summary.get('symbols_processed', 0)}"
        )
        if "coverage" in sentiment_summary:
            logger.info(f"Coverage: {sentiment_summary['coverage']}")
        if "averages" in sentiment_summary:
            logger.info(f"Averages: {sentiment_summary['averages']}")

        # Return exit code based on market data success rate
        min_rate = float(os.environ.get("MARKET_DATA_MIN_SUCCESS_RATE", "0"))
        if success_rate >= 90:
            logger.info("JOB COMPLETED SUCCESSFULLY")
            return 0
        elif success_rate >= 70:
            logger.warning("JOB COMPLETED WITH WARNINGS (success rate < 90%)")
            return 0
        elif success_rate > min_rate:
            logger.warning(
                f"JOB COMPLETED WITH DEGRADED RESULTS (success rate {success_rate:.1f}%)"
            )
            return 0
        elif success_rate == 0:
            logger.warning(
                "JOB COMPLETED WITH NO MARKET DATA - "
                "Yahoo Finance may be blocking cloud/CI IP addresses"
            )
            logger.warning(
                "Tip: Set YF_PROXY or HTTPS_PROXY env var to use a proxy, "
                "or set MARKET_DATA_MIN_SUCCESS_RATE to enforce a threshold"
            )
            return 0
        else:
            logger.error(
                f"JOB FAILED (success rate {success_rate:.1f}% "
                f"< minimum {min_rate:.1f}%)"
            )
            return 1

    except Exception as e:
        logger.exception(f"JOB FAILED WITH EXCEPTION: {str(e)}")
        return 1


async def run_quick_update(tickers: list[str] = None):
    """
    Run a quick update for specific tickers or a small sample.
    Useful for testing or on-demand updates.
    """
    if tickers is None:
        # Default to top 10 popular stocks
        tickers = [
            "AAPL",
            "MSFT",
            "GOOGL",
            "AMZN",
            "META",
            "NVDA",
            "TSLA",
            "BRK.B",
            "UNH",
            "JNJ",
        ]

    logger.info(f"Running quick update for {len(tickers)} tickers")

    summary = await run_market_data_update(tickers=tickers, batch_size=10)

    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Market Data Job Runner")
    parser.add_argument("--full", action="store_true", help="Run full daily update")
    parser.add_argument(
        "--quick", action="store_true", help="Run quick update (top 10 stocks)"
    )
    parser.add_argument("--tickers", nargs="+", help="Specific tickers to update")

    args = parser.parse_args()

    if args.full:
        exit_code = asyncio.run(run_daily_market_update())
        sys.exit(exit_code)
    elif args.quick:
        summary = asyncio.run(run_quick_update())
        print(f"Quick update complete: {summary}")
    elif args.tickers:
        summary = asyncio.run(run_quick_update(tickers=args.tickers))
        print(f"Update complete: {summary}")
    else:
        print("Usage:")
        print("  python market_data_job.py --full          # Run full daily update")
        print("  python market_data_job.py --quick         # Run quick update (top 10)")
        print(
            "  python market_data_job.py --tickers AAPL MSFT  # Update specific tickers"
        )
