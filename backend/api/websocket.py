"""
WebSocket API for Real-Time Market Data

Relays Alpaca WebSocket stream data to frontend clients.
Supports subscription management per client connection.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel

from data.alpaca_stream import (
    AlpacaStreamClient,
    get_price_cache,
    get_stream_client,
    init_stream_client,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Connection Manager
# =============================================================================

class ConnectionManager:
    """
    Manages WebSocket connections and subscriptions.
    Routes real-time data to appropriate clients based on their subscriptions.
    """

    def __init__(self):
        # Map of connection_id -> WebSocket
        self._connections: dict[str, WebSocket] = {}
        # Map of connection_id -> set of subscribed symbols
        self._subscriptions: dict[str, set[str]] = {}
        # Map of symbol -> set of connection_ids subscribed to it
        self._symbol_subscribers: dict[str, set[str]] = {}
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        # Connection counter for unique IDs
        self._connection_counter = 0

    async def connect(self, websocket: WebSocket) -> str:
        """Accept a new WebSocket connection and return connection ID."""
        await websocket.accept()

        async with self._lock:
            self._connection_counter += 1
            connection_id = f"conn_{self._connection_counter}"
            self._connections[connection_id] = websocket
            self._subscriptions[connection_id] = set()

        logger.info(f"Client connected: {connection_id}")
        return connection_id

    async def disconnect(self, connection_id: str):
        """Remove a WebSocket connection and clean up subscriptions."""
        async with self._lock:
            if connection_id in self._connections:
                del self._connections[connection_id]

            # Clean up subscriptions
            if connection_id in self._subscriptions:
                symbols = self._subscriptions[connection_id]
                for symbol in symbols:
                    if symbol in self._symbol_subscribers:
                        self._symbol_subscribers[symbol].discard(connection_id)
                        if not self._symbol_subscribers[symbol]:
                            del self._symbol_subscribers[symbol]
                del self._subscriptions[connection_id]

        logger.info(f"Client disconnected: {connection_id}")

    async def subscribe(self, connection_id: str, symbols: list[str]):
        """Subscribe a connection to symbols."""
        symbols = [s.upper() for s in symbols]

        async with self._lock:
            if connection_id not in self._subscriptions:
                return

            for symbol in symbols:
                self._subscriptions[connection_id].add(symbol)
                if symbol not in self._symbol_subscribers:
                    self._symbol_subscribers[symbol] = set()
                self._symbol_subscribers[symbol].add(connection_id)

        logger.debug(f"Client {connection_id} subscribed to {symbols}")

    async def unsubscribe(self, connection_id: str, symbols: list[str]):
        """Unsubscribe a connection from symbols."""
        symbols = [s.upper() for s in symbols]

        async with self._lock:
            if connection_id not in self._subscriptions:
                return

            for symbol in symbols:
                self._subscriptions[connection_id].discard(symbol)
                if symbol in self._symbol_subscribers:
                    self._symbol_subscribers[symbol].discard(connection_id)
                    if not self._symbol_subscribers[symbol]:
                        del self._symbol_subscribers[symbol]

        logger.debug(f"Client {connection_id} unsubscribed from {symbols}")

    async def broadcast_to_symbol(self, symbol: str, data: dict):
        """Send data to all clients subscribed to a symbol."""
        symbol = symbol.upper()

        async with self._lock:
            subscribers = self._symbol_subscribers.get(symbol, set()).copy()
            connections = {
                conn_id: self._connections[conn_id]
                for conn_id in subscribers
                if conn_id in self._connections
            }

        # Send to all subscribers outside the lock
        for connection_id, websocket in connections.items():
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.error(f"Error sending to {connection_id}: {e}")
                # Don't disconnect here, let the receive loop handle it

    async def send_to_connection(self, connection_id: str, data: dict):
        """Send data to a specific connection."""
        async with self._lock:
            websocket = self._connections.get(connection_id)

        if websocket:
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.error(f"Error sending to {connection_id}: {e}")

    def get_all_subscribed_symbols(self) -> set[str]:
        """Get all symbols that have at least one subscriber."""
        return set(self._symbol_subscribers.keys())

    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self._connections)


# Global connection manager
manager = ConnectionManager()


# =============================================================================
# Alpaca Stream Integration
# =============================================================================

async def on_quote_update(quote: dict):
    """Handle quote update from Alpaca stream."""
    symbol = quote.get("symbol")
    if symbol:
        # Broadcast to subscribed clients
        message = {
            "type": "quote",
            "symbol": symbol,
            "data": quote,
            "timestamp": datetime.utcnow().isoformat()
        }
        await manager.broadcast_to_symbol(symbol, message)


async def on_trade_update(trade: dict):
    """Handle trade update from Alpaca stream."""
    symbol = trade.get("symbol")
    if symbol:
        # Broadcast to subscribed clients
        message = {
            "type": "trade",
            "symbol": symbol,
            "data": trade,
            "timestamp": datetime.utcnow().isoformat()
        }
        await manager.broadcast_to_symbol(symbol, message)


async def setup_alpaca_stream():
    """Initialize and start the Alpaca stream client."""
    stream_client = await init_stream_client()

    # Register callbacks for broadcasting
    stream_client.on_quote(on_quote_update)
    stream_client.on_trade(on_trade_update)

    # Start the stream client
    await stream_client.start()

    logger.info("Alpaca stream client started")
    return stream_client


# =============================================================================
# WebSocket Endpoint
# =============================================================================

@router.websocket("/ws/market")
async def market_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time market data.

    Client messages:
    - {"action": "subscribe", "symbols": ["AAPL", "MSFT"]}
    - {"action": "unsubscribe", "symbols": ["AAPL"]}
    - {"action": "get_price", "symbol": "AAPL"}
    - {"action": "get_snapshot", "symbol": "AAPL"}
    - {"action": "ping"}

    Server messages:
    - {"type": "quote", "symbol": "AAPL", "data": {...}}
    - {"type": "trade", "symbol": "AAPL", "data": {...}}
    - {"type": "price", "symbol": "AAPL", "price": 150.25}
    - {"type": "snapshot", "symbol": "AAPL", "data": {...}}
    - {"type": "subscribed", "symbols": ["AAPL", "MSFT"]}
    - {"type": "unsubscribed", "symbols": ["AAPL"]}
    - {"type": "error", "message": "..."}
    - {"type": "pong"}
    """
    connection_id = await manager.connect(websocket)

    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "connection_id": connection_id,
            "timestamp": datetime.utcnow().isoformat()
        })

        while True:
            # Receive message from client
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                action = message.get("action")

                if action == "subscribe":
                    symbols = message.get("symbols", [])
                    if symbols:
                        await manager.subscribe(connection_id, symbols)

                        # Also subscribe to Alpaca stream if not already
                        stream_client = get_stream_client()
                        if stream_client:
                            await stream_client.subscribe(symbols)

                        await websocket.send_json({
                            "type": "subscribed",
                            "symbols": symbols
                        })

                elif action == "unsubscribe":
                    symbols = message.get("symbols", [])
                    if symbols:
                        await manager.unsubscribe(connection_id, symbols)
                        await websocket.send_json({
                            "type": "unsubscribed",
                            "symbols": symbols
                        })

                elif action == "get_price":
                    symbol = message.get("symbol", "").upper()
                    price_cache = get_price_cache()
                    price = await price_cache.get_price(symbol)

                    await websocket.send_json({
                        "type": "price",
                        "symbol": symbol,
                        "price": price,
                        "timestamp": datetime.utcnow().isoformat()
                    })

                elif action == "get_snapshot":
                    symbol = message.get("symbol", "").upper()
                    price_cache = get_price_cache()
                    snapshot = await price_cache.get_snapshot(symbol)

                    await websocket.send_json({
                        "type": "snapshot",
                        "symbol": symbol,
                        "data": snapshot,
                        "timestamp": datetime.utcnow().isoformat()
                    })

                elif action == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown action: {action}"
                    })

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON"
                })

    except WebSocketDisconnect:
        logger.info(f"Client {connection_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for {connection_id}: {e}")
    finally:
        await manager.disconnect(connection_id)


@router.get("/ws/status")
async def websocket_status():
    """Get WebSocket server status."""
    stream_client = get_stream_client()
    price_cache = get_price_cache()

    return {
        "connected_clients": manager.get_connection_count(),
        "subscribed_symbols": list(manager.get_all_subscribed_symbols()),
        "alpaca_stream_connected": stream_client is not None and stream_client._running if stream_client else False,
        "cached_prices": len(await price_cache.get_all_prices()),
        "timestamp": datetime.utcnow().isoformat()
    }
