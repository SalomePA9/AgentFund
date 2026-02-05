"""
Chat API endpoints.

Handles agent chat conversations.
"""

from datetime import datetime
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
        db.table("agent_chats")
        .select("*", count="exact")
        .eq("agent_id", str(agent_id))
    )

    if before:
        query = query.lt("created_at", before.isoformat())

    result = (
        query
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

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
    user_msg_result = db.table("agent_chats").insert({
        "agent_id": str(agent_id),
        "role": "user",
        "message": request.message,
    }).execute()

    if not user_msg_result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save message",
        )

    user_message = user_msg_result.data[0]

    # Generate agent response
    # This will be implemented with LLM integration in Phase 2
    # For now, return a placeholder response
    agent_response_text = _generate_placeholder_response(agent, request.message)

    # Save agent response
    agent_msg_result = db.table("agent_chats").insert({
        "agent_id": str(agent_id),
        "role": "agent",
        "message": agent_response_text,
        "context_used": {
            "agent_name": agent["name"],
            "persona": agent["persona"],
            "strategy_type": agent["strategy_type"],
        },
    }).execute()

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


# ---------------------------------------------------------------------------
# Placeholder Response Generator
# ---------------------------------------------------------------------------


def _generate_placeholder_response(agent: dict, user_message: str) -> str:
    """
    Generate a placeholder response until LLM integration is complete.
    This will be replaced with actual Claude API calls in Phase 2.
    """
    name = agent["name"]
    persona = agent["persona"]
    strategy = agent["strategy_type"]

    # Simple placeholder responses based on persona
    persona_intros = {
        "analytical": f"Based on my analysis as {name}",
        "aggressive": f"Let me be direct with you",
        "conservative": f"Taking a measured approach",
        "teacher": f"Great question! Let me explain",
        "concise": f"Here's the key point",
    }

    intro = persona_intros.get(persona, f"As {name}")

    return (
        f"{intro}, I'm currently running a {strategy.replace('_', ' ')} strategy. "
        f"The full chat functionality with personalized responses will be available soon. "
        f"In the meantime, you can view my positions and daily reports for detailed insights."
    )
