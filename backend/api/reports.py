"""
Reports API endpoints.

Handles daily reports and team summaries with LLM-powered generation.
"""

import logging
from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from supabase import Client

from api.auth import get_current_user
from database import get_db
from llm import AgentContext, get_report_generator

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ReportResponse(BaseModel):
    """Schema for daily report response."""

    id: str
    agent_id: str
    report_date: date
    report_content: str
    performance_snapshot: dict
    positions_snapshot: list[dict]
    actions_taken: list[dict]
    created_at: datetime


class TeamSummaryResponse(BaseModel):
    """Schema for team summary response."""

    date: date
    total_portfolio_value: float
    total_daily_change: float
    total_daily_return_pct: float
    total_return_pct: float
    agent_summaries: list[dict]
    top_performers: list[dict]
    recent_actions: list[dict]
    ai_summary: str | None = None


class ReportListResponse(BaseModel):
    """Schema for paginated report list."""

    data: list[ReportResponse]
    total: int
    page: int
    per_page: int


class GenerateReportRequest(BaseModel):
    """Request to generate a report."""

    agent_id: UUID | None = None
    report_date: date | None = None


class GenerateReportResponse(BaseModel):
    """Response from report generation."""

    message: str
    agent_id: str | None
    report_date: date
    status: str
    report: ReportResponse | None = None


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def _build_agent_context(
    agent: dict, db: Client, report_date: date | None = None
) -> AgentContext:
    """Build agent context for report generation."""
    agent_id = agent["id"]
    target_date = report_date or date.today()

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

    # Get recent activity (last 7 days)
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
    if created_at:
        try:
            created_date = datetime.fromisoformat(
                created_at.replace("Z", "+00:00")
            ).date()
            days_active = (target_date - created_date).days
        except Exception:
            days_active = 0
    else:
        days_active = 0

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
        report_date=target_date,
        days_active=days_active,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/team-summary", response_model=TeamSummaryResponse)
async def get_team_summary(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    summary_date: date | None = None,
    include_ai_summary: bool = Query(False, description="Generate AI summary"),
):
    """Get team summary digest for all user's agents."""
    target_date = summary_date or date.today()

    # Get all user's agents
    agents = db.table("agents").select("*").eq("user_id", current_user["id"]).execute()

    if not agents.data:
        return TeamSummaryResponse(
            date=target_date,
            total_portfolio_value=0,
            total_daily_change=0,
            total_daily_return_pct=0,
            total_return_pct=0,
            agent_summaries=[],
            top_performers=[],
            recent_actions=[],
        )

    # Calculate totals
    total_value = sum(float(a.get("total_value", 0) or 0) for a in agents.data)
    total_allocated = sum(
        float(a.get("allocated_capital", 0) or 0) for a in agents.data
    )

    # Calculate weighted daily return
    total_daily_return = 0.0
    for agent in agents.data:
        agent_value = float(agent.get("total_value", 0) or 0)
        agent_daily_return = float(agent.get("daily_return_pct", 0) or 0)
        if total_value > 0:
            weight = agent_value / total_value
            total_daily_return += agent_daily_return * weight

    # Build agent summaries
    agent_summaries = []
    for agent in agents.data:
        agent_value = float(agent.get("total_value", 0) or 0)
        agent_allocated = float(agent.get("allocated_capital", 0) or 0)
        total_return = (
            ((agent_value / agent_allocated) - 1) * 100 if agent_allocated > 0 else 0
        )

        agent_summaries.append(
            {
                "id": agent["id"],
                "name": agent["name"],
                "strategy_type": agent["strategy_type"],
                "status": agent["status"],
                "total_value": agent_value,
                "daily_return_pct": agent.get("daily_return_pct", 0) or 0,
                "total_return_pct": total_return,
            }
        )

    # Sort for top performers
    top_performers = sorted(
        agent_summaries,
        key=lambda x: x["total_return_pct"],
        reverse=True,
    )[:3]

    # Get recent actions across all agents
    agent_ids = [a["id"] for a in agents.data]
    recent_actions_result = (
        db.table("agent_activity")
        .select("*, agents(name)")
        .in_("agent_id", agent_ids)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )

    recent_actions = [
        {
            "agent_name": a.get("agents", {}).get("name", "Unknown"),
            "activity_type": a["activity_type"],
            "ticker": a.get("ticker"),
            "details": a.get("details", {}),
            "created_at": a["created_at"],
        }
        for a in recent_actions_result.data
    ]

    # Calculate portfolio-level metrics
    total_return_pct = (
        ((total_value / total_allocated) - 1) * 100 if total_allocated > 0 else 0
    )

    # Calculate daily change in dollars
    total_daily_change = total_value * (total_daily_return / 100)

    # Generate AI summary if requested
    ai_summary = None
    if include_ai_summary:
        try:
            generator = get_report_generator()
            agent_contexts = [
                AgentContext(
                    agent_id=a["id"],
                    agent_name=a["name"],
                    persona=a.get("persona", "analytical"),
                    strategy_type=a.get("strategy_type", "momentum"),
                    total_value=float(a.get("total_value", 0) or 0),
                    allocated_capital=float(a.get("allocated_capital", 0) or 0),
                    daily_return_pct=float(a.get("daily_return_pct", 0) or 0),
                    total_return_pct=(
                        (
                            (
                                float(a.get("total_value", 0) or 0)
                                / float(a.get("allocated_capital", 1) or 1)
                            )
                            - 1
                        )
                        * 100
                    ),
                )
                for a in agents.data
            ]
            ai_summary = generator.generate_team_summary(agent_contexts, target_date)
        except Exception as e:
            logger.error(f"Failed to generate AI team summary: {e}")

    return TeamSummaryResponse(
        date=target_date,
        total_portfolio_value=total_value,
        total_daily_change=total_daily_change,
        total_daily_return_pct=total_daily_return,
        total_return_pct=total_return_pct,
        agent_summaries=agent_summaries,
        top_performers=top_performers,
        recent_actions=recent_actions,
        ai_summary=ai_summary,
    )


