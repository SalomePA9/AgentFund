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

    symbol: str
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    market_cap: int | None = None
    price: float | None = None
    change_percent: float | None = None
    ma_30: float | None = None
    ma_100: float | None = None
    ma_200: float | None = None
    atr: float | None = None
    high_52w: float | None = None
    low_52w: float | None = None
    avg_volume: int | None = None
    volume: int | None = None
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    eps: float | None = None
    beta: float | None = None
    dividend_yield: float | None = None
    # Quality metrics
    roe: float | None = None
    profit_margin: float | None = None
    debt_to_equity: float | None = None
    # Momentum metrics
    momentum_6m: float | None = None
    momentum_12m: float | None = None
    # Factor scores (0-100)
    momentum_score: float | None = None
    value_score: float | None = None
    quality_score: float | None = None
    dividend_score: float | None = None
    volatility_score: float | None = None
    composite_score: float | None = None
    # Sentiment scores (populated in Phase 2.1)
    news_sentiment: float | None = None
    social_sentiment: float | None = None
    combined_sentiment: float | None = None
    sentiment_velocity: float | None = None
    updated_at: str | None = None
    scores_updated_at: str | None = None


class ScreenRequest(BaseModel):
    """Schema for stock screening request."""

    # Strategy preset name (momentum, quality_value, quality_momentum, dividend_growth,
    # trend_following, short_term_reversal, statistical_arbitrage, volatility_premium)
    strategy_type: str | None = None

    # Filter criteria
    min_market_cap: int | None = None
    max_market_cap: int | None = None
    sectors: list[str] | None = None
    exclude_sectors: list[str] | None = None

    # Score filters (0-100)
    min_momentum_score: float | None = None
    min_value_score: float | None = None
    min_quality_score: float | None = None
    min_dividend_score: float | None = None
    min_volatility_score: float | None = None
    min_composite_score: float | None = None

    # Sentiment filters (-100 to +100)
    min_combined_sentiment: float | None = None
    max_combined_sentiment: float | None = None
    min_news_sentiment: float | None = None
    min_social_sentiment: float | None = None
    min_sentiment_velocity: float | None = None  # Positive = improving
    sentiment_bullish_only: bool = False  # Only stocks with combined > 20
    sentiment_triangulation: bool = False  # News and social must agree

    # Price/MA filters
    above_ma_200: bool = True
    above_ma_100: bool = False
    above_ma_30: bool = False

    # Additional filters
    min_price: float | None = None
    max_price: float | None = None
    min_volume: int | None = None

    # Result options
    limit: int = 20
    sort_by: str = "composite_score"  # Field to sort results by
    sort_desc: bool = True


class SentimentResponse(BaseModel):
    """Schema for sentiment data response."""

    symbol: str
    news_sentiment: float | None = None
    social_sentiment: float | None = None
    combined_sentiment: float | None = None
    sentiment_velocity: float | None = None
    velocity_direction: str | None = None  # improving, declining, stable
    strength: str | None = None  # very_bullish, bullish, neutral, bearish, very_bearish
    has_sufficient_data: bool = False
    news_sample_size: int = 0
    social_sample_size: int = 0
    history: list[dict] | None = None


class SentimentBatchRequest(BaseModel):
    """Request for batch sentiment lookup."""

    symbols: list[str]


class SentimentBatchResponse(BaseModel):
    """Response for batch sentiment lookup."""

    data: dict[str, SentimentResponse]
    count: int


class TrendingSentimentResponse(BaseModel):
    """Response for trending sentiment stocks."""

    most_bullish: list[dict]
    most_bearish: list[dict]
    fastest_improving: list[dict]
    fastest_declining: list[dict]


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


