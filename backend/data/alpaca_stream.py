"""
Alpaca WebSocket Client for Real-Time Market Data

Connects to Alpaca's streaming WebSocket API for real-time quotes and trades.
Free tier provides real-time data via WebSocket (API calls have 15-min delay).
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Callable

import websockets
from websockets.exceptions import ConnectionClosed

from config import settings

logger = logging.getLogger(__name__)

# Alpaca WebSocket endpoints
ALPACA_DATA_WS_URL = "wss://stream.data.alpaca.markets/v2/iex"  # Free IEX data
ALPACA_DATA_WS_URL_SIP = "wss://stream.data.alpaca.markets/v2/sip"  # Paid SIP data


class AlpacaStreamClient:
    """
    WebSocket client for Alpaca real-time market data streaming.

    Subscribes to quotes and trades for specified symbols and
    broadcasts updates to registered callbacks.
    """

    def __init__(
        self,
        api_key: str = None,
        api_secret: str = None,
        feed: str = "iex",  # "iex" (free) or "sip" (paid)
    ):
        self.api_key = api_key or settings.ALPACA_API_KEY
        self.api_secret = api_secret or settings.ALPACA_API_SECRET
        self.feed = feed
        self.ws_url = ALPACA_DATA_WS_URL if feed == "iex" else ALPACA_DATA_WS_URL_SIP

        self._ws = None
        self._running = False
        self._subscribed_symbols: set[str] = set()
        self._quote_callbacks: list[Callable] = []
        self._trade_callbacks: list[Callable] = []
        self._bar_callbacks: list[Callable] = []
        self._reconnect_delay = 1
        self._max_reconnect_delay = 60

    async def connect(self):
        """Establish WebSocket connection to Alpaca."""
        logger.info(f"Connecting to Alpaca WebSocket ({self.feed} feed)...")

        try:
            self._ws = await websockets.connect(self.ws_url)
            self._running = True

            # Wait for welcome message
            welcome = await self._ws.recv()
            welcome_data = json.loads(welcome)
            logger.info(f"Alpaca WebSocket: {welcome_data}")

            # Authenticate
            auth_msg = {
                "action": "auth",
                "key": self.api_key,
                "secret": self.api_secret,
            }
            await self._ws.send(json.dumps(auth_msg))

            # Wait for auth response
            auth_response = await self._ws.recv()
            auth_data = json.loads(auth_response)

            if auth_data[0].get("T") == "error":
                raise Exception(f"Authentication failed: {auth_data[0].get('msg')}")

            logger.info("Alpaca WebSocket authenticated successfully")
            self._reconnect_delay = 1  # Reset reconnect delay on success

            return True

        except Exception as e:
            logger.error(f"Failed to connect to Alpaca WebSocket: {e}")
            self._running = False
            return False

    async def disconnect(self):
        """Close the WebSocket connection."""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        logger.info("Disconnected from Alpaca WebSocket")

    async def subscribe(
        self,
        symbols: list[str],
        quotes: bool = True,
        trades: bool = True,
        bars: bool = False,
    ):
        """
        Subscribe to real-time data for specified symbols.

        Args:
            symbols: List of stock symbols (e.g., ["AAPL", "MSFT"])
            quotes: Subscribe to quote updates (bid/ask)
            trades: Subscribe to trade updates
            bars: Subscribe to minute bars
        """
        if not self._ws:
            raise Exception("Not connected to WebSocket")

        symbols = [s.upper() for s in symbols]

        subscribe_msg = {"action": "subscribe"}

        if quotes:
            subscribe_msg["quotes"] = symbols
        if trades:
            subscribe_msg["trades"] = symbols
        if bars:
            subscribe_msg["bars"] = symbols

        await self._ws.send(json.dumps(subscribe_msg))
        self._subscribed_symbols.update(symbols)

        logger.info(f"Subscribed to {len(symbols)} symbols: {symbols[:10]}...")

    async def unsubscribe(
        self,
        symbols: list[str],
        quotes: bool = True,
        trades: bool = True,
        bars: bool = False,
    ):
        """Unsubscribe from real-time data for specified symbols."""
        if not self._ws:
            return

        symbols = [s.upper() for s in symbols]

        unsubscribe_msg = {"action": "unsubscribe"}

        if quotes:
            unsubscribe_msg["quotes"] = symbols
        if trades:
            unsubscribe_msg["trades"] = symbols
        if bars:
            unsubscribe_msg["bars"] = symbols

        await self._ws.send(json.dumps(unsubscribe_msg))
        self._subscribed_symbols.difference_update(symbols)

        logger.info(f"Unsubscribed from {len(symbols)} symbols")

    def on_quote(self, callback: Callable):
        """Register a callback for quote updates."""
        self._quote_callbacks.append(callback)

    def on_trade(self, callback: Callable):
        """Register a callback for trade updates."""
        self._trade_callbacks.append(callback)

    def on_bar(self, callback: Callable):
        """Register a callback for bar updates."""
        self._bar_callbacks.append(callback)

    async def _handle_message(self, message: str):
        """Process incoming WebSocket message."""
        try:
            data = json.loads(message)

            for item in data:
                msg_type = item.get("T")

                if msg_type == "q":
                    # Quote update
                    quote = self._parse_quote(item)
                    for callback in self._quote_callbacks:
                        await self._safe_callback(callback, quote)

                elif msg_type == "t":
                    # Trade update
                    trade = self._parse_trade(item)
                    for callback in self._trade_callbacks:
                        await self._safe_callback(callback, trade)

                elif msg_type == "b":
                    # Bar update
                    bar = self._parse_bar(item)
                    for callback in self._bar_callbacks:
                        await self._safe_callback(callback, bar)

                elif msg_type == "subscription":
                    logger.debug(f"Subscription confirmed: {item}")

                elif msg_type == "error":
                    logger.error(f"Alpaca error: {item.get('msg')}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def _parse_quote(self, data: dict) -> dict:
        """Parse quote message into standardized format."""
        return {
            "type": "quote",
            "symbol": data.get("S"),
            "bid_price": data.get("bp"),
            "bid_size": data.get("bs"),
            "ask_price": data.get("ap"),
            "ask_size": data.get("as"),
            "timestamp": data.get("t"),
            "conditions": data.get("c", []),
            "tape": data.get("z"),
        }

    def _parse_trade(self, data: dict) -> dict:
        """Parse trade message into standardized format."""
        return {
            "type": "trade",
            "symbol": data.get("S"),
            "price": data.get("p"),
            "size": data.get("s"),
            "timestamp": data.get("t"),
            "conditions": data.get("c", []),
            "trade_id": data.get("i"),
            "tape": data.get("z"),
        }

    def _parse_bar(self, data: dict) -> dict:
        """Parse bar message into standardized format."""
        return {
            "type": "bar",
            "symbol": data.get("S"),
            "open": data.get("o"),
            "high": data.get("h"),
            "low": data.get("l"),
            "close": data.get("c"),
            "volume": data.get("v"),
            "timestamp": data.get("t"),
            "vwap": data.get("vw"),
            "trade_count": data.get("n"),
        }

    async def _safe_callback(self, callback: Callable, data: dict):
        """Safely execute callback, handling both sync and async functions."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(data)
            else:
                callback(data)
        except Exception as e:
            logger.error(f"Callback error: {e}")

    async def run(self):
        """Main loop to receive and process messages."""
        while self._running:
            try:
                if not self._ws:
                    connected = await self.connect()
                    if not connected:
                        await asyncio.sleep(self._reconnect_delay)
                        self._reconnect_delay = min(
                            self._reconnect_delay * 2, self._max_reconnect_delay
                        )
                        continue

                    # Resubscribe to symbols after reconnection
                    if self._subscribed_symbols:
                        await self.subscribe(list(self._subscribed_symbols))

                message = await self._ws.recv()
                await self._handle_message(message)

            except ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
                self._ws = None
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, self._max_reconnect_delay
                )

            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await asyncio.sleep(1)

    async def start(self):
        """Start the WebSocket client in the background."""
        asyncio.create_task(self.run())

    async def stop(self):
        """Stop the WebSocket client."""
        await self.disconnect()


