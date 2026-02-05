"""
Agents API endpoints.

Handles agent CRUD operations, status management, and position tracking.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import Client

from api.auth import get_current_user
from database import get_db

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class StrategyParams(BaseModel):
    """Strategy configuration parameters."""

    momentum_lookback_days: int = 180
    min_market_cap: int = 1_000_000_000
    sectors: str | list[str] = "all"
    exclude_tickers: list[str] = []
    max_positions: int = 10
    sentiment_weight: float = 0.3
    rebalance_frequency: str = "weekly"


class RiskParams(BaseModel):
    """Risk configuration parameters."""

    stop_loss_type: str = "ma_200"
    stop_loss_percentage: float = 0.10
    max_position_size_pct: float = 0.15
    min_risk_reward_ratio: float = 2.0
    max_sector_concentration: float = 0.50


class AgentCreate(BaseModel):
    """Schema for creating a new agent."""

    name: str = Field(..., min_length=1, max_length=100)
    persona: str = Field(default="analytical")
    strategy_type: str = Field(...)
    strategy_params: StrategyParams = Field(default_factory=StrategyParams)
    risk_params: RiskParams = Field(default_factory=RiskParams)
    allocated_capital: Decimal = Field(..., gt=0)
    time_horizon_days: int = Field(..., ge=30)


class AgentUpdate(BaseModel):
    """Schema for updating an agent."""

    name: str | None = None
    persona: str | None = None
    strategy_params: StrategyParams | None = None
    risk_params: RiskParams | None = None


class AgentResponse(BaseModel):
    """Schema for agent response."""

    id: str
    user_id: str
    name: str
    persona: str
    status: str
    strategy_type: str
    strategy_params: dict
    risk_params: dict
    allocated_capital: Decimal
    cash_balance: Decimal
    time_horizon_days: int
    start_date: date
    end_date: date
    total_value: Decimal | None
    total_return_pct: float | None
    daily_return_pct: float | None
    sharpe_ratio: float | None
    max_drawdown_pct: float | None
    win_rate_pct: float | None
    created_at: datetime
    updated_at: datetime


class PositionResponse(BaseModel):
    """Schema for position response."""

    id: str
    agent_id: str
    ticker: str
    entry_price: Decimal
    entry_date: date
    shares: Decimal
    entry_rationale: str | None
    target_price: Decimal | None
    stop_loss_price: Decimal | None
    current_price: Decimal | None
    current_value: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_pnl_pct: float | None
    status: str
    exit_price: Decimal | None
    exit_date: date | None
    exit_rationale: str | None
    realized_pnl: Decimal | None
    realized_pnl_pct: float | None


class ActivityResponse(BaseModel):
    """Schema for activity log response."""

    id: str
    agent_id: str
    activity_type: str
    ticker: str | None
    details: dict
    created_at: datetime


class PerformanceResponse(BaseModel):
    """Schema for performance metrics response."""

    total_value: Decimal
    total_return_pct: float
    daily_return_pct: float
    vs_benchmark_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate_pct: float
    open_positions: int
    closed_positions: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    status_filter: str | None = Query(None, alias="status"),
):
    """List all agents for the current user."""
    query = db.table("agents").select("*").eq("user_id", current_user["id"])

    if status_filter:
        query = query.eq("status", status_filter)

    result = query.order("created_at", desc=True).execute()
    return result.data


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent: AgentCreate,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Create a new trading agent."""
    # Validate strategy type (original 4 + advanced 5)
    valid_strategies = [
        # Original strategies
        "momentum", "quality_value", "quality_momentum", "dividend_growth",
        # Advanced strategies
        "trend_following", "short_term_reversal", "statistical_arbitrage", "volatility_premium",
    ]
    if agent.strategy_type not in valid_strategies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid strategy type. Must be one of: {valid_strategies}",
        )

    # Validate persona
    valid_personas = ["analytical", "aggressive", "conservative", "teacher", "concise"]
    if agent.persona not in valid_personas:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid persona. Must be one of: {valid_personas}",
        )

    # Check user has enough unallocated capital
    user_capital = Decimal(str(current_user.get("total_capital", 0)))
    user_allocated = Decimal(str(current_user.get("allocated_capital", 0)))
    available = user_capital - user_allocated

    if agent.allocated_capital > available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient capital. Available: ${available:.2f}",
        )

    # Calculate dates
    start_date = date.today()
    from datetime import timedelta

    end_date = start_date + timedelta(days=agent.time_horizon_days)

    # Create agent
    result = db.table("agents").insert(
        {
            "user_id": current_user["id"],
            "name": agent.name,
            "persona": agent.persona,
            "status": "active",
            "strategy_type": agent.strategy_type,
            "strategy_params": agent.strategy_params.model_dump(),
            "risk_params": agent.risk_params.model_dump(),
            "allocated_capital": float(agent.allocated_capital),
            "cash_balance": float(agent.allocated_capital),
            "time_horizon_days": agent.time_horizon_days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_value": float(agent.allocated_capital),
            "total_return_pct": 0.0,
        }
    ).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create agent",
        )

    # Update user's allocated capital
    new_allocated = user_allocated + agent.allocated_capital
    db.table("users").update(
        {"allocated_capital": float(new_allocated)}
    ).eq("id", current_user["id"]).execute()

    return result.data[0]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Get a specific agent."""
    result = (
        db.table("agents")
        .select("*")
        .eq("id", str(agent_id))
        .eq("user_id", current_user["id"])
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    return result.data[0]


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    agent_update: AgentUpdate,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Update an agent's configuration."""
    # Check agent exists and belongs to user
    existing = (
        db.table("agents")
        .select("*")
        .eq("id", str(agent_id))
        .eq("user_id", current_user["id"])
        .execute()
    )

    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    # Build update data
    update_data = {}
    if agent_update.name is not None:
        update_data["name"] = agent_update.name
    if agent_update.persona is not None:
        update_data["persona"] = agent_update.persona
    if agent_update.strategy_params is not None:
        update_data["strategy_params"] = agent_update.strategy_params.model_dump()
    if agent_update.risk_params is not None:
        update_data["risk_params"] = agent_update.risk_params.model_dump()

    if not update_data:
        return existing.data[0]

    result = (
        db.table("agents")
        .update(update_data)
        .eq("id", str(agent_id))
        .execute()
    )

    return result.data[0]


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Delete an agent."""
    # Get agent first
    existing = (
        db.table("agents")
        .select("*")
        .eq("id", str(agent_id))
        .eq("user_id", current_user["id"])
        .execute()
    )

    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    agent = existing.data[0]

    # Return allocated capital to user
    user_allocated = Decimal(str(current_user.get("allocated_capital", 0)))
    agent_value = Decimal(str(agent.get("total_value", agent["allocated_capital"])))
    new_allocated = max(Decimal("0"), user_allocated - Decimal(str(agent["allocated_capital"])))

    # Delete agent (cascade will delete positions, activity, etc.)
    db.table("agents").delete().eq("id", str(agent_id)).execute()

    # Update user's allocated capital
    db.table("users").update(
        {"allocated_capital": float(new_allocated)}
    ).eq("id", current_user["id"]).execute()


@router.post("/{agent_id}/pause", response_model=AgentResponse)
async def pause_agent(
    agent_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Pause an agent (stops trading but keeps positions)."""
    result = (
        db.table("agents")
        .update({"status": "paused"})
        .eq("id", str(agent_id))
        .eq("user_id", current_user["id"])
        .eq("status", "active")
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found or not active",
        )

    # Log activity
    db.table("agent_activity").insert(
        {
            "agent_id": str(agent_id),
            "activity_type": "paused",
            "details": {"reason": "user_requested"},
        }
    ).execute()

    return result.data[0]


