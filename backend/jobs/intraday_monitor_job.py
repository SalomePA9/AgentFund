"""
Intraday Position Monitor Job

Runs on a frequent schedule (e.g. every 5-15 minutes) during market hours
to give agents the ability to react to intraday price movements.

Responsibilities:
  - Check stop-loss breaches against live broker prices
  - Check take-profit targets reached
  - Enforce position aging / time horizon limits
  - Execute exits immediately when triggered

Unlike strategy_execution_job (which runs the full strategy pipeline once
per rebalance period), this job is a lightweight monitor that only examines
existing positions and acts on predefined exit criteria.  It enables
agents to trade at multiple points throughout the day.
"""

import asyncio
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any  # noqa: F401

# Add parent directory to path for imports when running as script
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from database import get_supabase_client  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_broker_for_user(supabase, user_id: str):
    """Create an Alpaca broker instance for a user, or None."""
    from core.broker.alpaca_broker import AlpacaBroker, BrokerMode

    try:
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
            return None

        paper = user.get("alpaca_paper_mode", True)
        mode = BrokerMode.PAPER if paper else BrokerMode.LIVE
        return AlpacaBroker(api_key, api_secret, mode)
    except Exception as e:
        logger.error("Failed to create broker for user %s: %s", user_id, e)
        return None


def _check_market_open(broker) -> bool:
    """Return True if US equity market is currently open."""
    try:
        clock = broker.is_market_open()
        return clock.get("is_open", False)
    except Exception:
        logger.warning("Failed to check market hours — assuming open")
        return True


# ---------------------------------------------------------------------------
# Position checks
# ---------------------------------------------------------------------------


def check_stop_loss(pos: dict, live_price: float) -> str | None:
    """Return exit reason if stop-loss breached, else None."""
    stop = pos.get("stop_loss_price")
    if stop is None:
        return None

    stop = float(stop)
    side = pos.get("side", "long")

    if side == "long" and live_price <= stop:
        return f"Intraday stop-loss breached: price {live_price:.2f} <= stop {stop:.2f}"
    if side == "short" and live_price >= stop:
        return f"Intraday stop-loss breached: price {live_price:.2f} >= stop {stop:.2f}"
    return None


def check_take_profit(pos: dict, live_price: float) -> str | None:
    """Return exit reason if take-profit reached, else None."""
    target = pos.get("target_price")
    if target is None:
        return None

    target = float(target)
    side = pos.get("side", "long")

    if side == "long" and live_price >= target:
        return (
            f"Intraday take-profit reached: price {live_price:.2f} >= "
            f"target {target:.2f}"
        )
    if side == "short" and live_price <= target:
        return (
            f"Intraday take-profit reached: price {live_price:.2f} <= "
            f"target {target:.2f}"
        )
    return None


def check_position_age(pos: dict, max_holding_days: int | None) -> str | None:
    """Return exit reason if the position exceeds its time horizon."""
    if not max_holding_days:
        return None

    entry_date_str = pos.get("entry_date")
    if not entry_date_str:
        return None

    try:
        entry_date = (
            date.fromisoformat(entry_date_str)
            if isinstance(entry_date_str, str)
            else entry_date_str
        )
        days_held = (date.today() - entry_date).days
        if days_held >= max_holding_days:
            return (
                f"Position aged out: held {days_held}d, "
                f"max horizon {max_holding_days}d"
            )
    except (ValueError, TypeError):
        pass

    return None


# ---------------------------------------------------------------------------
# Exit execution
# ---------------------------------------------------------------------------


async def execute_exit(
    supabase,
    broker,
    pos: dict,
    reason: str,
    live_price: float | None,
) -> bool:
    """
    Close a position at the broker and update the DB record.

    Returns True on success.
    """
    sym = pos.get("ticker", pos.get("symbol", ""))
    agent_id = pos.get("agent_id")

    try:
        # Cancel outstanding GTC stop/take-profit orders before closing
        stop_oid = pos.get("stop_order_id")
        if stop_oid:
            try:
                broker.cancel_order(stop_oid)
                logger.info("Cancelled GTC stop order %s for %s", stop_oid, sym)
            except Exception:
                logger.debug(
                    "Could not cancel stop order %s (may already be filled/cancelled)",
                    stop_oid,
                )

        # Close at broker
        order = broker.close_position(sym)
        exit_price = live_price or float(order.get("filled_avg_price") or 0)

        # Update position record
        entry_price = float(pos.get("entry_price", 0))
        shares = float(pos.get("shares", 0))
        pnl = (exit_price - entry_price) * shares if entry_price > 0 else 0
        pnl_pct = (exit_price - entry_price) / entry_price if entry_price > 0 else 0

        supabase.table("positions").update(
            {
                "status": "closed",
                "exit_price": exit_price,
                "exit_date": date.today().isoformat(),
                "exit_rationale": reason,
                "exit_order_id": order.get("id"),
                "realized_pnl": round(pnl, 2),
                "realized_pnl_pct": round(pnl_pct, 4),
            }
        ).eq("id", pos["id"]).execute()

        # Log activity
        activity_type = "stop_hit" if "stop-loss" in reason else "target_hit"
        if "aged out" in reason:
            activity_type = "sell"

        supabase.table("agent_activity").insert(
            {
                "agent_id": agent_id,
                "activity_type": activity_type,
                "ticker": sym,
                "details": {
                    "reason": reason,
                    "exit_price": exit_price,
                    "realized_pnl": round(pnl, 2),
                    "realized_pnl_pct": round(pnl_pct, 4),
                },
            }
        ).execute()

        logger.info(
            "Agent %s: exited %s — %s (P&L: %.2f)",
            agent_id,
            sym,
            reason,
            pnl,
        )
        return True

    except Exception as e:
        logger.error(
            "Agent %s: failed to exit %s — %s",
            agent_id,
            sym,
            e,
        )
        return False


