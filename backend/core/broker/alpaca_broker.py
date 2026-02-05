"""
Alpaca Broker Integration

Handles all interactions with Alpaca's trading API for paper and live trading.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
    StopLimitOrderRequest,
    StopOrderRequest,
    TrailingStopOrderRequest,
)
from alpaca.trading.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
    QueryOrderStatus,
    TimeInForce,
)
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
from alpaca.data.timeframe import TimeFrame

logger = logging.getLogger(__name__)


class BrokerMode(str, Enum):
    """Trading mode for the broker."""
    PAPER = "paper"
    LIVE = "live"


class AlpacaBroker:
    """
    Alpaca broker client for paper and live trading.

    Handles:
    - Account information retrieval
    - Market/limit/stop order placement
    - Order cancellation and modification
    - Position retrieval and management
    - Quote and bar data access
    """

    # API endpoints
    PAPER_URL = "https://paper-api.alpaca.markets"
    LIVE_URL = "https://api.alpaca.markets"

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        mode: BrokerMode = BrokerMode.PAPER
    ):
        """
        Initialize Alpaca broker client.

        Args:
            api_key: Alpaca API key
            api_secret: Alpaca API secret
            mode: Trading mode (paper or live)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.mode = mode

        # Determine if paper trading
        paper = mode == BrokerMode.PAPER

        # Initialize trading client
        self.trading_client = TradingClient(
            api_key=api_key,
            secret_key=api_secret,
            paper=paper
        )

        # Initialize data client (same credentials work for both)
        self.data_client = StockHistoricalDataClient(
            api_key=api_key,
            secret_key=api_secret
        )

        logger.info(f"Alpaca broker initialized in {mode.value} mode")

    # =========================================================================
    # Account Operations
    # =========================================================================

    def get_account(self) -> dict[str, Any]:
        """
        Get account information.

        Returns:
            Account details including buying power, equity, etc.
        """
        try:
            account = self.trading_client.get_account()

            return {
                "account_id": account.id,
                "status": account.status.value,
                "currency": account.currency,
                "buying_power": float(account.buying_power),
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value),
                "equity": float(account.equity),
                "last_equity": float(account.last_equity),
                "long_market_value": float(account.long_market_value),
                "short_market_value": float(account.short_market_value),
                "initial_margin": float(account.initial_margin),
                "maintenance_margin": float(account.maintenance_margin),
                "daytrade_count": account.daytrade_count,
                "pattern_day_trader": account.pattern_day_trader,
                "trading_blocked": account.trading_blocked,
                "transfers_blocked": account.transfers_blocked,
                "account_blocked": account.account_blocked,
                "trade_suspended_by_user": account.trade_suspended_by_user,
                "multiplier": account.multiplier,
                "created_at": account.created_at.isoformat() if account.created_at else None,
            }
        except Exception as e:
            logger.error(f"Error getting account: {str(e)}")
            raise

    def is_market_open(self) -> dict[str, Any]:
        """
        Check if the market is currently open.

        Returns:
            Market status including open/close times
        """
        try:
            clock = self.trading_client.get_clock()

            return {
                "is_open": clock.is_open,
                "timestamp": clock.timestamp.isoformat(),
                "next_open": clock.next_open.isoformat(),
                "next_close": clock.next_close.isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting market clock: {str(e)}")
            raise

    # =========================================================================
    # Order Operations
    # =========================================================================

    def place_market_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        time_in_force: str = "day",
        client_order_id: str | None = None
    ) -> dict[str, Any]:
        """
        Place a market order.

        Args:
            symbol: Stock symbol
            qty: Number of shares
            side: "buy" or "sell"
            time_in_force: Order duration (day, gtc, ioc, fok)
            client_order_id: Optional custom order ID

        Returns:
            Order details
        """
        try:
            order_data = MarketOrderRequest(
                symbol=symbol.upper(),
                qty=qty,
                side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
                time_in_force=self._parse_time_in_force(time_in_force),
                client_order_id=client_order_id,
            )

            order = self.trading_client.submit_order(order_data)
            return self._format_order(order)

        except Exception as e:
            logger.error(f"Error placing market order: {str(e)}")
            raise

    def place_limit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        limit_price: float,
        time_in_force: str = "day",
        client_order_id: str | None = None
    ) -> dict[str, Any]:
        """
        Place a limit order.

        Args:
            symbol: Stock symbol
            qty: Number of shares
            side: "buy" or "sell"
            limit_price: Limit price
            time_in_force: Order duration
            client_order_id: Optional custom order ID

        Returns:
            Order details
        """
        try:
            order_data = LimitOrderRequest(
                symbol=symbol.upper(),
                qty=qty,
                side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
                time_in_force=self._parse_time_in_force(time_in_force),
                limit_price=limit_price,
                client_order_id=client_order_id,
            )

            order = self.trading_client.submit_order(order_data)
            return self._format_order(order)

        except Exception as e:
            logger.error(f"Error placing limit order: {str(e)}")
            raise

    def place_stop_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        stop_price: float,
        time_in_force: str = "day",
        client_order_id: str | None = None
    ) -> dict[str, Any]:
        """
        Place a stop order.

        Args:
            symbol: Stock symbol
            qty: Number of shares
            side: "buy" or "sell"
            stop_price: Stop trigger price
            time_in_force: Order duration
            client_order_id: Optional custom order ID

        Returns:
            Order details
        """
        try:
            order_data = StopOrderRequest(
                symbol=symbol.upper(),
                qty=qty,
                side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
                time_in_force=self._parse_time_in_force(time_in_force),
                stop_price=stop_price,
                client_order_id=client_order_id,
            )

            order = self.trading_client.submit_order(order_data)
            return self._format_order(order)

        except Exception as e:
            logger.error(f"Error placing stop order: {str(e)}")
            raise

    def place_stop_limit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        stop_price: float,
        limit_price: float,
        time_in_force: str = "day",
        client_order_id: str | None = None
    ) -> dict[str, Any]:
        """
        Place a stop-limit order.

        Args:
            symbol: Stock symbol
            qty: Number of shares
            side: "buy" or "sell"
            stop_price: Stop trigger price
            limit_price: Limit price after stop triggers
            time_in_force: Order duration
            client_order_id: Optional custom order ID

        Returns:
            Order details
        """
        try:
            order_data = StopLimitOrderRequest(
                symbol=symbol.upper(),
                qty=qty,
                side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
                time_in_force=self._parse_time_in_force(time_in_force),
                stop_price=stop_price,
                limit_price=limit_price,
                client_order_id=client_order_id,
            )

            order = self.trading_client.submit_order(order_data)
            return self._format_order(order)

        except Exception as e:
            logger.error(f"Error placing stop-limit order: {str(e)}")
            raise

    def place_trailing_stop_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        trail_percent: float | None = None,
        trail_price: float | None = None,
        time_in_force: str = "day",
        client_order_id: str | None = None
    ) -> dict[str, Any]:
        """
        Place a trailing stop order.

        Args:
            symbol: Stock symbol
            qty: Number of shares
            side: "buy" or "sell"
            trail_percent: Trail by percentage (e.g., 5 for 5%)
            trail_price: Trail by fixed dollar amount
            time_in_force: Order duration
            client_order_id: Optional custom order ID

        Returns:
            Order details
        """
        try:
            order_data = TrailingStopOrderRequest(
                symbol=symbol.upper(),
                qty=qty,
                side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
                time_in_force=self._parse_time_in_force(time_in_force),
                trail_percent=trail_percent,
                trail_price=trail_price,
                client_order_id=client_order_id,
            )

            order = self.trading_client.submit_order(order_data)
            return self._format_order(order)

        except Exception as e:
            logger.error(f"Error placing trailing stop order: {str(e)}")
            raise

    def get_order(self, order_id: str) -> dict[str, Any]:
        """
        Get order details by ID.

        Args:
            order_id: Alpaca order ID

        Returns:
            Order details
        """
        try:
            order = self.trading_client.get_order_by_id(order_id)
            return self._format_order(order)
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {str(e)}")
            raise

    def get_orders(
        self,
        status: str = "all",
        limit: int = 100,
        symbols: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """
        Get list of orders.

        Args:
            status: Filter by status (open, closed, all)
            limit: Maximum number of orders to return
            symbols: Filter by symbols

        Returns:
            List of orders
        """
        try:
            # Map status string to enum
            status_map = {
                "open": QueryOrderStatus.OPEN,
                "closed": QueryOrderStatus.CLOSED,
                "all": QueryOrderStatus.ALL,
            }

            request = GetOrdersRequest(
                status=status_map.get(status.lower(), QueryOrderStatus.ALL),
                limit=limit,
                symbols=symbols,
            )

            orders = self.trading_client.get_orders(request)
            return [self._format_order(order) for order in orders]

        except Exception as e:
            logger.error(f"Error getting orders: {str(e)}")
            raise

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.

        Args:
            order_id: Alpaca order ID

        Returns:
            True if cancelled successfully
        """
        try:
            self.trading_client.cancel_order_by_id(order_id)
            logger.info(f"Order {order_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {str(e)}")
            raise

    def cancel_all_orders(self) -> int:
        """
        Cancel all open orders.

        Returns:
            Number of orders cancelled
        """
        try:
            cancelled = self.trading_client.cancel_orders()
            count = len(cancelled) if cancelled else 0
            logger.info(f"Cancelled {count} orders")
            return count
        except Exception as e:
            logger.error(f"Error cancelling all orders: {str(e)}")
            raise

    # =========================================================================
    # Position Operations
    # =========================================================================

    def get_positions(self) -> list[dict[str, Any]]:
        """
        Get all open positions.

        Returns:
            List of position details
        """
        try:
            positions = self.trading_client.get_all_positions()
            return [self._format_position(pos) for pos in positions]
        except Exception as e:
            logger.error(f"Error getting positions: {str(e)}")
            raise

    def get_position(self, symbol: str) -> dict[str, Any] | None:
        """
        Get position for a specific symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Position details or None if no position
        """
        try:
            position = self.trading_client.get_open_position(symbol.upper())
            return self._format_position(position)
        except Exception as e:
            if "position does not exist" in str(e).lower():
                return None
            logger.error(f"Error getting position for {symbol}: {str(e)}")
            raise

    def close_position(self, symbol: str, qty: float | None = None) -> dict[str, Any]:
        """
        Close a position (fully or partially).

        Args:
            symbol: Stock symbol
            qty: Number of shares to close (None = close all)

        Returns:
            Order details for the closing order
        """
        try:
            if qty:
                order = self.trading_client.close_position(
                    symbol.upper(),
                    close_options={"qty": str(qty)}
                )
            else:
                order = self.trading_client.close_position(symbol.upper())

            return self._format_order(order)
        except Exception as e:
            logger.error(f"Error closing position for {symbol}: {str(e)}")
            raise

    def close_all_positions(self) -> list[dict[str, Any]]:
        """
        Close all open positions.

        Returns:
            List of closing orders
        """
        try:
            orders = self.trading_client.close_all_positions()
            return [self._format_order(o) for o in orders] if orders else []
        except Exception as e:
            logger.error(f"Error closing all positions: {str(e)}")
            raise

    # =========================================================================
    # Market Data Operations
    # =========================================================================

    def get_latest_quote(self, symbol: str) -> dict[str, Any]:
        """
        Get the latest quote for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Latest quote data
        """
        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol.upper())
            quotes = self.data_client.get_stock_latest_quote(request)
            quote = quotes[symbol.upper()]

            return {
                "symbol": symbol.upper(),
                "bid_price": float(quote.bid_price),
                "bid_size": quote.bid_size,
                "ask_price": float(quote.ask_price),
                "ask_size": quote.ask_size,
                "timestamp": quote.timestamp.isoformat(),
            }
        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {str(e)}")
            raise

    def get_bars(
        self,
        symbol: str,
        timeframe: str = "1Day",
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        """
        Get historical bars for a symbol.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe (1Min, 5Min, 15Min, 1Hour, 1Day)
            start: Start datetime
            end: End datetime
            limit: Maximum number of bars

        Returns:
            List of bar data
        """
        try:
            # Parse timeframe
            tf_map = {
                "1min": TimeFrame.Minute,
                "5min": TimeFrame(5, "Min"),
                "15min": TimeFrame(15, "Min"),
                "1hour": TimeFrame.Hour,
                "1day": TimeFrame.Day,
            }
            tf = tf_map.get(timeframe.lower(), TimeFrame.Day)

            # Default to last 30 days if no dates provided
            if not end:
                end = datetime.now()
            if not start:
                start = end - timedelta(days=30)

            request = StockBarsRequest(
                symbol_or_symbols=symbol.upper(),
                timeframe=tf,
                start=start,
                end=end,
                limit=limit,
            )

            bars = self.data_client.get_stock_bars(request)
            symbol_bars = bars[symbol.upper()]

            return [
                {
                    "timestamp": bar.timestamp.isoformat(),
                    "open": float(bar.open),
                    "high": float(bar.high),
                    "low": float(bar.low),
                    "close": float(bar.close),
                    "volume": bar.volume,
                    "vwap": float(bar.vwap) if bar.vwap else None,
                    "trade_count": bar.trade_count,
                }
                for bar in symbol_bars
            ]
        except Exception as e:
            logger.error(f"Error getting bars for {symbol}: {str(e)}")
            raise

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _parse_time_in_force(self, tif: str) -> TimeInForce:
        """Parse time in force string to enum."""
        tif_map = {
            "day": TimeInForce.DAY,
            "gtc": TimeInForce.GTC,
            "ioc": TimeInForce.IOC,
            "fok": TimeInForce.FOK,
            "opg": TimeInForce.OPG,
            "cls": TimeInForce.CLS,
        }
        return tif_map.get(tif.lower(), TimeInForce.DAY)

    def _format_order(self, order) -> dict[str, Any]:
        """Format order object to dictionary."""
        return {
            "id": str(order.id),
            "client_order_id": order.client_order_id,
            "symbol": order.symbol,
            "side": order.side.value,
            "type": order.type.value,
            "qty": float(order.qty) if order.qty else None,
            "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
            "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
            "limit_price": float(order.limit_price) if order.limit_price else None,
            "stop_price": float(order.stop_price) if order.stop_price else None,
            "trail_percent": float(order.trail_percent) if order.trail_percent else None,
            "trail_price": float(order.trail_price) if order.trail_price else None,
            "status": order.status.value,
            "time_in_force": order.time_in_force.value,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "updated_at": order.updated_at.isoformat() if order.updated_at else None,
            "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
            "filled_at": order.filled_at.isoformat() if order.filled_at else None,
            "cancelled_at": order.cancelled_at.isoformat() if order.cancelled_at else None,
            "expired_at": order.expired_at.isoformat() if order.expired_at else None,
        }

    def _format_position(self, position) -> dict[str, Any]:
        """Format position object to dictionary."""
        return {
            "symbol": position.symbol,
            "qty": float(position.qty),
            "side": "long" if float(position.qty) > 0 else "short",
            "avg_entry_price": float(position.avg_entry_price),
            "market_value": float(position.market_value),
            "cost_basis": float(position.cost_basis),
            "unrealized_pl": float(position.unrealized_pl),
            "unrealized_plpc": float(position.unrealized_plpc),
            "unrealized_intraday_pl": float(position.unrealized_intraday_pl),
            "unrealized_intraday_plpc": float(position.unrealized_intraday_plpc),
            "current_price": float(position.current_price),
            "lastday_price": float(position.lastday_price),
            "change_today": float(position.change_today),
        }


def create_broker(
    api_key: str,
    api_secret: str,
    paper: bool = True
) -> AlpacaBroker:
    """
    Factory function to create an Alpaca broker instance.

    Args:
        api_key: Alpaca API key
        api_secret: Alpaca API secret
        paper: Use paper trading (default True)

    Returns:
        AlpacaBroker instance
    """
    mode = BrokerMode.PAPER if paper else BrokerMode.LIVE
    return AlpacaBroker(api_key, api_secret, mode)
