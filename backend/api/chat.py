"""
Chat API endpoints.

Handles agent chat conversations with LLM-powered responses.
"""

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from supabase import Client

from api.auth import get_current_user
from database import get_db
from llm import ChatContext
from llm import ChatMessage as LLMChatMessage
from llm import get_chat_handler

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    """Schema for a chat message."""

    id: str
    agent_id: str
    role: str  # 'user' or 'agent'
    message: str
    context_used: dict | None = None
    created_at: datetime


class ChatRequest(BaseModel):
    """Schema for sending a chat message."""

    message: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    """Schema for chat response."""

    user_message: ChatMessage
    agent_response: ChatMessage


class ChatHistoryResponse(BaseModel):
    """Schema for chat history."""

    data: list[ChatMessage]
    total: int
    has_more: bool


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def _build_chat_context(agent: dict, db: Client) -> ChatContext:
    """Build chat context from agent data."""
    agent_id = agent["id"]

    # Get top positions
    positions_result = (
        db.table("positions")
        .select("ticker, shares, entry_price, current_price, unrealized_pnl_pct")
        .eq("agent_id", agent_id)
        .eq("status", "open")
        .order("unrealized_pnl_pct", desc=True)
        .limit(5)
        .execute()
    )

    # Get recent activity
    activity_result = (
        db.table("agent_activity")
        .select("activity_type, ticker, details")
        .eq("agent_id", agent_id)
        .order("created_at", desc=True)
        .limit(3)
        .execute()
    )

    return ChatContext(
        agent_id=agent_id,
        agent_name=agent["name"],
        persona=agent.get("persona", "analytical"),
        strategy_type=agent.get("strategy_type", "momentum"),
        status=agent.get("status", "active"),
        total_value=float(agent.get("total_value", 0) or 0),
        allocated_capital=float(agent.get("allocated_capital", 0) or 0),
        daily_return_pct=float(agent.get("daily_return_pct", 0) or 0),
        total_return_pct=_calculate_total_return(agent),
        positions_count=agent.get("positions_count", 0) or 0,
        top_positions=positions_result.data or [],
        recent_activities=activity_result.data or [],
        sharpe_ratio=agent.get("sharpe_ratio"),
        win_rate=agent.get("win_rate"),
        max_drawdown=agent.get("max_drawdown"),
    )


def _calculate_total_return(agent: dict) -> float:
    """Calculate total return percentage."""
    total_value = float(agent.get("total_value", 0) or 0)
    allocated = float(agent.get("allocated_capital", 0) or 0)
    if allocated > 0:
        return ((total_value / allocated) - 1) * 100
    return 0.0


def _get_conversation_history(
    db: Client, agent_id: str, limit: int = 10
) -> list[LLMChatMessage]:
    """Get recent conversation history for context."""
    result = (
        db.table("agent_chats")
        .select("role, message, created_at")
        .eq("agent_id", agent_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    # Convert to LLM ChatMessage format and reverse to chronological order
    messages = []
    for msg in reversed(result.data or []):
        role = "assistant" if msg["role"] == "agent" else "user"
        messages.append(
            LLMChatMessage(
                role=role,
                content=msg["message"],
                timestamp=datetime.fromisoformat(
                    msg["created_at"].replace("Z", "+00:00")
                ),
            )
        )

    return messages


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/agents/{agent_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    agent_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    limit: int = Query(50, ge=1, le=100),
    before: datetime | None = None,
):
    """Get chat history for an agent."""
    # Verify agent belongs to user
    agent = (
        db.table("agents")
        .select("id, name, persona")
        .eq("id", str(agent_id))
        .eq("user_id", current_user["id"])
        .execute()
    )

    if not agent.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    # Build query
    query = (
        db.table("agent_chats").select("*", count="exact").eq("agent_id", str(agent_id))
    )

    if before:
        query = query.lt("created_at", before.isoformat())

    result = query.order("created_at", desc=True).limit(limit).execute()

    # Reverse to show oldest first
    messages = list(reversed(result.data))

    return ChatHistoryResponse(
        data=messages,
        total=result.count or 0,
        has_more=(result.count or 0) > len(messages),
    )


@router.post("/agents/{agent_id}", response_model=ChatResponse)
async def send_message(
    agent_id: UUID,
    request: ChatRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Send a message to an agent and get a response."""
    # Verify agent belongs to user
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

    # Save user message
    user_msg_result = (
        db.table("agent_chats")
        .insert(
            {
                "agent_id": str(agent_id),
                "role": "user",
                "message": request.message,
            }
        )
        .execute()
    )

    if not user_msg_result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save message",
        )

    user_message = user_msg_result.data[0]

    # Build context and get conversation history
    context = _build_chat_context(agent, db)
    history = _get_conversation_history(db, str(agent_id))

    # Generate agent response using LLM
    chat_handler = get_chat_handler()
    try:
        llm_response = chat_handler.generate_response(
            context=context,
            user_message=request.message,
            history=history,
        )
        agent_response_text = llm_response.content
        context_used = llm_response.context_used
    except Exception as e:
        logger.error(f"LLM response generation failed: {e}")
        # Fallback to simple response
        agent_response_text = (
            f"I'm {agent['name']}, your {agent['strategy_type'].replace('_', ' ')} agent. "
            f"I encountered an issue processing your message. Please try again."
        )
        context_used = {"error": str(e)}

    # Save agent response
    agent_msg_result = (
        db.table("agent_chats")
        .insert(
            {
                "agent_id": str(agent_id),
                "role": "agent",
                "message": agent_response_text,
                "context_used": context_used,
            }
        )
        .execute()
    )

    if not agent_msg_result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save agent response",
        )

    agent_message = agent_msg_result.data[0]

    return ChatResponse(
        user_message=user_message,
        agent_response=agent_message,
    )


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def clear_chat_history(
    agent_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Clear chat history for an agent."""
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

    db.table("agent_chats").delete().eq("agent_id", str(agent_id)).execute()