# ---------------------------------------------------------------------------
# Main job
# ---------------------------------------------------------------------------


async def run_intraday_monitor() -> dict:
    """
    Main entry point for the intraday position monitor.

    Scans all open positions across active agents, fetches live prices
    from the broker, and exits positions that have hit stops, targets,
    or time horizons.
    """
    logger.info("=" * 60)
    logger.info("INTRADAY MONITOR STARTED")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)

    start_time = datetime.utcnow()
    supabase = get_supabase_client()

    exits_triggered = 0
    positions_scanned = 0

    try:
        # Fetch all active agents grouped by user for broker reuse
        agents = (
            supabase.table("agents")
            .select("id, user_id, strategy_params, risk_params")
            .eq("status", "active")
            .execute()
        ).data

        if not agents:
            return {
                "status": "success",
                "message": "No active agents",
                "positions_scanned": 0,
                "exits_triggered": 0,
            }

        # Group agents by user_id to reuse broker connections
        user_agents: dict[str, list[dict]] = {}
        for ag in agents:
            uid = ag.get("user_id")
            if uid:
                user_agents.setdefault(uid, []).append(ag)

        for user_id, user_agent_list in user_agents.items():
            broker = _get_broker_for_user(supabase, user_id)
            if not broker:
                continue

            # Check market hours — skip if market is closed
            if not _check_market_open(broker):
                logger.info("Market closed — skipping monitor for user %s", user_id)
                continue

            for ag in user_agent_list:
                agent_id = ag["id"]
                max_holding_days = ag.get("strategy_params", {}).get(
                    "max_holding_days"
                ) or ag.get("risk_params", {}).get("max_holding_days")

                # Fetch open positions for this agent
                positions = (
                    supabase.table("positions")
                    .select("*")
                    .eq("agent_id", agent_id)
                    .eq("status", "open")
                    .execute()
                ).data

                for pos in positions:
                    positions_scanned += 1
                    sym = pos.get("ticker", "")
                    if not sym:
                        continue

                    # Get live price from broker
                    try:
                        quote = broker.get_latest_quote(sym)
                        live_price = (
                            quote.get("ask_price") or quote.get("bid_price") or 0
                        )
                    except Exception:
                        logger.warning("Could not get live price for %s", sym)
                        continue

                    if live_price <= 0:
                        continue

                    # Update current_price in DB for dashboard visibility
                    try:
                        supabase.table("positions").update(
                            {"current_price": live_price}
                        ).eq("id", pos["id"]).execute()
                    except Exception:
                        logger.debug("Failed to update current_price for position %s", pos.get("id"))

                    # Check exit conditions in priority order
                    reason = check_stop_loss(pos, live_price)
                    if not reason:
                        reason = check_take_profit(pos, live_price)
                    if not reason:
                        reason = check_position_age(pos, max_holding_days)

                    if reason:
                        success = await execute_exit(
                            supabase, broker, pos, reason, live_price
                        )
                        if success:
                            exits_triggered += 1

        duration = (datetime.utcnow() - start_time).total_seconds()

        summary = {
            "status": "success",
            "timestamp": start_time.isoformat(),
            "duration_seconds": round(duration, 2),
            "positions_scanned": positions_scanned,
            "exits_triggered": exits_triggered,
        }

        logger.info("=" * 60)
        logger.info("INTRADAY MONITOR SUMMARY")
        for k, v in summary.items():
            logger.info("  %s: %s", k, v)

        return summary

    except Exception as e:
        logger.exception(f"INTRADAY MONITOR FAILED: {e}")
        return {
            "status": "error",
            "error": str(e),
            "positions_scanned": positions_scanned,
            "exits_triggered": exits_triggered,
        }


if __name__ == "__main__":
    summary = asyncio.run(run_intraday_monitor())
    print(f"Intraday monitor complete: {summary}")
