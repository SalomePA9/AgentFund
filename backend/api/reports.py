"""
Reports API endpoints.

Handles daily reports and team summaries.
"""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from supabase import Client

from api.auth import get_current_user
from database import get_db

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


class ReportListResponse(BaseModel):
    """Schema for paginated report list."""

    data: list[ReportResponse]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/team-summary", response_model=TeamSummaryResponse)
async def get_team_summary(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    summary_date: date | None = None,
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

    return TeamSummaryResponse(
        date=target_date,
        total_portfolio_value=total_value,
        total_daily_change=0,  # TODO: Calculate from daily returns
        total_daily_return_pct=0,  # TODO: Calculate weighted average
        total_return_pct=total_return_pct,
        agent_summaries=agent_summaries,
        top_performers=top_performers,
        recent_actions=recent_actions,
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


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def trigger_report_generation(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    agent_id: UUID | None = None,
):
    """
    Manually trigger report generation.
    Admin/debug endpoint - reports are normally generated automatically.
    """
    # This will be implemented with the LLM integration in Phase 2
    # For now, return a placeholder response

    return {
        "message": "Report generation queued",
        "agent_id": str(agent_id) if agent_id else "all",
        "status": "pending",
    }
