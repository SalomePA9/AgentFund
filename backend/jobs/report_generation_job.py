"""
Report Generation Job

Generates daily reports for all active agents using the LLM report generator.
Runs as the final step of the nightly pipeline after strategy execution.

Pipeline order:
  1. market_data_job       — fetch prices, fundamentals, technicals
  2. sentiment_job         — analyse news + social sentiment
  3. macro_data_job        — FRED, VIX, insider, short interest
  4. factor_scoring_job    — calculate factor scores + sentiment integration
  5. strategy_execution_job — run strategies with macro overlay
  6. report_generation_job (this) — generate LLM reports for all active agents
"""

import asyncio
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# Add parent directory to path for imports when running as script
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from database import get_supabase_client  # noqa: E402
from llm import AgentContext, get_report_generator  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def _fetch_macro_overlay_data(db) -> dict:
    """Fetch the latest macro risk overlay state from the database."""
    macro_data: dict = {}

    try:
        overlay_result = (
            db.table("macro_risk_overlay_state")
            .select("*")
            .order("computed_at", desc=True)
            .limit(1)
            .execute()
        )
        if overlay_result.data:
            row = overlay_result.data[0]
            macro_data["regime"] = row.get("regime_label")
            macro_data["scale_factor"] = row.get("risk_scale_factor")
            macro_data["composite_score"] = row.get("composite_risk_score")
            macro_data["warnings"] = row.get("warnings") or []
            macro_data["contributions"] = {
                "credit_spread": row.get("credit_spread_signal"),
                "yield_curve": row.get("yield_curve_signal"),
                "vol_regime": row.get("vol_regime_signal"),
                "seasonality": row.get("seasonality_signal"),
                "insider_breadth": row.get("insider_breadth_signal"),
            }
    except Exception:
        logger.debug("macro_risk_overlay_state table not available", exc_info=True)

    return macro_data


def _build_agent_context(agent: dict, db, report_date: date) -> AgentContext:
    """Build agent context for report generation."""
    agent_id = agent["id"]

    # Get open positions
    positions_result = (
        db.table("positions")
        .select(
            "ticker, shares, entry_price, current_price, unrealized_pnl, unrealized_pnl_pct"
        )
        .eq("agent_id", agent_id)
        .eq("status", "open")
        .execute()
    )

    # Get recent activity
    activity_result = (
        db.table("agent_activity")
        .select("activity_type, ticker, details, created_at")
        .eq("agent_id", agent_id)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )

    # Calculate metrics
    total_value = float(agent.get("total_value", 0) or 0)
    allocated_capital = float(agent.get("allocated_capital", 0) or 0)
    total_return_pct = (
        ((total_value / allocated_capital) - 1) * 100 if allocated_capital > 0 else 0.0
    )

    # Calculate days active
    created_at = agent.get("created_at")
    days_active = 0
    if created_at:
        try:
            created_date = datetime.fromisoformat(
                created_at.replace("Z", "+00:00")
            ).date()
            days_active = (report_date - created_date).days
        except Exception:
            pass

    # Fetch macro overlay data
    macro = _fetch_macro_overlay_data(db)
    contributions = macro.get("contributions", {})

    # Get VIX details from macro indicators
    vix_level = None
    vix_regime = None
    try:
        vix_result = (
            db.table("macro_indicators")
            .select("value, metadata")
            .eq("indicator_name", "vix")
            .order("recorded_at", desc=True)
            .limit(1)
            .execute()
        )
        if vix_result.data:
            vix_level = vix_result.data[0].get("value")
            meta = vix_result.data[0].get("metadata", {})
            vix_regime = meta.get("regime_label") if meta else None
    except Exception:
        pass

    return AgentContext(
        agent_id=agent_id,
        agent_name=agent["name"],
        persona=agent.get("persona", "analytical"),
        strategy_type=agent.get("strategy_type", "momentum"),
        total_value=total_value,
        allocated_capital=allocated_capital,
        daily_return_pct=float(agent.get("daily_return_pct", 0) or 0),
        total_return_pct=total_return_pct,
        sharpe_ratio=agent.get("sharpe_ratio"),
        max_drawdown=agent.get("max_drawdown"),
        win_rate=agent.get("win_rate"),
        positions=positions_result.data or [],
        positions_count=len(positions_result.data or []),
        activities=activity_result.data or [],
        report_date=report_date,
        days_active=days_active,
        macro_regime=macro.get("regime"),
        macro_scale_factor=macro.get("scale_factor"),
        macro_composite_score=macro.get("composite_score"),
        macro_warnings=macro.get("warnings"),
        credit_spread_signal=contributions.get("credit_spread"),
        yield_curve_signal=contributions.get("yield_curve"),
        vol_regime_signal=contributions.get("vol_regime"),
        vix_level=vix_level,
        vix_regime=vix_regime,
        seasonality_signal=contributions.get("seasonality"),
        insider_breadth_signal=contributions.get("insider_breadth"),
    )


