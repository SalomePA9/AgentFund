"""
Broker API endpoints.

Handles Alpaca broker connection, account info, orders, and positions.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from supabase import Client

from api.auth import get_current_user
from database import get_db
from core.broker import AlpacaBroker, BrokerMode, create_broker
from core.security import encrypt_api_key, decrypt_api_key

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class BrokerConnectRequest(BaseModel):
    """Schema for connecting broker account."""

    api_key: str
    api_secret: str
    paper_mode: bool = True


class BrokerStatus(BaseModel):
    """Schema for broker status response."""

    connected: bool
    paper_mode: bool | None = None
    account_id: str | None = None
    status: str | None = None
    portfolio_value: float | None = None
    cash: float | None = None
    buying_power: float | None = None
    equity: float | None = None


class AccountInfo(BaseModel):
    """Schema for full account information."""

    account_id: str
    status: str
    currency: str
    buying_power: float
    cash: float
    portfolio_value: float
    equity: float
    last_equity: float
    long_market_value: float
    short_market_value: float
    initial_margin: float
    maintenance_margin: float
    daytrade_count: int
    pattern_day_trader: bool
    trading_blocked: bool
    paper_mode: bool


class MarketClockResponse(BaseModel):
    """Schema for market clock response."""

    is_open: bool
    timestamp: str
    next_open: str
    next_close: str


class OrderRequest(BaseModel):
    """Schema for order placement request."""

    symbol: str
    qty: float
    side: str  # "buy" or "sell"
    order_type: str = "market"  # market, limit, stop, stop_limit, trailing_stop
    time_in_force: str = "day"  # day, gtc, ioc, fok
    limit_price: float | None = None
    stop_price: float | None = None
    trail_percent: float | None = None
    trail_price: float | None = None
    client_order_id: str | None = None


class OrderResponse(BaseModel):
    """Schema for order response."""

    id: str
    client_order_id: str | None
    symbol: str
    side: str
    type: str
    qty: float | None
    filled_qty: float
    filled_avg_price: float | None
    limit_price: float | None
    stop_price: float | None
    status: str
    time_in_force: str
    created_at: str | None
    filled_at: str | None


class PositionResponse(BaseModel):
    """Schema for position response."""

    symbol: str
    qty: float
    side: str
    avg_entry_price: float
    market_value: float
    cost_basis: float
    unrealized_pl: float
    unrealized_plpc: float
    current_price: float
    change_today: float


class QuoteResponse(BaseModel):
    """Schema for quote response."""

    symbol: str
    bid_price: float
    bid_size: int
    ask_price: float
    ask_size: int
    timestamp: str


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def get_user_broker(user: dict) -> AlpacaBroker:
    """Get broker instance for user."""
    api_key = user.get("alpaca_api_key")
    api_secret = user.get("alpaca_api_secret")

    if not api_key or not api_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Broker not connected. Please connect your Alpaca account first.",
        )

    paper_mode = user.get("alpaca_paper_mode", True)

    return create_broker(
        api_key=decrypt_api_key(api_key),
        api_secret=decrypt_api_key(api_secret),
        paper=paper_mode,
    )


# ---------------------------------------------------------------------------
# Connection Endpoints
# ---------------------------------------------------------------------------


@router.post("/connect", response_model=BrokerStatus)
async def connect_broker(
    credentials: BrokerConnectRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """
    Connect Alpaca broker account.

    Validates credentials by connecting to Alpaca, then stores encrypted
    credentials in the database.
    """
    try:
        # Test connection with provided credentials
        broker = create_broker(
            api_key=credentials.api_key,
            api_secret=credentials.api_secret,
            paper=credentials.paper_mode,
        )
        account = broker.get_account()

        # Encrypt and store credentials
        encrypted_key = encrypt_api_key(credentials.api_key)
        encrypted_secret = encrypt_api_key(credentials.api_secret)

        db.table("users").update(
            {
                "alpaca_api_key": encrypted_key,
                "alpaca_api_secret": encrypted_secret,
                "alpaca_paper_mode": credentials.paper_mode,
                "total_capital": account["portfolio_value"],
            }
        ).eq("id", current_user["id"]).execute()

        return BrokerStatus(
            connected=True,
            paper_mode=credentials.paper_mode,
            account_id=account["account_id"],
            status=account["status"],
            portfolio_value=account["portfolio_value"],
            cash=account["cash"],
            buying_power=account["buying_power"],
            equity=account["equity"],
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to connect to Alpaca: {str(e)}",
        )


@router.get("/status", response_model=BrokerStatus)
async def get_broker_status(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get broker connection status and account summary."""
    api_key = current_user.get("alpaca_api_key")
    api_secret = current_user.get("alpaca_api_secret")

    if not api_key or not api_secret:
        return BrokerStatus(connected=False)

    try:
        broker = get_user_broker(current_user)
        account = broker.get_account()

        return BrokerStatus(
            connected=True,
            paper_mode=current_user.get("alpaca_paper_mode", True),
            account_id=account["account_id"],
            status=account["status"],
            portfolio_value=account["portfolio_value"],
            cash=account["cash"],
            buying_power=account["buying_power"],
            equity=account["equity"],
        )

    except Exception:
        return BrokerStatus(connected=False)


