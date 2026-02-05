"""
Factor Scoring Job

Calculates factor scores (0-100) for all stocks after market data update.
Runs as part of the nightly job pipeline.
"""

import asyncio
import logging
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, "/home/user/AgentFund/backend")

from core.factors import FactorCalculator, FactorScores
from database import supabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

logger = logging.getLogger(__name__)


async def fetch_all_stock_data() -> dict[str, dict]:
    """Fetch all stock data from database for factor calculation."""
    try:
        result = supabase.table("stocks").select("*").execute()

        # Convert to dict keyed by symbol
        stock_data = {}
        for row in result.data:
            symbol = row.get("symbol")
            if not symbol:
                continue

            # Map database columns to factor calculator expected format
            stock_data[symbol] = {
                "current_price": row.get("price"),
                "price_history": [],  # Would need to fetch from price_history table
                "pe_ratio": row.get("pe_ratio"),
                "pb_ratio": row.get("pb_ratio"),
                "roe": row.get("roe"),
                "profit_margin": row.get("profit_margin"),
                "debt_to_equity": row.get("debt_to_equity"),
                "dividend_yield": row.get("dividend_yield"),
                "dividend_growth_5y": row.get("dividend_growth_5y"),
                "ma_30": row.get("ma_30"),
                "ma_100": row.get("ma_100"),
                "ma_200": row.get("ma_200"),
                "atr": row.get("atr"),
                "momentum_6m": row.get("momentum_6m"),
                "momentum_12m": row.get("momentum_12m"),
                "sector": row.get("sector"),
            }

        return stock_data

    except Exception as e:
        logger.error(f"Error fetching stock data: {str(e)}")
        return {}


async def fetch_sectors() -> dict[str, str]:
    """Fetch sector mapping for all stocks."""
    try:
        result = supabase.table("stocks").select("symbol, sector").execute()
        return {row["symbol"]: row.get("sector", "Unknown") for row in result.data}
    except Exception as e:
        logger.error(f"Error fetching sectors: {str(e)}")
        return {}


async def update_factor_scores(scores: dict[str, FactorScores]) -> tuple[int, int]:
    """
    Update factor scores in database.

    Returns:
        Tuple of (success_count, failure_count)
    """
    success = 0
    failures = 0

    # Process in batches
    batch_size = 100
    symbols = list(scores.keys())

    for i in range(0, len(symbols), batch_size):
        batch_symbols = symbols[i:i + batch_size]
        batch_data = []

        for symbol in batch_symbols:
            score = scores[symbol]
            batch_data.append({
                "symbol": symbol,
                "momentum_score": score.momentum_score,
                "value_score": score.value_score,
                "quality_score": score.quality_score,
                "dividend_score": score.dividend_score,
                "volatility_score": score.volatility_score,
                "composite_score": score.composite_score,
            })

        try:
            # Update stocks table with factor scores
            for data in batch_data:
                supabase.table("stocks").update({
                    "momentum_score": data["momentum_score"],
                    "value_score": data["value_score"],
                    "quality_score": data["quality_score"],
                    "dividend_score": data["dividend_score"],
                    "volatility_score": data["volatility_score"],
                    "composite_score": data["composite_score"],
                    "scores_updated_at": datetime.utcnow().isoformat(),
                }).eq("symbol", data["symbol"]).execute()

            success += len(batch_data)

        except Exception as e:
            logger.error(f"Error updating factor scores batch: {str(e)}")
            failures += len(batch_data)

    return success, failures


async def run_factor_scoring_job() -> dict:
    """
    Main entry point for factor scoring job.

    Returns:
        Job summary dictionary
    """
    logger.info("=" * 60)
    logger.info("FACTOR SCORING JOB STARTED")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)

    start_time = datetime.utcnow()

    try:
        # Fetch all stock data
        logger.info("Fetching stock data from database...")
        stock_data = await fetch_all_stock_data()
        logger.info(f"Fetched {len(stock_data)} stocks")

        if not stock_data:
            logger.warning("No stock data found")
            return {
                "status": "warning",
                "message": "No stock data found",
                "stocks_processed": 0,
            }

        # Fetch sector mapping
        sectors = await fetch_sectors()
        logger.info(f"Fetched {len(sectors)} sector mappings")

        # Calculate factor scores
        logger.info("Calculating factor scores...")
        calculator = FactorCalculator(sector_aware=True)
        scores = calculator.calculate_all(stock_data, sectors)
        logger.info(f"Calculated scores for {len(scores)} stocks")

        # Update database
        logger.info("Updating factor scores in database...")
        success, failures = await update_factor_scores(scores)
        logger.info(f"Database update: {success} success, {failures} failures")

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        summary = {
            "status": "success" if failures == 0 else "partial",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": round(duration, 2),
            "stocks_fetched": len(stock_data),
            "scores_calculated": len(scores),
            "db_success": success,
            "db_failures": failures,
        }

        logger.info("=" * 60)
        logger.info("JOB SUMMARY")
        logger.info("=" * 60)
        for key, value in summary.items():
            logger.info(f"{key}: {value}")

        return summary

    except Exception as e:
        logger.exception(f"JOB FAILED WITH EXCEPTION: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
        }


if __name__ == "__main__":
    summary = asyncio.run(run_factor_scoring_job())
    print(f"Factor scoring complete: {summary}")