async def run_report_generation_job(report_date: date | None = None) -> dict:
    """
    Generate daily reports for all active agents.

    Returns a summary dict with counts of generated/failed reports.
    """
    target_date = report_date or date.today()

    logger.info("=" * 60)
    logger.info("REPORT GENERATION JOB STARTED")
    logger.info("Report date: %s", target_date)
    logger.info("=" * 60)

    start_time = datetime.now(timezone.utc)
    db = get_supabase_client()

    try:
        # Fetch all active agents
        agents_result = db.table("agents").select("*").eq("status", "active").execute()
        agents = agents_result.data or []

        logger.info("Found %d active agents", len(agents))

        if not agents:
            return {
                "status": "success",
                "message": "No active agents",
                "generated": 0,
                "failed": 0,
            }

        generator = get_report_generator()
        generated = 0
        failed = 0

        for agent in agents:
            agent_id = agent["id"]
            agent_name = agent.get("name", "?")

            try:
                context = _build_agent_context(agent, db, target_date)
                report = generator.generate_daily_report(context)

                # Save report to database (upsert)
                report_data = {
                    "agent_id": agent_id,
                    "report_date": report.report_date.isoformat(),
                    "report_content": report.content,
                    "performance_snapshot": report.performance_snapshot,
                    "positions_snapshot": report.positions_snapshot,
                    "actions_taken": report.actions_taken,
                }

                existing = (
                    db.table("daily_reports")
                    .select("id")
                    .eq("agent_id", agent_id)
                    .eq("report_date", target_date.isoformat())
                    .execute()
                )

                if existing.data:
                    db.table("daily_reports").update(report_data).eq(
                        "id", existing.data[0]["id"]
                    ).execute()
                else:
                    db.table("daily_reports").insert(report_data).execute()

                generated += 1
                logger.info(
                    "Agent %s (%s): report generated (%d tokens)",
                    agent_id,
                    agent_name,
                    report.tokens_used,
                )

            except Exception as e:
                failed += 1
                logger.error(
                    "Agent %s (%s): report generation failed — %s",
                    agent_id,
                    agent_name,
                    e,
                )

        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        summary = {
            "status": "success" if failed == 0 else "partial",
            "report_date": target_date.isoformat(),
            "agents_total": len(agents),
            "generated": generated,
            "failed": failed,
            "duration_seconds": round(duration, 2),
        }

        logger.info("=" * 60)
        logger.info("REPORT GENERATION SUMMARY")
        for key, value in summary.items():
            logger.info("  %s: %s", key, value)
        logger.info("=" * 60)

        return summary

    except Exception as e:
        logger.exception("Report generation job failed: %s", e)
        return {
            "status": "error",
            "error": str(e),
            "duration_seconds": (
                datetime.now(timezone.utc) - start_time
            ).total_seconds(),
        }


if __name__ == "__main__":
    summary = asyncio.run(run_report_generation_job())
    print(f"Report generation complete: {summary}")
