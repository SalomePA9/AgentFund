"""
Strategy Execution Job

Runs the strategy execution engine for all active agents.
Scheduled after factor scoring, sentiment, and macro data jobs complete.

Pipeline order:
  1. market_data_job   — fetch prices, fundamentals, technicals
  2. sentiment_job     — analyse news + social sentiment
  3. macro_data_job    — FRED, VIX, insider, short interest (uncorrelated signals)
  4. factor_scoring_job — calculate factor scores + sentiment integration
  5. strategy_execution_job (this) — run strategies with macro overlay
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

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
# Order execution
# ---------------------------------------------------------------------------


async def execute_orders(
    supabase,
    result: ExecutionResult,
    agent: dict,
    market_data: dict[str, dict],
) -> tuple[list[dict], Any]:
    """
    Forward actionable OrderActions to the Alpaca broker for execution.

    Only processes "buy" and "sell" actions (new entries and full exits).
    "increase" / "decrease" are converted to the appropriate buy/sell
    quantity delta.  "hold" actions are skipped.

    Returns (order_results, broker) — broker is None if no credentials.
    """
    from core.broker.alpaca_broker import AlpacaBroker, BrokerMode

    # Resolve broker credentials from the agent's owner
    user_id = agent.get("user_id")
    if not user_id:
        logger.warning("Agent %s has no user_id — skipping execution", result.agent_id)
        return [], None

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
        return [], None

    paper = user.get("alpaca_paper_mode", True)
    mode = BrokerMode.PAPER if paper else BrokerMode.LIVE
    broker = AlpacaBroker(api_key, api_secret, mode)

    # Check if market is open before submitting orders
    try:
        clock = broker.is_market_open()
        if not clock.get("is_open", False):
            logger.info(
                "Agent %s: market is closed — deferring orders (next open: %s)",
                result.agent_id,
                clock.get("next_open", "unknown"),
            )
            return [], broker
    except Exception:
        logger.warning(
            "Agent %s: could not check market hours — proceeding cautiously",
            result.agent_id,
        )

    # Get account details — use buying_power for cash awareness
    try:
        account = broker.get_account()
        equity = account.get("equity", 0.0)
        buying_power = account.get("buying_power", 0.0)
    except Exception as e:
        logger.error("Agent %s: failed to get account — %s", result.agent_id, e)
        return [], broker

    if equity <= 0:
        logger.warning("Agent %s: account equity is zero", result.agent_id)
        return [], broker

    # Use the agent's allocated_capital as the sizing basis (not full
    # account equity) so multiple agents sharing one Alpaca account
    # don't over-allocate.  Fall back to equity if not set.
    allocated = float(agent.get("allocated_capital", 0)) or equity
    sizing_basis = min(allocated, equity)

    # Track remaining buying power as we place orders.  Start from the
    # lesser of broker buying_power and allocated capital so we never
    # exceed either constraint.
    remaining_bp = min(buying_power, allocated)

    logger.info(
        "Agent %s: equity=%.2f buying_power=%.2f allocated=%.2f sizing_basis=%.2f",
        result.agent_id,
        equity,
        buying_power,
        allocated,
        sizing_basis,
    )

    order_results: list[dict] = []

    # Process sells first to free up buying power before buys
    sell_actions = [a for a in result.order_actions if a.action in ("sell", "decrease")]
    buy_actions = [a for a in result.order_actions if a.action in ("buy", "increase")]
    hold_actions = [a for a in result.order_actions if a.action == "hold"]

    for action in sell_actions + buy_actions + hold_actions:
        if action.action == "hold":
            continue

        price = (market_data.get(action.symbol) or {}).get("current_price")
        if not price or price <= 0:
            logger.warning("No price for %s — skipping order", action.symbol)
            continue

        try:
            if action.action == "buy":
                notional = action.target_weight * sizing_basis
                # Cap to remaining buying power
                if notional > remaining_bp:
                    logger.info(
                        "Agent %s: capping %s buy from %.2f to %.2f (buying power)",
                        result.agent_id,
                        action.symbol,
                        notional,
                        remaining_bp,
                    )
                    notional = remaining_bp
                qty = int(notional / price)
                if qty <= 0:
                    continue
                # Use limit order at +0.5% for better fill quality
                limit_price = round(price * 1.005, 2)
                order = broker.place_limit_order(
                    action.symbol,
                    qty,
                    "buy",
                    limit_price=limit_price,
                    time_in_force="day",
                )
                remaining_bp -= qty * price
                order_results.append(order)

            elif action.action == "sell":
                # Market order for exits — guaranteed fill
                order = broker.close_position(action.symbol)
                # Reclaim buying power from sell proceeds
                sold_qty = float(order.get("qty") or 0)
                remaining_bp += sold_qty * price
                order_results.append(order)

            elif action.action == "increase":
                delta_weight = action.target_weight - action.current_weight
                if delta_weight <= 0:
                    continue
                notional = delta_weight * sizing_basis
                if notional > remaining_bp:
                    notional = remaining_bp
                qty = int(notional / price)
                if qty <= 0:
                    continue
                limit_price = round(price * 1.005, 2)
                order = broker.place_limit_order(
                    action.symbol,
                    qty,
                    "buy",
                    limit_price=limit_price,
                    time_in_force="day",
                )
                remaining_bp -= qty * price
                order_results.append(order)

            elif action.action == "decrease":
                delta_weight = action.current_weight - action.target_weight
                if delta_weight <= 0:
                    continue
                notional = delta_weight * sizing_basis
                qty = int(notional / price)
                if qty <= 0:
                    continue
                # Limit sell at -0.5% for orderly exit
                limit_price = round(price * 0.995, 2)
                order = broker.place_limit_order(
                    action.symbol,
                    qty,
                    "sell",
                    limit_price=limit_price,
                    time_in_force="day",
                )
                remaining_bp += qty * price
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

    logger.info(
        "Agent %s: submitted %d orders, remaining_bp=%.2f",
        result.agent_id,
        len(order_results),
        remaining_bp,
    )
    return order_results, broker


# ---------------------------------------------------------------------------
# Broker-side protective orders (stop-loss & take-profit)
# ---------------------------------------------------------------------------


def place_bracket_orders(
    broker,
    symbol: str,
    qty: float,
    stop_price: float | None,
    target_price: float | None,
    side: str = "long",
) -> dict[str, str | None]:
    """
    Place server-side stop-loss and take-profit orders at the broker so
    positions are protected between batch runs.

    Returns dict with ``stop_order_id`` and ``tp_order_id`` (or None on failure).
    """
    ids: dict[str, str | None] = {"stop_order_id": None, "tp_order_id": None}

    sell_side = "sell" if side == "long" else "buy"

    # Place GTC stop order
    if stop_price is not None and qty > 0:
        try:
            stop_order = broker.place_stop_order(
                symbol=symbol,
                qty=qty,
                side=sell_side,
                stop_price=round(stop_price, 2),
                time_in_force="gtc",
            )
            ids["stop_order_id"] = stop_order.get("id")
            logger.info(
                "Placed stop order for %s @ %.2f (id=%s)",
                symbol,
                stop_price,
                ids["stop_order_id"],
            )
        except Exception as e:
            logger.error("Failed to place stop order for %s: %s", symbol, e)

    # Place GTC limit order for take-profit
    if target_price is not None and qty > 0:
        try:
            tp_order = broker.place_limit_order(
                symbol=symbol,
                qty=qty,
                side=sell_side,
                limit_price=round(target_price, 2),
                time_in_force="gtc",
            )
            ids["tp_order_id"] = tp_order.get("id")
            logger.info(
                "Placed take-profit order for %s @ %.2f (id=%s)",
                symbol,
                target_price,
                ids["tp_order_id"],
            )
        except Exception as e:
            logger.error("Failed to place take-profit order for %s: %s", symbol, e)

    return ids


# ---------------------------------------------------------------------------
# GTC order cleanup
# ---------------------------------------------------------------------------


def _cancel_gtc_orders(broker, pos_row: dict) -> None:
    """
    Cancel any outstanding broker-side GTC stop and take-profit orders
    for a position that is being exited.  Prevents orphaned orders
    from lingering at the broker after the position is closed.
    """
    if not broker:
        return

    stop_oid = pos_row.get("stop_order_id")
    if stop_oid:
        try:
            broker.cancel_order(stop_oid)
            logger.info("Cancelled GTC stop order %s", stop_oid)
        except Exception:
            logger.debug(
                "Could not cancel stop order %s (may already be filled/cancelled)",
                stop_oid,
            )


# ---------------------------------------------------------------------------
# Position lifecycle management
# ---------------------------------------------------------------------------


async def sync_positions(
    supabase,
    result: ExecutionResult,
    agent: dict,
    order_results: list[dict],
    market_data: dict[str, dict],
    broker=None,
) -> None:
    """
    Create, update, and close position records in the ``positions`` table
    based on executed order actions.

    This bridges the gap between the engine's recommendations and the
    persistent position records that drive stop-loss monitoring, aging,
    and cash tracking.
    """
    agent_id = result.agent_id

    # Build lookup of strategy-recommended positions for metadata
    recommended: dict[str, Any] = {}
    if result.strategy_output:
        for pos in result.strategy_output.positions:
            recommended[pos.symbol] = pos

    # Build lookup of filled order results by symbol for order IDs
    filled_orders: dict[str, dict] = {}
    for o in order_results:
        sym = o.get("symbol")
        if sym and not o.get("error"):
            filled_orders[sym] = o

    for action in result.order_actions:
        sym = action.symbol
        md = market_data.get(sym) or {}
        current_price = md.get("current_price")
        rec = recommended.get(sym)

        try:
            if action.action == "buy":
                # Create a new position record
                order_info = filled_orders.get(sym, {})
                entry_price = order_info.get("filled_avg_price") or current_price
                qty = order_info.get("filled_qty") or order_info.get("qty")

                if not entry_price or not qty:
                    continue

                row = {
                    "agent_id": agent_id,
                    "ticker": sym,
                    "shares": float(qty),
                    "entry_price": float(entry_price),
                    "entry_date": datetime.utcnow().date().isoformat(),
                    "entry_rationale": action.reason,
                    "current_price": float(current_price) if current_price else None,
                    "status": "open",
                    "entry_order_id": order_info.get("id"),
                }

                # Attach stop-loss and take-profit from strategy output
                stop_price = None
                target_price_val = None
                if rec:
                    if rec.stop_loss is not None:
                        stop_price = float(rec.stop_loss)
                        row["stop_loss_price"] = stop_price
                    if rec.take_profit is not None:
                        target_price_val = float(rec.take_profit)
                        row["target_price"] = target_price_val

                # Place broker-side protective orders (GTC stop + take-profit)
                if broker and float(qty) > 0:
                    bracket_ids = place_bracket_orders(
                        broker,
                        symbol=sym,
                        qty=float(qty),
                        stop_price=stop_price,
                        target_price=target_price_val,
                        side=rec.side.value if rec and rec.side else "long",
                    )
                    if bracket_ids.get("stop_order_id"):
                        row["stop_order_id"] = bracket_ids["stop_order_id"]

                supabase.table("positions").insert(row).execute()
                logger.info("Agent %s: created position record for %s", agent_id, sym)

            elif action.action == "sell":
                # Close existing position record(s)
                order_info = filled_orders.get(sym, {})
                exit_price = order_info.get("filled_avg_price") or current_price

                existing = (
                    supabase.table("positions")
                    .select("id, entry_price, shares, stop_order_id")
                    .eq("agent_id", agent_id)
                    .eq("ticker", sym)
                    .eq("status", "open")
                    .execute()
                )

                for pos_row in existing.data:
                    # Cancel broker-side GTC stop/take-profit orders
                    _cancel_gtc_orders(broker, pos_row)

                    update: dict[str, Any] = {
                        "status": "closed",
                        "exit_date": datetime.utcnow().date().isoformat(),
                        "exit_rationale": action.reason,
                        "exit_order_id": order_info.get("id"),
                    }
                    if exit_price:
                        update["exit_price"] = float(exit_price)
                        ep = float(pos_row.get("entry_price") or 0)
                        if ep > 0:
                            pnl = (float(exit_price) - ep) * float(
                                pos_row.get("shares", 0)
                            )
                            pnl_pct = (float(exit_price) - ep) / ep
                            update["realized_pnl"] = round(pnl, 2)
                            update["realized_pnl_pct"] = round(pnl_pct, 4)

                    supabase.table("positions").update(update).eq(
                        "id", pos_row["id"]
                    ).execute()

                logger.info("Agent %s: closed position record for %s", agent_id, sym)

            elif action.action in ("increase", "decrease"):
                # Update shares on the existing open position
                order_info = filled_orders.get(sym, {})
                delta_qty = order_info.get("filled_qty") or order_info.get("qty")
                if not delta_qty:
                    continue

                existing = (
                    supabase.table("positions")
                    .select("id, shares, stop_order_id")
                    .eq("agent_id", agent_id)
                    .eq("ticker", sym)
                    .eq("status", "open")
                    .limit(1)
                    .execute()
                )

                if existing.data:
                    pos_row = existing.data[0]
                    old_shares = float(pos_row.get("shares", 0))
                    if action.action == "increase":
                        new_shares = old_shares + float(delta_qty)
                    else:
                        new_shares = max(0, old_shares - float(delta_qty))

                    update: dict[str, Any] = {"shares": new_shares}

                    # If shares decreased to zero, close the position to
                    # prevent ghost positions from affecting future weight
                    # calculations and portfolio reporting.
                    if new_shares <= 0:
                        _cancel_gtc_orders(broker, pos_row)
                        update["status"] = "closed"
                        update["exit_date"] = datetime.utcnow().date().isoformat()
                        update["exit_rationale"] = action.reason
                        supabase.table("positions").update(update).eq(
                            "id", pos_row["id"]
                        ).execute()
                        continue

                    stop_price = None
                    target_price_val = None
                    if rec and rec.stop_loss is not None:
                        stop_price = float(rec.stop_loss)
                        update["stop_loss_price"] = stop_price
                    if rec and rec.take_profit is not None:
                        target_price_val = float(rec.take_profit)
                        update["target_price"] = target_price_val

                    # Cancel old GTC stop order and place a new one at
                    # the updated quantity so the full position is covered.
                    if broker and new_shares > 0:
                        _cancel_gtc_orders(broker, pos_row)
                        bracket_ids = place_bracket_orders(
                            broker,
                            symbol=sym,
                            qty=new_shares,
                            stop_price=stop_price,
                            target_price=target_price_val,
                            side=rec.side.value if rec and rec.side else "long",
                        )
                        if bracket_ids.get("stop_order_id"):
                            update["stop_order_id"] = bracket_ids["stop_order_id"]

                    supabase.table("positions").update(update).eq(
                        "id", pos_row["id"]
                    ).execute()

        except Exception as e:
            logger.error(
                "Agent %s: failed to sync position for %s — %s",
                agent_id,
                sym,
                e,
            )


# ---------------------------------------------------------------------------
# Cash balance sync
# ---------------------------------------------------------------------------


async def sync_agent_cash_balance(
    supabase,
    agent: dict,
    order_results: list[dict],
    market_data: dict[str, dict],
    result: ExecutionResult,
) -> None:
    """
    Update the agent's ``cash_balance`` in the database based on
    executed buy/sell orders.

    Buys reduce cash, sells increase it.  This keeps the agent
    aware of its available cash for future trades.
    """
    agent_id = agent["id"]
    cash = float(agent.get("cash_balance", 0))

    for action in result.order_actions:
        if action.action == "hold":
            continue

        # Find the matching order result
        order_info = None
        for o in order_results:
            if o.get("symbol") == action.symbol and not o.get("error"):
                order_info = o
                break

        if not order_info:
            continue

        filled_price = float(order_info.get("filled_avg_price") or 0)
        filled_qty = float(order_info.get("filled_qty") or order_info.get("qty") or 0)

        if filled_price <= 0 or filled_qty <= 0:
            # Use market data price estimate if fill info unavailable
            price = (market_data.get(action.symbol) or {}).get("current_price")
            if not price:
                continue
            filled_price = float(price)
            filled_qty = float(order_info.get("qty") or 0)

        trade_value = filled_price * filled_qty

        if action.action in ("buy", "increase"):
            cash -= trade_value
        elif action.action in ("sell", "decrease"):
            cash += trade_value

    # Clamp to zero (shouldn't go negative but guard against it)
    cash = max(0.0, cash)

    try:
        supabase.table("agents").update({"cash_balance": round(cash, 2)}).eq(
            "id", agent_id
        ).execute()

        logger.info(
            "Agent %s: cash_balance updated to %.2f",
            agent_id,
            cash,
        )
    except Exception as e:
        logger.error("Agent %s: failed to sync cash_balance — %s", agent_id, e)


# ---------------------------------------------------------------------------
# Result persistence
# ---------------------------------------------------------------------------


async def save_execution_result(
    supabase,
    result: ExecutionResult,
) -> bool:
    """Save strategy execution result as agent activity records."""
    if result.error:
        return False

    # Allow circuit breaker results (strategy_output=None but order_actions present)
    has_actions = bool(result.order_actions)
    if not result.strategy_output and not has_actions:
        return False

    try:
        output = result.strategy_output

        # Log the execution as an activity event
        if output:
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
        elif result.regime == "circuit_breaker":
            supabase.table("agent_activity").insert(
                {
                    "agent_id": result.agent_id,
                    "activity_type": "rebalance",
                    "details": {
                        "regime": "circuit_breaker",
                        "liquidation": True,
                        "positions_liquidated": len(result.order_actions),
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


async def _fetch_macro_overlay_data(
    supabase,
) -> tuple[dict, dict, dict, dict]:
    """
    Fetch the latest macro and alternative data for the MacroRiskOverlay.

    Reads the most recent values from the macro_indicators, insider_signals,
    and short_interest tables populated by macro_data_job.  Also fetches
    fresh VIX data directly (fast, free, no API key).

    Returns (macro_data, insider_data, vol_regime_data, short_interest_data).
    """
    from config import settings

    macro_data: dict = {}
    insider_data: dict = {}
    vol_regime_data: dict = {}
    short_interest_data: dict = {}

    if not settings.macro_overlay_enabled:
        logger.info("Macro overlay disabled — skipping macro data fetch")
        return macro_data, insider_data, vol_regime_data, short_interest_data

    # Fetch FRED macro indicators from DB (populated by macro_data_job)
    try:
        result = (
            supabase.table("macro_indicators")
            .select("*")
            .order("recorded_at", desc=True)
            .limit(10)
            .execute()
        )
        for row in result.data:
            name = row.get("indicator_name")
            if name and name not in macro_data:
                macro_data[name] = {
                    "current": float(row["value"]) if row.get("value") else None,
                    "z_score": float(row["z_score"]) if row.get("z_score") else 0.0,
                    "percentile": (
                        float(row["percentile"]) if row.get("percentile") else 50.0
                    ),
                    "rate_of_change": (
                        float(row["rate_of_change"])
                        if row.get("rate_of_change")
                        else 0.0
                    ),
                }
        logger.info("Loaded %d macro indicators from DB", len(macro_data))
    except Exception:
        logger.warning(
            "Failed to fetch macro indicators — overlay will be partial", exc_info=True
        )

    # Fetch VIX data (fast, always fresh)
    try:
        from data.macro.volatility_regime import VolatilityRegimeClient

        vol_client = VolatilityRegimeClient()
        vol_regime_data = await vol_client.fetch_regime(lookback_days=60)
        logger.info(
            "VIX regime: %s (score=%.2f)",
            vol_regime_data.get("regime_label"),
            vol_regime_data.get("regime_score", 0),
        )
    except Exception:
        logger.warning("Failed to fetch VIX data", exc_info=True)

    # Fetch insider signals from DB
    try:
        result = (
            supabase.table("insider_signals")
            .select("symbol, net_sentiment, cluster_score, buy_ratio, filing_count")
            .order("recorded_at", desc=True)
            .limit(500)
            .execute()
        )
        seen = set()
        for row in result.data:
            sym = row.get("symbol")
            if sym and sym not in seen:
                seen.add(sym)
                insider_data[sym] = {
                    "net_sentiment": (
                        float(row["net_sentiment"]) if row.get("net_sentiment") else 0
                    ),
                    "cluster_score": (
                        float(row["cluster_score"]) if row.get("cluster_score") else 0
                    ),
                    "buy_ratio": (
                        float(row["buy_ratio"]) if row.get("buy_ratio") else 0.5
                    ),
                    "filing_count": row.get("filing_count", 0),
                }
        logger.info("Loaded insider signals for %d symbols", len(insider_data))
    except Exception:
        logger.warning("Failed to fetch insider signals", exc_info=True)

    # Fetch short interest from DB
    try:
        result = (
            supabase.table("short_interest")
            .select("symbol, short_pct_float, short_ratio, short_interest_score")
            .order("recorded_at", desc=True)
            .limit(500)
            .execute()
        )
        seen = set()
        for row in result.data:
            sym = row.get("symbol")
            if sym and sym not in seen:
                seen.add(sym)
                short_interest_data[sym] = {
                    "short_pct_float": (
                        float(row["short_pct_float"])
                        if row.get("short_pct_float")
                        else None
                    ),
                    "short_ratio": (
                        float(row["short_ratio"]) if row.get("short_ratio") else None
                    ),
                    "short_interest_score": (
                        float(row["short_interest_score"])
                        if row.get("short_interest_score")
                        else 0
                    ),
                }
        logger.info("Loaded short interest for %d symbols", len(short_interest_data))
    except Exception:
        logger.warning("Failed to fetch short interest", exc_info=True)

    return macro_data, insider_data, vol_regime_data, short_interest_data


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

        # Fetch macro + alternative data for the MacroRiskOverlay
        # These are pre-fetched once and shared across all agents.
        macro_data, insider_data, vol_regime_data, short_interest_data = (
            await _fetch_macro_overlay_data(supabase)
        )

        # Pre-compute MacroRiskOverlay once (deterministic for all agents)
        from core.macro_risk_overlay import MacroRiskOverlay

        pre_overlay = None
        try:
            overlay = MacroRiskOverlay()
            pre_overlay = overlay.compute(
                macro_data=macro_data,
                insider_data=insider_data,
                vol_regime_data=vol_regime_data,
            )
            logger.info(
                "Pre-computed overlay: scale=%.2f regime=%s",
                pre_overlay.risk_scale_factor,
                pre_overlay.regime_label,
            )
        except Exception:
            logger.warning("Failed to pre-compute overlay", exc_info=True)

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
                cash_balance=float(agent.get("cash_balance", 0)),
                current_positions=positions,
            )

            # Run strategy with macro overlay data
            result = await engine.execute_for_agent(
                ctx,
                market_data=market_data,
                sentiment_data=sentiment_data,
                macro_data=macro_data,
                insider_data=insider_data,
                vol_regime_data=vol_regime_data,
                short_interest_data=short_interest_data,
                pre_computed_overlay=pre_overlay,
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
                orders, broker = await execute_orders(
                    supabase, result, agent, market_data
                )

                # Sync position records (create/update/close in DB)
                # and place broker-side protective orders for new buys
                await sync_positions(
                    supabase,
                    result,
                    agent,
                    orders,
                    market_data,
                    broker=broker,
                )

                # Update agent's cash_balance based on executed trades
                await sync_agent_cash_balance(
                    supabase, agent, orders, market_data, result
                )

                if saved:
                    successes += 1
                else:
                    failures += 1

                pos_count = (
                    len(result.strategy_output.positions)
                    if result.strategy_output
                    else 0
                )
                overlay_info = ""
                if result.macro_overlay:
                    overlay_info = (
                        f" | macro_scale={result.macro_overlay.risk_scale_factor:.2f}"
                        f" macro_regime={result.macro_overlay.regime_label}"
                    )
                logger.info(
                    f"Agent {agent_id} ({agent.get('name', '?')}): "
                    f"{pos_count} positions, {len(orders)} orders | "
                    f"regime={result.regime}{overlay_info}"
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