# =============================================================================
# Price Cache - Stores latest prices from WebSocket stream
# =============================================================================


class RealTimePriceCache:
    """
    In-memory cache for real-time prices from WebSocket stream.
    Thread-safe and provides latest quote/trade data.
    """

    def __init__(self):
        self._quotes: dict[str, dict] = {}
        self._trades: dict[str, dict] = {}
        self._last_update: dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    async def update_quote(self, quote: dict):
        """Update cached quote for a symbol."""
        symbol = quote.get("symbol")
        if symbol:
            async with self._lock:
                self._quotes[symbol] = quote
                self._last_update[symbol] = datetime.utcnow()

    async def update_trade(self, trade: dict):
        """Update cached trade for a symbol."""
        symbol = trade.get("symbol")
        if symbol:
            async with self._lock:
                self._trades[symbol] = trade
                self._last_update[symbol] = datetime.utcnow()

    async def get_quote(self, symbol: str) -> dict | None:
        """Get latest quote for a symbol."""
        async with self._lock:
            return self._quotes.get(symbol.upper())

    async def get_trade(self, symbol: str) -> dict | None:
        """Get latest trade for a symbol."""
        async with self._lock:
            return self._trades.get(symbol.upper())

    async def get_price(self, symbol: str) -> float | None:
        """Get latest price (from trade or quote midpoint)."""
        symbol = symbol.upper()

        async with self._lock:
            # Prefer last trade price
            trade = self._trades.get(symbol)
            if trade and trade.get("price"):
                return trade["price"]

            # Fall back to quote midpoint
            quote = self._quotes.get(symbol)
            if quote:
                bid = quote.get("bid_price")
                ask = quote.get("ask_price")
                if bid and ask:
                    return (bid + ask) / 2

            return None

    async def get_all_prices(self) -> dict[str, float]:
        """Get all cached prices."""
        prices = {}
        async with self._lock:
            for symbol in set(self._trades.keys()) | set(self._quotes.keys()):
                trade = self._trades.get(symbol)
                if trade and trade.get("price"):
                    prices[symbol] = trade["price"]
                else:
                    quote = self._quotes.get(symbol)
                    if quote:
                        bid = quote.get("bid_price")
                        ask = quote.get("ask_price")
                        if bid and ask:
                            prices[symbol] = (bid + ask) / 2
        return prices

    async def get_snapshot(self, symbol: str) -> dict | None:
        """Get full snapshot (quote + trade) for a symbol."""
        symbol = symbol.upper()
        async with self._lock:
            quote = self._quotes.get(symbol)
            trade = self._trades.get(symbol)
            last_update = self._last_update.get(symbol)

            if not quote and not trade:
                return None

            return {
                "symbol": symbol,
                "quote": quote,
                "trade": trade,
                "price": trade.get("price") if trade else None,
                "bid_price": quote.get("bid_price") if quote else None,
                "ask_price": quote.get("ask_price") if quote else None,
                "last_update": last_update.isoformat() if last_update else None,
            }

    def clear(self):
        """Clear all cached data."""
        self._quotes.clear()
        self._trades.clear()
        self._last_update.clear()


# =============================================================================
# Global instances
# =============================================================================

# Global price cache instance
price_cache = RealTimePriceCache()

# Global stream client instance (initialized on startup)
stream_client: AlpacaStreamClient | None = None


async def init_stream_client(
    api_key: str = None, api_secret: str = None
) -> AlpacaStreamClient:
    """Initialize the global stream client."""
    global stream_client

    stream_client = AlpacaStreamClient(api_key=api_key, api_secret=api_secret)

    # Register callbacks to update price cache
    stream_client.on_quote(price_cache.update_quote)
    stream_client.on_trade(price_cache.update_trade)

    return stream_client


def get_stream_client() -> AlpacaStreamClient | None:
    """Get the global stream client instance."""
    return stream_client


def get_price_cache() -> RealTimePriceCache:
    """Get the global price cache instance."""
    return price_cache