@router.delete("/disconnect")
async def disconnect_broker(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """Disconnect broker account (removes stored credentials)."""
    db.table("users").update(
        {
            "alpaca_api_key": None,
            "alpaca_api_secret": None,
            "alpaca_paper_mode": None,
        }
    ).eq("id", current_user["id"]).execute()

    return {"message": "Broker disconnected successfully"}


# ---------------------------------------------------------------------------
# Account Endpoints
# ---------------------------------------------------------------------------


@router.get("/account", response_model=AccountInfo)
async def get_account_info(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get full Alpaca account information."""
    try:
        broker = get_user_broker(current_user)
        account = broker.get_account()

        return AccountInfo(
            account_id=account["account_id"],
            status=account["status"],
            currency=account["currency"],
            buying_power=account["buying_power"],
            cash=account["cash"],
            portfolio_value=account["portfolio_value"],
            equity=account["equity"],
            last_equity=account["last_equity"],
            long_market_value=account["long_market_value"],
            short_market_value=account["short_market_value"],
            initial_margin=account["initial_margin"],
            maintenance_margin=account["maintenance_margin"],
            daytrade_count=account["daytrade_count"],
            pattern_day_trader=account["pattern_day_trader"],
            trading_blocked=account["trading_blocked"],
            paper_mode=current_user.get("alpaca_paper_mode", True),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get account info: {str(e)}",
        )


@router.get("/clock", response_model=MarketClockResponse)
async def get_market_clock(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get market clock (open/close times)."""
    try:
        broker = get_user_broker(current_user)
        clock = broker.is_market_open()

        return MarketClockResponse(**clock)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get market clock: {str(e)}",
        )


@router.post("/switch-mode", response_model=BrokerStatus)
async def switch_trading_mode(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    """
    Toggle between paper and live trading mode.

    WARNING: Switching to live mode will use real money.
    """
    api_key = current_user.get("alpaca_api_key")
    api_secret = current_user.get("alpaca_api_secret")

    if not api_key or not api_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Broker not connected",
        )

    current_paper_mode = current_user.get("alpaca_paper_mode", True)
    new_paper_mode = not current_paper_mode

    try:
        # Test connection with new mode
        broker = create_broker(
            api_key=decrypt_api_key(api_key),
            api_secret=decrypt_api_key(api_secret),
            paper=new_paper_mode,
        )
        account = broker.get_account()

        # Update mode in database
        db.table("users").update(
            {"alpaca_paper_mode": new_paper_mode}
        ).eq("id", current_user["id"]).execute()

        return BrokerStatus(
            connected=True,
            paper_mode=new_paper_mode,
            account_id=account["account_id"],
            status=account["status"],
            portfolio_value=account["portfolio_value"],
            cash=account["cash"],
            buying_power=account["buying_power"],
            equity=account["equity"],
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to switch mode: {str(e)}",
        )


# ---------------------------------------------------------------------------
# Order Endpoints
# ---------------------------------------------------------------------------


@router.post("/orders", response_model=OrderResponse)
async def place_order(
    order: OrderRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Place a new order.

    Supports market, limit, stop, stop-limit, and trailing stop orders.
    """
    try:
        broker = get_user_broker(current_user)

        if order.order_type == "market":
            result = broker.place_market_order(
                symbol=order.symbol,
                qty=order.qty,
                side=order.side,
                time_in_force=order.time_in_force,
                client_order_id=order.client_order_id,
            )
        elif order.order_type == "limit":
            if not order.limit_price:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="limit_price required for limit orders",
                )
            result = broker.place_limit_order(
                symbol=order.symbol,
                qty=order.qty,
                side=order.side,
                limit_price=order.limit_price,
                time_in_force=order.time_in_force,
                client_order_id=order.client_order_id,
            )
        elif order.order_type == "stop":
            if not order.stop_price:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="stop_price required for stop orders",
                )
            result = broker.place_stop_order(
                symbol=order.symbol,
                qty=order.qty,
                side=order.side,
                stop_price=order.stop_price,
                time_in_force=order.time_in_force,
                client_order_id=order.client_order_id,
            )
        elif order.order_type == "stop_limit":
            if not order.stop_price or not order.limit_price:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="stop_price and limit_price required for stop-limit orders",
                )
            result = broker.place_stop_limit_order(
                symbol=order.symbol,
                qty=order.qty,
                side=order.side,
                stop_price=order.stop_price,
                limit_price=order.limit_price,
                time_in_force=order.time_in_force,
                client_order_id=order.client_order_id,
            )
        elif order.order_type == "trailing_stop":
            if not order.trail_percent and not order.trail_price:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="trail_percent or trail_price required for trailing stop orders",
                )
            result = broker.place_trailing_stop_order(
                symbol=order.symbol,
                qty=order.qty,
                side=order.side,
                trail_percent=order.trail_percent,
                trail_price=order.trail_price,
                time_in_force=order.time_in_force,
                client_order_id=order.client_order_id,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid order type: {order.order_type}",
            )

        return OrderResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to place order: {str(e)}",
        )


@router.get("/orders", response_model=list[OrderResponse])
async def get_orders(
    current_user: Annotated[dict, Depends(get_current_user)],
    status_filter: str = Query("all", regex="^(open|closed|all)$"),
    limit: int = Query(100, ge=1, le=500),
):
    """Get list of orders."""
    try:
        broker = get_user_broker(current_user)
        orders = broker.get_orders(status=status_filter, limit=limit)
        return [OrderResponse(**o) for o in orders]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get orders: {str(e)}",
        )


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get order details by ID."""
    try:
        broker = get_user_broker(current_user)
        order = broker.get_order(order_id)
        return OrderResponse(**order)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order not found: {str(e)}",
        )


@router.delete("/orders/{order_id}")
async def cancel_order(
    order_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Cancel an order."""
    try:
        broker = get_user_broker(current_user)
        broker.cancel_order(order_id)
        return {"message": f"Order {order_id} cancelled"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to cancel order: {str(e)}",
        )


@router.delete("/orders")
async def cancel_all_orders(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Cancel all open orders."""
    try:
        broker = get_user_broker(current_user)
        count = broker.cancel_all_orders()
        return {"message": f"Cancelled {count} orders"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel orders: {str(e)}",
        )


# ---------------------------------------------------------------------------
# Position Endpoints
# ---------------------------------------------------------------------------


@router.get("/positions", response_model=list[PositionResponse])
async def get_positions(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get all open positions."""
    try:
        broker = get_user_broker(current_user)
        positions = broker.get_positions()
        return [PositionResponse(**p) for p in positions]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get positions: {str(e)}",
        )


@router.get("/positions/{symbol}", response_model=PositionResponse)
async def get_position(
    symbol: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get position for a specific symbol."""
    try:
        broker = get_user_broker(current_user)
        position = broker.get_position(symbol)

        if not position:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No position for {symbol}",
            )

        return PositionResponse(**position)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get position: {str(e)}",
        )


@router.delete("/positions/{symbol}")
async def close_position(
    symbol: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    qty: float | None = None,
):
    """Close a position (fully or partially)."""
    try:
        broker = get_user_broker(current_user)
        order = broker.close_position(symbol, qty)
        return {"message": f"Closing position for {symbol}", "order": order}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to close position: {str(e)}",
        )


@router.delete("/positions")
async def close_all_positions(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Close all open positions."""
    try:
        broker = get_user_broker(current_user)
        orders = broker.close_all_positions()
        return {"message": f"Closing {len(orders)} positions", "orders": orders}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to close positions: {str(e)}",
        )


# ---------------------------------------------------------------------------
# Market Data Endpoints
# ---------------------------------------------------------------------------


@router.get("/quote/{symbol}", response_model=QuoteResponse)
async def get_quote(
    symbol: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Get latest quote for a symbol."""
    try:
        broker = get_user_broker(current_user)
        quote = broker.get_latest_quote(symbol)
        return QuoteResponse(**quote)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get quote: {str(e)}",
        )
