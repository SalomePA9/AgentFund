"""
Market Data API endpoints.

Handles stock data, screening, and sentiment information.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from supabase import Client

from api.auth import get_current_user
from database import get_db

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class StockResponse(BaseModel):
    """Schema for stock data response."""

    ticker: str
    name: str | None
    sector: str | None
    industry: str | None
    market_cap: int | None
    price: float | None
    ma_30: float | None
    ma_100: float | None
    ma_200: float | None
    atr: float | None
    momentum_score: float | None
    value_score: float | None
    quality_score: float | None
    composite_score: float | None
    pe_ratio: float | None
    pb_ratio: float | None
    roe: float | None
    profit_margin: float | None
    debt_to_equity: float | None
    dividend_yield: float | None
    news_sentiment: float | None
    social_sentiment: float | None
    combined_sentiment: float | None
    updated_at: str | None


class ScreenRequest(BaseModel):
    """Schema for stock screening request."""

    strategy_type: str | None = None
    min_market_cap: int | None = None
    sectors: list[str] | None = None
    min_momentum_score: float | None = None
    min_value_score: float | None = None
    min_quality_score: float | None = None
    above_ma_200: bool = True
    limit: int = 20


class SentimentResponse(BaseModel):
    """Schema for sentiment data response."""

    ticker: str
    news_sentiment: float | None
    social_sentiment: float | None
    combined_sentiment: float | None
    sentiment_velocity: float | None
    news_headlines: list[dict] | None = None


class StockListResponse(BaseModel):
    """Schema for paginated stock list."""

    data: list[StockResponse]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/stocks", response_model=StockListResponse)
async def list_stocks(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sector: str | None = None,
    sort_by: str = Query("market_cap", regex="^(market_cap|momentum_score|value_score|quality_score|price)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
):
    """Get paginated list of stocks."""
    offset = (page - 1) * per_page

    # Build query
    query = db.table("stocks").select("*", count="exact")

    if sector:
        query = query.eq("sector", sector)

    # Apply sorting
    query = query.order(sort_by, desc=(sort_order == "desc"))

    # Apply pagination
    result = query.range(offset, offset + per_page - 1).execute()

    return StockListResponse(
        data=result.data,
        total=result.count or 0,
        page=page,
        per_page=per_page,
    )


@router.get("/stocks/{ticker}", response_model=StockResponse)
async def get_stock(
    ticker: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Get detailed information for a specific stock."""
    result = db.table("stocks").select("*").eq("ticker", ticker.upper()).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {ticker} not found",
        )

    return result.data[0]


@router.post("/screen", response_model=list[StockResponse])
async def screen_stocks(
    screen: ScreenRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Screen stocks based on criteria."""
    query = db.table("stocks").select("*")

    # Apply filters
    if screen.min_market_cap:
        query = query.gte("market_cap", screen.min_market_cap)

    if screen.sectors:
        query = query.in_("sector", screen.sectors)

    if screen.min_momentum_score is not None:
        query = query.gte("momentum_score", screen.min_momentum_score)

    if screen.min_value_score is not None:
        query = query.gte("value_score", screen.min_value_score)

    if screen.min_quality_score is not None:
        query = query.gte("quality_score", screen.min_quality_score)

    # Strategy-specific defaults
    if screen.strategy_type == "momentum":
        query = query.gte("momentum_score", 80)
        query = query.order("momentum_score", desc=True)
    elif screen.strategy_type == "quality_value":
        query = query.gte("value_score", 70)
        query = query.gte("quality_score", 60)
        query = query.order("value_score", desc=True)
    elif screen.strategy_type == "quality_momentum":
        query = query.gte("momentum_score", 70)
        query = query.gte("quality_score", 60)
        query = query.order("momentum_score", desc=True)
    elif screen.strategy_type == "dividend_growth":
        query = query.gte("dividend_yield", 0.02)
        query = query.gte("quality_score", 50)
        query = query.order("dividend_yield", desc=True)
    else:
        query = query.order("composite_score", desc=True)

    # Above 200-day MA filter
    if screen.above_ma_200:
        # This requires price > ma_200, handled in post-processing
        pass

    result = query.limit(screen.limit * 2).execute()  # Fetch extra for filtering

    # Post-process: filter price > ma_200
    if screen.above_ma_200:
        filtered = [
            s for s in result.data
            if s.get("price") and s.get("ma_200") and s["price"] > s["ma_200"]
        ]
    else:
        filtered = result.data

    return filtered[: screen.limit]


@router.get("/sentiment/{ticker}", response_model=SentimentResponse)
async def get_sentiment(
    ticker: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Get sentiment data for a specific stock."""
    # Get current sentiment from stocks table
    stock = db.table("stocks").select(
        "ticker, news_sentiment, social_sentiment, combined_sentiment, sentiment_velocity"
    ).eq("ticker", ticker.upper()).execute()

    if not stock.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {ticker} not found",
        )

    # Get recent sentiment history
    history = (
        db.table("sentiment_history")
        .select("*")
        .eq("ticker", ticker.upper())
        .order("recorded_at", desc=True)
        .limit(10)
        .execute()
    )

    stock_data = stock.data[0]

    return SentimentResponse(
        ticker=stock_data["ticker"],
        news_sentiment=stock_data.get("news_sentiment"),
        social_sentiment=stock_data.get("social_sentiment"),
        combined_sentiment=stock_data.get("combined_sentiment"),
        sentiment_velocity=stock_data.get("sentiment_velocity"),
        news_headlines=None,  # TODO: Fetch from sentiment analysis
    )


@router.get("/sectors")
async def list_sectors(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Get list of available sectors."""
    result = db.table("stocks").select("sector").execute()

    # Get unique sectors
    sectors = list(set(s["sector"] for s in result.data if s.get("sector")))
    sectors.sort()

    return {"sectors": sectors}