@router.post("/{agent_id}/resume", response_model=AgentResponse)
async def resume_agent(
    agent_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Resume a paused agent."""
    result = (
        db.table("agents")
        .update({"status": "active"})
        .eq("id", str(agent_id))
        .eq("user_id", current_user["id"])
        .eq("status", "paused")
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found or not paused",
        )

    # Log activity
    db.table("agent_activity").insert(
        {
            "agent_id": str(agent_id),
            "activity_type": "resumed",
            "details": {"reason": "user_requested"},
        }
    ).execute()

    return result.data[0]


@router.get("/{agent_id}/positions", response_model=list[PositionResponse])
async def get_agent_positions(
    agent_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    status_filter: str | None = Query(None, alias="status"),
):
    """Get positions for an agent."""
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

    query = db.table("positions").select("*").eq("agent_id", str(agent_id))

    if status_filter:
        query = query.eq("status", status_filter)

    result = query.order("created_at", desc=True).execute()
    return result.data


@router.get("/{agent_id}/activity", response_model=list[ActivityResponse])
async def get_agent_activity(
    agent_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get activity log for an agent."""
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
        db.table("agent_activity")
        .select("*")
        .eq("agent_id", str(agent_id))
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    return result.data


@router.get("/{agent_id}/performance", response_model=PerformanceResponse)
async def get_agent_performance(
    agent_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Get performance metrics for an agent."""
    # Get agent
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

    agent = agent_result.data[0]

    # Get position counts
    positions = (
        db.table("positions")
        .select("status")
        .eq("agent_id", str(agent_id))
        .execute()
    )

    open_count = sum(1 for p in positions.data if p["status"] == "open")
    closed_count = len(positions.data) - open_count

    return {
        "total_value": agent.get("total_value", agent["allocated_capital"]),
        "total_return_pct": agent.get("total_return_pct", 0.0),
        "daily_return_pct": agent.get("daily_return_pct", 0.0),
        "vs_benchmark_pct": 0.0,  # TODO: Calculate vs SPY
        "sharpe_ratio": agent.get("sharpe_ratio", 0.0),
        "max_drawdown_pct": agent.get("max_drawdown_pct", 0.0),
        "win_rate_pct": agent.get("win_rate_pct", 0.0),
        "open_positions": open_count,
        "closed_positions": closed_count,
    }