@router.get("/stocks/{symbol}", response_model=StockResponse)
async def get_stock(
    symbol: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Get detailed information for a specific stock."""
    result = db.table("stocks").select("*").eq("symbol", symbol.upper()).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {symbol} not found",
        )

    return result.data[0]


@router.post("/screen", response_model=list[StockResponse])
async def screen_stocks(
    screen: ScreenRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """
    Screen stocks based on strategy type and custom criteria.

    Supported strategy_type values:
    - momentum: High momentum stocks (momentum_score >= 80)
    - quality_value: Value stocks with quality (value >= 70, quality >= 60)
    - quality_momentum: Momentum with quality filter (momentum >= 70, quality >= 60)
    - dividend_growth: Dividend stocks with quality (yield >= 2%, quality >= 50)
    - trend_following: Stocks in strong uptrends (price > all MAs, momentum >= 60)
    - short_term_reversal: Oversold quality stocks (volatility >= 70, quality >= 50)
    - statistical_arbitrage: Low volatility quality stocks (volatility >= 60, quality >= 60)
    - volatility_premium: Low volatility high quality (volatility >= 70, quality >= 70)
    """
    query = db.table("stocks").select("*")

    # Apply market cap filters
    if screen.min_market_cap:
        query = query.gte("market_cap", screen.min_market_cap)
    if screen.max_market_cap:
        query = query.lte("market_cap", screen.max_market_cap)

    # Apply sector filters
    if screen.sectors:
        query = query.in_("sector", screen.sectors)

    # Apply price filters
    if screen.min_price:
        query = query.gte("price", screen.min_price)
    if screen.max_price:
        query = query.lte("price", screen.max_price)

    # Apply volume filter
    if screen.min_volume:
        query = query.gte("avg_volume", screen.min_volume)

    # Apply score filters (user-specified)
    if screen.min_momentum_score is not None:
        query = query.gte("momentum_score", screen.min_momentum_score)
    if screen.min_value_score is not None:
        query = query.gte("value_score", screen.min_value_score)
    if screen.min_quality_score is not None:
        query = query.gte("quality_score", screen.min_quality_score)
    if screen.min_dividend_score is not None:
        query = query.gte("dividend_score", screen.min_dividend_score)
    if screen.min_volatility_score is not None:
        query = query.gte("volatility_score", screen.min_volatility_score)
    if screen.min_composite_score is not None:
        query = query.gte("composite_score", screen.min_composite_score)

    # Apply sentiment filters
    if screen.min_combined_sentiment is not None:
        query = query.gte("combined_sentiment", screen.min_combined_sentiment)
    if screen.max_combined_sentiment is not None:
        query = query.lte("combined_sentiment", screen.max_combined_sentiment)
    if screen.min_news_sentiment is not None:
        query = query.gte("news_sentiment", screen.min_news_sentiment)
    if screen.min_social_sentiment is not None:
        query = query.gte("social_sentiment", screen.min_social_sentiment)
    if screen.min_sentiment_velocity is not None:
        query = query.gte("sentiment_velocity", screen.min_sentiment_velocity)
    if screen.sentiment_bullish_only:
        query = query.gte("combined_sentiment", 20)

    # Strategy-specific defaults and sorting
    sort_field = screen.sort_by
    sort_desc = screen.sort_desc

    if screen.strategy_type == "momentum":
        # Pure momentum: high momentum score
        query = query.gte("momentum_score", 80)
        sort_field = "momentum_score"
    elif screen.strategy_type == "quality_value":
        # Value + Quality: cheap stocks that are fundamentally sound
        query = query.gte("value_score", 70)
        query = query.gte("quality_score", 60)
        sort_field = "value_score"
    elif screen.strategy_type == "quality_momentum":
        # Momentum + Quality: trending stocks with good fundamentals
        query = query.gte("momentum_score", 70)
        query = query.gte("quality_score", 60)
        sort_field = "momentum_score"
    elif screen.strategy_type == "dividend_growth":
        # Dividend stocks with quality
        query = query.gte("dividend_yield", 0.02)
        query = query.gte("quality_score", 50)
        sort_field = "dividend_score"
    elif screen.strategy_type == "trend_following":
        # Strong uptrends: price above all MAs, good momentum
        query = query.gte("momentum_score", 60)
        screen.above_ma_200 = True
        screen.above_ma_100 = True
        screen.above_ma_30 = True
        sort_field = "momentum_score"
    elif screen.strategy_type == "short_term_reversal":
        # Oversold stocks: high volatility, quality filter
        query = query.gte("volatility_score", 70)
        query = query.gte("quality_score", 50)
        sort_field = "volatility_score"
    elif screen.strategy_type == "statistical_arbitrage":
        # Low volatility quality stocks
        query = query.gte("volatility_score", 60)
        query = query.gte("quality_score", 60)
        sort_field = "quality_score"
    elif screen.strategy_type == "volatility_premium":
        # Low volatility, high quality
        query = query.gte("volatility_score", 70)
        query = query.gte("quality_score", 70)
        sort_field = "volatility_score"

    # Apply sorting
    query = query.order(sort_field, desc=sort_desc)

    # Fetch extra for post-filtering
    result = query.limit(screen.limit * 3).execute()
    filtered = result.data

    # Post-process: MA filters (price > MA)
    if screen.above_ma_200:
        filtered = [
            s for s in filtered
            if s.get("price") and s.get("ma_200") and s["price"] > s["ma_200"]
        ]
    if screen.above_ma_100:
        filtered = [
            s for s in filtered
            if s.get("price") and s.get("ma_100") and s["price"] > s["ma_100"]
        ]
    if screen.above_ma_30:
        filtered = [
            s for s in filtered
            if s.get("price") and s.get("ma_30") and s["price"] > s["ma_30"]
        ]

    # Post-process: exclude sectors
    if screen.exclude_sectors:
        filtered = [
            s for s in filtered
            if s.get("sector") not in screen.exclude_sectors
        ]

    # Post-process: sentiment triangulation (news and social must agree)
    if screen.sentiment_triangulation:
        filtered = [
            s for s in filtered
            if _sentiments_agree(s.get("news_sentiment"), s.get("social_sentiment"))
        ]

    return filtered[: screen.limit]


def _sentiments_agree(news: float | None, social: float | None) -> bool:
    """Check if news and social sentiment agree (both positive or both negative)."""
    if news is None or social is None:
        return False
    # Both bullish (> 10) or both bearish (< -10)
    if news > 10 and social > 10:
        return True
    if news < -10 and social < -10:
        return True
    return False


@router.get("/sentiment/{symbol}", response_model=SentimentResponse)
async def get_sentiment(
    symbol: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    include_history: bool = Query(False, description="Include sentiment history"),
):
    """
    Get sentiment data for a specific stock.

    Returns news sentiment, social sentiment, combined score, and velocity.
    Optionally includes historical sentiment data for charting.
    """
    # Get current sentiment from stocks table
    stock = db.table("stocks").select(
        "symbol, news_sentiment, social_sentiment, combined_sentiment, sentiment_velocity"
    ).eq("symbol", symbol.upper()).execute()

    if not stock.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {symbol} not found",
        )

    stock_data = stock.data[0]

    # Get recent sentiment history if requested
    history_data = None
    news_sample = 0
    social_sample = 0

    if include_history:
        history = (
            db.table("sentiment_history")
            .select("*")
            .eq("symbol", symbol.upper())
            .order("recorded_at", desc=True)
            .limit(30)
            .execute()
        )
        if history.data:
            history_data = [
                {
                    "date": h.get("recorded_at"),
                    "news": h.get("news_sentiment"),
                    "social": h.get("social_sentiment"),
                    "combined": h.get("combined_sentiment"),
                }
                for h in history.data
            ]
            # Get sample sizes from most recent record
            if history.data:
                news_sample = history.data[0].get("news_sample_size", 0)
                social_sample = history.data[0].get("social_sample_size", 0)

    # Calculate derived fields
    combined = stock_data.get("combined_sentiment")
    velocity = stock_data.get("sentiment_velocity")

    return SentimentResponse(
        symbol=stock_data["symbol"],
        news_sentiment=stock_data.get("news_sentiment"),
        social_sentiment=stock_data.get("social_sentiment"),
        combined_sentiment=combined,
        sentiment_velocity=velocity,
        velocity_direction=_get_velocity_direction(velocity),
        strength=_get_sentiment_strength(combined),
        has_sufficient_data=(news_sample + social_sample) >= 5,
        news_sample_size=news_sample,
        social_sample_size=social_sample,
        history=history_data,
    )


@router.post("/sentiment/batch", response_model=SentimentBatchResponse)
async def get_sentiment_batch(
    request: SentimentBatchRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """
    Get sentiment data for multiple stocks at once.

    Accepts up to 50 symbols per request.
    """
    if len(request.symbols) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 50 symbols per request",
        )

    symbols = [s.upper() for s in request.symbols]

    result = db.table("stocks").select(
        "symbol, news_sentiment, social_sentiment, combined_sentiment, sentiment_velocity"
    ).in_("symbol", symbols).execute()

    data = {}
    for stock in result.data:
        symbol = stock["symbol"]
        combined = stock.get("combined_sentiment")
        velocity = stock.get("sentiment_velocity")

        data[symbol] = SentimentResponse(
            symbol=symbol,
            news_sentiment=stock.get("news_sentiment"),
            social_sentiment=stock.get("social_sentiment"),
            combined_sentiment=combined,
            sentiment_velocity=velocity,
            velocity_direction=_get_velocity_direction(velocity),
            strength=_get_sentiment_strength(combined),
        )

    return SentimentBatchResponse(data=data, count=len(data))


@router.get("/sentiment/trending", response_model=TrendingSentimentResponse)
async def get_trending_sentiment(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
    limit: int = Query(10, ge=1, le=50),
):
    """
    Get stocks with notable sentiment movements.

    Returns:
    - Most bullish: Highest combined sentiment
    - Most bearish: Lowest combined sentiment
    - Fastest improving: Highest positive velocity
    - Fastest declining: Highest negative velocity
    """
    # Most bullish
    bullish = db.table("stocks").select(
        "symbol, name, combined_sentiment, sentiment_velocity, sector"
    ).not_.is_("combined_sentiment", "null").order(
        "combined_sentiment", desc=True
    ).limit(limit).execute()

    # Most bearish
    bearish = db.table("stocks").select(
        "symbol, name, combined_sentiment, sentiment_velocity, sector"
    ).not_.is_("combined_sentiment", "null").order(
        "combined_sentiment", desc=False
    ).limit(limit).execute()

    # Fastest improving (positive velocity)
    improving = db.table("stocks").select(
        "symbol, name, combined_sentiment, sentiment_velocity, sector"
    ).not_.is_("sentiment_velocity", "null").gt(
        "sentiment_velocity", 0
    ).order(
        "sentiment_velocity", desc=True
    ).limit(limit).execute()

    # Fastest declining (negative velocity)
    declining = db.table("stocks").select(
        "symbol, name, combined_sentiment, sentiment_velocity, sector"
    ).not_.is_("sentiment_velocity", "null").lt(
        "sentiment_velocity", 0
    ).order(
        "sentiment_velocity", desc=False
    ).limit(limit).execute()

    return TrendingSentimentResponse(
        most_bullish=bullish.data,
        most_bearish=bearish.data,
        fastest_improving=improving.data,
        fastest_declining=declining.data,
    )


def _get_velocity_direction(velocity: float | None) -> str | None:
    """Convert velocity to direction string."""
    if velocity is None:
        return None
    if velocity > 2:
        return "improving"
    elif velocity < -2:
        return "declining"
    else:
        return "stable"


def _get_sentiment_strength(combined: float | None) -> str | None:
    """Convert combined sentiment to strength category."""
    if combined is None:
        return None
    if combined <= -60:
        return "very_bearish"
    elif combined <= -20:
        return "bearish"
    elif combined <= 20:
        return "neutral"
    elif combined <= 60:
        return "bullish"
    else:
        return "very_bullish"


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


class PositionSizeRequest(BaseModel):
    """Request for position sizing calculation."""

    symbol: str
    capital: float
    risk_per_trade: float = 0.01  # 1% risk per trade
    stop_price: float | None = None  # Fixed stop price
    use_atr_stop: bool = True  # Use ATR-based stop
    atr_multiplier: float = 2.0  # ATR multiplier for stop
    max_position_pct: float = 0.10  # Max 10% of capital per position


class PositionSizeResponse(BaseModel):
    """Response for position sizing calculation."""

    symbol: str
    shares: int
    position_value: float
    position_pct: float
    entry_price: float
    stop_price: float
    risk_amount: float
    atr: float | None
    error: str | None = None


@router.post("/position-size", response_model=PositionSizeResponse)
async def calculate_position_size(
    request: PositionSizeRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """
    Calculate position size based on risk parameters.

    Uses ATR-based or fixed stop loss for position sizing.
    Ensures position doesn't exceed max percentage of capital.
    """
    from core.factors import calculate_position_size as calc_size

    # Get stock data
    result = db.table("stocks").select("price, atr").eq("symbol", request.symbol.upper()).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stock {request.symbol} not found",
        )

    stock = result.data[0]
    entry_price = stock.get("price")
    atr = stock.get("atr")

    if not entry_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No price data for {request.symbol}",
        )

    # Calculate position size
    if request.use_atr_stop and atr:
        sizing = calc_size(
            capital=request.capital,
            risk_per_trade=request.risk_per_trade,
            entry_price=entry_price,
            stop_price=entry_price - (atr * request.atr_multiplier),
            atr=atr,
            atr_multiplier=request.atr_multiplier,
            max_position_pct=request.max_position_pct,
        )
    elif request.stop_price:
        sizing = calc_size(
            capital=request.capital,
            risk_per_trade=request.risk_per_trade,
            entry_price=entry_price,
            stop_price=request.stop_price,
            max_position_pct=request.max_position_pct,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either use_atr_stop with ATR data or provide stop_price",
        )

    return PositionSizeResponse(
        symbol=request.symbol.upper(),
        shares=sizing["shares"],
        position_value=sizing["position_value"],
        position_pct=sizing["position_pct"],
        entry_price=entry_price,
        stop_price=sizing["stop_price"],
        risk_amount=sizing["risk_amount"],
        atr=atr,
        error=sizing.get("error"),
    )