@router.get("/agents/{agent_id}", response_model=ReportListResponse)
async def list_agent_reports(
    agent_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
):
    """Get paginated list of reports for an agent."""
    # Verify agent belongs to user
    agent = (
        db.table("agents")
        .select("id")
        .eq("id", str(agent_id))
        .eq("user_id", current_user["id"])
        .execute()
    )

    if not agent.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    offset = (page - 1) * per_page

    result = (
        db.table("daily_reports")
        .select("*", count="exact")
        .eq("agent_id", str(agent_id))
        .order("report_date", desc=True)
        .range(offset, offset + per_page - 1)
        .execute()
    )

    return ReportListResponse(
        data=result.data,
        total=result.count or 0,
        page=page,
        per_page=per_page,
    )


@router.get("/agents/{agent_id}/{report_date}", response_model=ReportResponse)
async def get_agent_report(
    agent_id: UUID,
    report_date: date,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Get a specific daily report for an agent."""
    # Verify agent belongs to user
    agent = (
        db.table("agents")
        .select("id")
        .eq("id", str(agent_id))
        .eq("user_id", current_user["id"])
        .execute()
    )

    if not agent.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    result = (
        db.table("daily_reports")
        .select("*")
        .eq("agent_id", str(agent_id))
        .eq("report_date", report_date.isoformat())
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report not found for {report_date}",
        )

    return result.data[0]


@router.post("/generate", response_model=GenerateReportResponse)
async def generate_report(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    request: GenerateReportRequest | None = None,
):
    """
    Generate a daily report for an agent.

    If agent_id is provided, generates for that agent only.
    Otherwise, generates for all user's agents.
    """
    target_date = (request.report_date if request else None) or date.today()
    agent_id = request.agent_id if request else None

    # Get agent(s)
    if agent_id:
        agent_result = (
            db.table("agents")
            .select("*")
            .eq("id", str(agent_id))
            .eq("user_id", current_user["id"])
            .execute()
        )
        if not agent_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found",
            )
        agents = agent_result.data
    else:
        agents_result = (
            db.table("agents").select("*").eq("user_id", current_user["id"]).execute()
        )
        agents = agents_result.data or []

    if not agents:
        return GenerateReportResponse(
            message="No agents found",
            agent_id=str(agent_id) if agent_id else None,
            report_date=target_date,
            status="skipped",
        )

    # Generate report for first/specified agent
    agent = agents[0]
    context = _build_agent_context(agent, db, target_date)

    generator = get_report_generator()
    try:
        report = generator.generate_daily_report(context)
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation failed: {str(e)}",
        )

    # Save report to database
    report_data = {
        "agent_id": agent["id"],
        "report_date": report.report_date.isoformat(),
        "report_content": report.content,
        "performance_snapshot": report.performance_snapshot,
        "positions_snapshot": report.positions_snapshot,
        "actions_taken": report.actions_taken,
    }

    # Upsert (update if exists for same date)
    existing = (
        db.table("daily_reports")
        .select("id")
        .eq("agent_id", agent["id"])
        .eq("report_date", target_date.isoformat())
        .execute()
    )

    if existing.data:
        # Update existing report
        result = (
            db.table("daily_reports")
            .update(report_data)
            .eq("id", existing.data[0]["id"])
            .execute()
        )
    else:
        # Insert new report
        result = db.table("daily_reports").insert(report_data).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save report",
        )

    saved_report = result.data[0]

    return GenerateReportResponse(
        message="Report generated successfully",
        agent_id=agent["id"],
        report_date=target_date,
        status="completed",
        report=ReportResponse(
            id=saved_report["id"],
            agent_id=saved_report["agent_id"],
            report_date=saved_report["report_date"],
            report_content=saved_report["report_content"],
            performance_snapshot=saved_report["performance_snapshot"],
            positions_snapshot=saved_report["positions_snapshot"],
            actions_taken=saved_report["actions_taken"],
            created_at=saved_report["created_at"],
        ),
    )
