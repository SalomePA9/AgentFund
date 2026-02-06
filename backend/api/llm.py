"""
LLM API endpoints.

Provides endpoints for LLM usage monitoring and management.
"""

import logging
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from api.auth import get_current_user
from llm import get_claude_client

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class LLMStatusResponse(BaseModel):
    """LLM service status."""

    configured: bool
    model: str
    cache_enabled: bool
    cache_size: int


class LLMUsageResponse(BaseModel):
    """LLM usage statistics."""

    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    estimated_cost: float
    period: str


class ClearCacheResponse(BaseModel):
    """Response from clearing cache."""

    entries_cleared: int
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/status", response_model=LLMStatusResponse)
async def get_llm_status(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Get LLM service status.

    Returns whether the LLM is configured and basic settings.
    """
    client = get_claude_client()

    return LLMStatusResponse(
        configured=client.is_configured,
        model=client.default_model,
        cache_enabled=client.enable_cache,
        cache_size=len(client._cache),
    )


@router.get("/usage", response_model=LLMUsageResponse)
async def get_llm_usage(
    current_user: Annotated[dict, Depends(get_current_user)],
    hours: int = Query(24, ge=1, le=720, description="Hours to look back"),
):
    """
    Get LLM usage statistics.

    Returns token usage and estimated cost for the specified period.
    """
    client = get_claude_client()

    since = datetime.utcnow() - timedelta(hours=hours)
    usage = client.get_usage_summary(since=since)

    return LLMUsageResponse(
        total_requests=usage["total_requests"],
        total_input_tokens=usage["total_input_tokens"],
        total_output_tokens=usage["total_output_tokens"],
        total_tokens=usage["total_tokens"],
        estimated_cost=usage["estimated_cost"],
        period=f"last {hours} hours",
    )


@router.post("/cache/clear", response_model=ClearCacheResponse)
async def clear_llm_cache(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Clear the LLM response cache.

    Useful for debugging or when you want fresh responses.
    """
    client = get_claude_client()
    cleared = client.clear_cache()

    return ClearCacheResponse(
        entries_cleared=cleared,
        message=f"Cleared {cleared} cached responses",
    )
