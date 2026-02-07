"""
Strategy Execution Job

Runs the strategy execution engine for all active agents.
Scheduled after factor scoring and sentiment jobs complete.

Pipeline order:
  1. market_data_job   — fetch prices, fundamentals, technicals
  2. sentiment_job     — analyse news + social sentiment
  3. factor_scoring_job — calculate factor scores + sentiment integration
  4. strategy_execution_job (this) — run strategies, generate positions
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

from core.engine import AgentContext, ExecutionResult, StrategyEngine  # noqa: E402
from core.sentiment_integration import SentimentInput  # noqa: E402
from database import get_supabase_client  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------


async def fetch_active_agents(
    supabase,
) -> list[dict]:
    """Fetch all agents with status='active'."""
    try:
        result = supabase.table("agents").select("*").eq("status", "active").execute()
        return result.data
    except Exception as e:
        logger.error(f"Error fetching active agents: {e}")
        return []


async def fetch_agent_positions(supabase, agent_id: str) -> list[dict]:
    """Fetch open positions for an agent."""
    try:
        result = (
            supabase.table("positions")
            .select("*")
            .eq("agent_id", agent_id)
            .eq("status", "open")
            .execute()
        )
        return result.data
    except Exception as e:
        logger.error(f"Error fetching positions for agent {agent_id}: {e}")
        return []


def _fetch_price_history(supabase, symbols: list[str]) -> dict[str, list[float]]:
    """Fetch price history from the price_history table for all symbols."""
    history: dict[str, list[float]] = {s: [] for s in symbols}

    try:
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


async def fetch_market_and_sentiment(
    supabase,
) -> tuple[dict[str, dict], dict[str, SentimentInput]]:
    """Fetch market data and sentiment for all stocks (shared across agents)."""
    market_data: dict[str, dict] = {}
    sentiment_data: dict[str, SentimentInput] = {}

    try:
        result = supabase.table("stocks").select("*").execute()

        symbols = [r.get("symbol") for r in result.data if r.get("symbol")]
        price_history = _fetch_price_history(supabase, symbols)

        for row in result.data:
            symbol = row.get("symbol")
            if not symbol:
                continue

            market_data[symbol] = {
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
                "sector": row.get("sector"),
            }

            sentiment_data[symbol] = SentimentInput(
                symbol=symbol,
                news_sentiment=row.get("news_sentiment"),
                social_sentiment=row.get("social_sentiment"),
                combined_sentiment=row.get("combined_sentiment"),
                velocity=row.get("sentiment_velocity"),
            )

    except Exception as e:
        logger.error(f"Error fetching market/sentiment data: {e}")

    return market_data, sentiment_data


# ---------------------------------------------------------------------------
# Result persistence
# ---------------------------------------------------------------------------


async def save_execution_result(
    supabase,
    result: ExecutionResult,
) -> bool:
    """Save strategy execution result as agent activity records."""
    if result.error or not result.strategy_output:
        return False

    try:
        output = result.strategy_output

        # Log the execution as an activity event
        supabase.table("agent_activity").insert(
            {
                "agent_id": result.agent_id,
                "activity_type": "rebalance",
                "details": {
                    "strategy": output.strategy_name,
                    "regime": result.regime,
                    "positions_recommended": len(output.positions),
                    "risk_metrics": output.risk_metrics,
                    "executed_at": result.executed_at.isoformat(),
                },
            }
        ).execute()

        # Log each position recommendation
        for pos in output.positions:
            supabase.table("agent_activity").insert(
                {
                    "agent_id": result.agent_id,
                    "activity_type": "signal",
                    "ticker": pos.symbol,
                    "details": {
                        "side": pos.side.value,
                        "target_weight": pos.target_weight,
                        "signal_strength": pos.signal_strength,
                        "integrated_score": result.integrated_scores.get(pos.symbol),
                        "metadata": pos.metadata,
                    },
                }
            ).execute()

        return True

    except Exception as e:
        logger.error(f"Error saving execution result for agent {result.agent_id}: {e}")
        return False


# ---------------------------------------------------------------------------
# Main job
# ---------------------------------------------------------------------------


async def run_strategy_execution_job() -> dict:
    """
    Main entry point for strategy execution job.

    Runs the full strategy pipeline for every active agent.
    """
    logger.info("=" * 60)
    logger.info("STRATEGY EXECUTION JOB STARTED")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)

    start_time = datetime.utcnow()
    supabase = get_supabase_client()

    try:
        # Fetch active agents
        agents = await fetch_active_agents(supabase)
        logger.info(f"Found {len(agents)} active agents")

        if not agents:
            return {
                "status": "success",
                "message": "No active agents to process",
                "agents_processed": 0,
            }

        # Fetch shared market + sentiment data once (avoid N queries)
        logger.info("Fetching market and sentiment data...")
        market_data, sentiment_data = await fetch_market_and_sentiment(supabase)
        logger.info(
            f"Loaded {len(market_data)} stocks, "
            f"{sum(1 for s in sentiment_data.values() if s.combined_sentiment is not None)} with sentiment"
        )

        # Execute strategy for each agent
        engine = StrategyEngine(db_client=supabase)
        results: list[ExecutionResult] = []
        successes = 0
        failures = 0

        for agent in agents:
            agent_id = agent["id"]

            # Build agent context
            positions = await fetch_agent_positions(supabase, agent_id)
            ctx = AgentContext(
                agent_id=agent_id,
                user_id=agent["user_id"],
                strategy_type=agent["strategy_type"],
                strategy_params=agent.get("strategy_params", {}),
                risk_params=agent.get("risk_params", {}),
                allocated_capital=float(agent.get("allocated_capital", 0)),
                current_positions=positions,
            )

            # Run strategy
            result = await engine.execute_for_agent(
                ctx, market_data=market_data, sentiment_data=sentiment_data
            )
            results.append(result)

            # Persist results
            if result.error:
                failures += 1
                logger.warning(
                    f"Agent {agent_id} ({agent.get('name', '?')}): FAILED — {result.error}"
                )
            else:
                saved = await save_execution_result(supabase, result)
                if saved:
                    successes += 1
                else:
                    failures += 1

                pos_count = (
                    len(result.strategy_output.positions)
                    if result.strategy_output
                    else 0
                )
                logger.info(
                    f"Agent {agent_id} ({agent.get('name', '?')}): "
                    f"{pos_count} positions | regime={result.regime}"
                )

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        summary = {
            "status": "success" if failures == 0 else "partial",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": round(duration, 2),
            "agents_total": len(agents),
            "agents_success": successes,
            "agents_failed": failures,
        }

        logger.info("=" * 60)
        logger.info("JOB SUMMARY")
        logger.info("=" * 60)
        for key, value in summary.items():
            logger.info(f"  {key}: {value}")

        return summary

    except Exception as e:
        logger.exception(f"JOB FAILED WITH EXCEPTION: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "duration_seconds": (datetime.utcnow() - start_time).total_seconds(),
        }


if __name__ == "__main__":
    summary = asyncio.run(run_strategy_execution_job())
    print(f"Strategy execution complete: {summary}")
