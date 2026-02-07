"""
Factor Scoring Job

Calculates factor scores (0-100) for all stocks after market data update.
Runs as part of the nightly job pipeline.
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

from core.factors import FactorCalculator, FactorScores  # noqa: E402
from core.sentiment_integration import (  # noqa: E402
    SentimentFactorIntegrator,
    SentimentInput,
    TemporalSentimentAnalyzer,
)
from database import get_supabase_client  # noqa: E402

# Get database client
supabase = get_supabase_client()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


def _fetch_price_history(symbols: list[str]) -> dict[str, list[float]]:
    """Fetch price history from the price_history table for all symbols.

    Returns:
        Dict of symbol -> list of closing prices (oldest to newest).
    """
    history: dict[str, list[float]] = {s: [] for s in symbols}

    try:
        # Fetch the last 252 trading days (~1 year) for momentum calculations
        result = (
            supabase.table("price_history")
            .select("symbol, date, price")
            .in_("symbol", symbols)
            .order("date", desc=False)
            .execute()
        )

        for row in result.data:
            sym = row.get("symbol")
            price = row.get("price")
            if sym and price is not None:
                history[sym].append(float(price))

    except Exception as e:
        logger.error(f"Error fetching price history: {e}")

    loaded = sum(1 for v in history.values() if v)
    logger.info("Loaded price history for %d/%d symbols", loaded, len(symbols))
    return history


async def fetch_all_stock_data() -> tuple[dict[str, dict], dict[str, SentimentInput]]:
    """Fetch all stock data and sentiment from database for factor calculation.

    Returns:
        Tuple of (market_data dict, sentiment_data dict).
    """
    stock_data: dict[str, dict] = {}
    sentiment_data: dict[str, SentimentInput] = {}

    try:
        result = supabase.table("stocks").select("*").execute()

        symbols = [r.get("symbol") for r in result.data if r.get("symbol")]
        price_history = _fetch_price_history(symbols)

        for row in result.data:
            symbol = row.get("symbol")
            if not symbol:
                continue

            # Map database columns to factor calculator expected format
            stock_data[symbol] = {
                "current_price": row.get("price"),
                "price_history": price_history.get(symbol, []),
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

            # Extract sentiment columns (already populated by sentiment_job)
            sentiment_data[symbol] = SentimentInput(
                symbol=symbol,
                news_sentiment=row.get("news_sentiment"),
                social_sentiment=row.get("social_sentiment"),
                combined_sentiment=row.get("combined_sentiment"),
                velocity=row.get("sentiment_velocity"),
            )

        return stock_data, sentiment_data

    except Exception as e:
        logger.error(f"Error fetching stock data: {str(e)}")
        return {}, {}


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
        batch_symbols = symbols[i : i + batch_size]
        batch_data = []

        for symbol in batch_symbols:
            score = scores[symbol]
            batch_data.append(
                {
                    "symbol": symbol,
                    "momentum_score": score.momentum_score,
                    "value_score": score.value_score,
                    "quality_score": score.quality_score,
                    "dividend_score": score.dividend_score,
                    "volatility_score": score.volatility_score,
                    "composite_score": score.composite_score,
                    "sentiment_score": score.sentiment_score,
                    "integrated_composite": score.integrated_composite,
                }
            )

        try:
            # Update stocks table with factor + integrated scores
            for data in batch_data:
                update_payload: dict[str, object] = {
                    "momentum_score": data["momentum_score"],
                    "value_score": data["value_score"],
                    "quality_score": data["quality_score"],
                    "dividend_score": data["dividend_score"],
                    "volatility_score": data["volatility_score"],
                    "composite_score": data["composite_score"],
                    "scores_updated_at": datetime.utcnow().isoformat(),
                }
                if data.get("sentiment_score") is not None:
                    update_payload["sentiment_score"] = data["sentiment_score"]
                if data.get("integrated_composite") is not None:
                    update_payload["integrated_composite"] = data[
                        "integrated_composite"
                    ]
                supabase.table("stocks").update(update_payload).eq(
                    "symbol", data["symbol"]
                ).execute()

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
        # Fetch all stock data (now includes sentiment)
        logger.info("Fetching stock data from database...")
        stock_data, sentiment_data = await fetch_all_stock_data()
        logger.info(
            f"Fetched {len(stock_data)} stocks, "
            f"{sum(1 for s in sentiment_data.values() if s.combined_sentiment is not None)} with sentiment"
        )

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

        # Calculate base factor scores
        logger.info("Calculating factor scores...")
        calculator = FactorCalculator(sector_aware=True)
        scores = calculator.calculate_all(stock_data, sectors)
        logger.info(f"Calculated base scores for {len(scores)} stocks")

        # Run sentiment-factor integration for each strategy type
        logger.info("Running sentiment-factor integration...")
        strategy_types = [
            "momentum",
            "quality_value",
            "quality_momentum",
            "dividend_growth",
        ]

        # Build factor_data dict from calculated scores
        factor_data: dict[str, dict[str, float]] = {}
        for symbol, fs in scores.items():
            factor_data[symbol] = {
                "momentum_score": fs.momentum_score,
                "value_score": fs.value_score,
                "quality_score": fs.quality_score,
                "dividend_score": fs.dividend_score,
                "volatility_score": fs.volatility_score,
            }

        # Enrich sentiment with temporal features from sentiment_history
        logger.info("Enriching sentiment with temporal history...")
        temporal_analyzer = TemporalSentimentAnalyzer(db_client=supabase)
        sentiment_data = await temporal_analyzer.enrich(
            sentiment_data, lookback_days=30
        )

        # Use momentum strategy as the default integrated composite
        # (agents override with their own strategy_type at execution time)
        integrator = SentimentFactorIntegrator(strategy_type="momentum")
        integrated = integrator.integrate(
            factor_data, sentiment_data, market_data=stock_data
        )

        # Merge integrated scores back into FactorScores
        for symbol, iscore in integrated.items():
            if symbol in scores:
                scores[symbol].sentiment_score = iscore.sentiment_score
                scores[symbol].integrated_composite = iscore.composite_score

        logger.info(f"Integrated sentiment for {len(integrated)} stocks")

        # Update database
        logger.info("Updating factor scores in database...")
        success, failures = await update_factor_scores(scores)
        logger.info(f"Database update: {success} success, {failures} failures")

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        sentiment_count = sum(
            1 for s in sentiment_data.values() if s.combined_sentiment is not None
        )

        summary = {
            "status": "success" if failures == 0 else "partial",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": round(duration, 2),
            "stocks_fetched": len(stock_data),
            "scores_calculated": len(scores),
            "sentiment_integrated": sentiment_count,
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
