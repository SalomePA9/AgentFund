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

from core.engine import (
    AgentContext,
    ExecutionResult,
    OrderAction,
    StrategyEngine,
)  # noqa: E402
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
# Order execution
# ---------------------------------------------------------------------------


async def execute_orders(
    supabase,
    result: ExecutionResult,
    agent: dict,
    market_data: dict[str, dict],
) -> list[dict]:
    """
    Forward actionable OrderActions to the Alpaca broker for execution.

    Only processes "buy" and "sell" actions (new entries and full exits).
    "increase" / "decrease" are converted to the appropriate buy/sell
    quantity delta.  "hold" actions are skipped.

    Returns a list of order result dicts (or errors).
    """
    from core.broker.alpaca_broker import AlpacaBroker, BrokerMode

    # Resolve broker credentials from the agent's owner
    user_id = agent.get("user_id")
    if not user_id:
        logger.warning("Agent %s has no user_id — skipping execution", result.agent_id)
        return []

    user_result = (
        supabase.table("users")
        .select("alpaca_api_key, alpaca_api_secret, alpaca_paper_mode")
        .eq("id", user_id)
        .single()
        .execute()
    )
    user = user_result.data
    api_key = user.get("alpaca_api_key")
    api_secret = user.get("alpaca_api_secret")

    if not api_key or not api_secret:
        logger.info(
            "Agent %s: user has no Alpaca credentials — logging only",
            result.agent_id,
        )
        return []

    paper = user.get("alpaca_paper_mode", True)
    mode = BrokerMode.PAPER if paper else BrokerMode.LIVE
    broker = AlpacaBroker(api_key, api_secret, mode)

    # Get account equity to convert weights → share counts
    try:
        account = broker.get_account()
        equity = account.get("equity", 0.0)
    except Exception as e:
        logger.error("Agent %s: failed to get account — %s", result.agent_id, e)
        return []

    if equity <= 0:
        logger.warning("Agent %s: account equity is zero", result.agent_id)
        return []

    order_results: list[dict] = []

    for action in result.order_actions:
        if action.action == "hold":
            continue

        price = (market_data.get(action.symbol) or {}).get("current_price")
        if not price or price <= 0:
            logger.warning("No price for %s — skipping order", action.symbol)
            continue

        try:
            if action.action == "buy":
                # New position: target_weight * equity / price = shares
                notional = action.target_weight * equity
                qty = int(notional / price)
                if qty <= 0:
                    continue
                order = broker.place_market_order(action.symbol, qty, "buy")
                order_results.append(order)

            elif action.action == "sell":
                # Full exit
                order = broker.close_position(action.symbol)
                order_results.append(order)

            elif action.action == "increase":
                delta_weight = action.target_weight - action.current_weight
                if delta_weight <= 0:
                    continue
                notional = delta_weight * equity
                qty = int(notional / price)
                if qty <= 0:
                    continue
                order = broker.place_market_order(action.symbol, qty, "buy")
                order_results.append(order)

            elif action.action == "decrease":
                delta_weight = action.current_weight - action.target_weight
                if delta_weight <= 0:
                    continue
                notional = delta_weight * equity
                qty = int(notional / price)
                if qty <= 0:
                    continue
                order = broker.place_market_order(action.symbol, qty, "sell")
                order_results.append(order)

        except Exception as e:
            logger.error(
                "Agent %s: order for %s (%s) failed — %s",
                result.agent_id,
                action.symbol,
                action.action,
                e,
            )
            order_results.append(
                {"symbol": action.symbol, "action": action.action, "error": str(e)}
            )

    logger.info("Agent %s: submitted %d orders", result.agent_id, len(order_results))
    return order_results


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

        # Log each order action (buy/sell/hold/increase/decrease)
        for action in result.order_actions:
            activity_type = "signal"
            if action.action in ("buy", "increase"):
                activity_type = "buy"
            elif action.action in ("sell", "decrease"):
                activity_type = "sell"

            supabase.table("agent_activity").insert(
                {
                    "agent_id": result.agent_id,
                    "activity_type": activity_type,
                    "ticker": action.symbol,
                    "details": {
                        "order_action": action.action,
                        "target_weight": action.target_weight,
                        "current_weight": action.current_weight,
                        "signal_strength": action.signal_strength,
                        "integrated_score": result.integrated_scores.get(action.symbol),
                        "reason": action.reason,
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

            # Persist results and execute orders
            if result.error:
                failures += 1
                logger.warning(
                    f"Agent {agent_id} ({agent.get('name', '?')}): FAILED — {result.error}"
                )
            else:
                saved = await save_execution_result(supabase, result)

                # Forward actionable orders to broker
                orders = await execute_orders(supabase, result, agent, market_data)

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
                    f"{pos_count} positions, {len(orders)} orders | regime={result.regime}"
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
