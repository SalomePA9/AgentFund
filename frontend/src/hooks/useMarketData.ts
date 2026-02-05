'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { getMarketWebSocket, Quote, Trade, PriceUpdate } from '@/lib/websocket';

/**
 * Real-time price data for a symbol
 */
export interface RealTimePrice {
  symbol: string;
  price: number | null;
  bidPrice: number | null;
  askPrice: number | null;
  lastTradePrice: number | null;
  lastTradeSize: number | null;
  change: number | null;
  changePercent: number | null;
  lastUpdate: Date | null;
}

/**
 * Hook for subscribing to real-time market data for multiple symbols
 */
export function useMarketData(symbols: string[]) {
  const [prices, setPrices] = useState<Map<string, RealTimePrice>>(new Map());
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const previousPrices = useRef<Map<string, number>>(new Map());

  // Initialize prices for symbols
  useEffect(() => {
    setPrices((prev) => {
      const updated = new Map(prev);
      let hasChanges = false;
      symbols.forEach((symbol) => {
        const upperSymbol = symbol.toUpperCase();
        if (!updated.has(upperSymbol)) {
          updated.set(upperSymbol, {
            symbol: upperSymbol,
            price: null,
            bidPrice: null,
            askPrice: null,
            lastTradePrice: null,
            lastTradeSize: null,
            change: null,
            changePercent: null,
            lastUpdate: null,
          });
          hasChanges = true;
        }
      });
      return hasChanges ? updated : prev;
    });
  }, [symbols]);

  // Handle quote updates
  const handleQuote = useCallback((message: any) => {
    if (message.type !== 'quote') return;

    const data = message.data as Quote;
    const symbol = data.symbol;

    setPrices((prev) => {
      const current = prev.get(symbol) || {
        symbol,
        price: null,
        bidPrice: null,
        askPrice: null,
        lastTradePrice: null,
        lastTradeSize: null,
        change: null,
        changePercent: null,
        lastUpdate: null,
      };

      const midPrice =
        data.bid_price && data.ask_price
          ? (data.bid_price + data.ask_price) / 2
          : current.price;

      // Calculate change from previous price
      const prevPrice = previousPrices.current.get(symbol);
      let change = current.change;
      let changePercent = current.changePercent;

      if (midPrice && prevPrice) {
        change = midPrice - prevPrice;
        changePercent = (change / prevPrice) * 100;
      }

      if (midPrice) {
        previousPrices.current.set(symbol, midPrice);
      }

      const updated = new Map(prev);
      updated.set(symbol, {
        ...current,
        bidPrice: data.bid_price,
        askPrice: data.ask_price,
        price: midPrice,
        change,
        changePercent,
        lastUpdate: new Date(),
      });

      return updated;
    });
  }, []);

  // Handle trade updates
  const handleTrade = useCallback((message: any) => {
    if (message.type !== 'trade') return;

    const data = message.data as Trade;
    const symbol = data.symbol;

    setPrices((prev) => {
      const current = prev.get(symbol) || {
        symbol,
        price: null,
        bidPrice: null,
        askPrice: null,
        lastTradePrice: null,
        lastTradeSize: null,
        change: null,
        changePercent: null,
        lastUpdate: null,
      };

      // Calculate change from previous price
      const prevPrice = previousPrices.current.get(symbol);
      let change = current.change;
      let changePercent = current.changePercent;

      if (data.price && prevPrice) {
        change = data.price - prevPrice;
        changePercent = (change / prevPrice) * 100;
      }

      if (data.price) {
        previousPrices.current.set(symbol, data.price);
      }

      const updated = new Map(prev);
      updated.set(symbol, {
        ...current,
        price: data.price,
        lastTradePrice: data.price,
        lastTradeSize: data.size,
        change,
        changePercent,
        lastUpdate: new Date(),
      });

      return updated;
    });
  }, []);

  // Connect to WebSocket and subscribe to symbols
  useEffect(() => {
    if (symbols.length === 0) return;

    const ws = getMarketWebSocket();

    const connect = async () => {
      try {
        await ws.connect();
        setIsConnected(true);
        setError(null);

        // Subscribe to symbols
        ws.subscribe(symbols);

        // Register handlers
        ws.on('quote', handleQuote);
        ws.on('trade', handleTrade);
      } catch (err) {
        setError(err as Error);
        setIsConnected(false);
      }
    };

    connect();

    // Cleanup on unmount or symbols change
    return () => {
      ws.off('quote', handleQuote);
      ws.off('trade', handleTrade);
      // Note: We don't disconnect here as other components may be using the connection
      // The connection is managed by the singleton
    };
  }, [symbols, handleQuote, handleTrade]);

  // Get price for a specific symbol
  const getPrice = useCallback(
    (symbol: string): RealTimePrice | undefined => {
      return prices.get(symbol.toUpperCase());
    },
    [prices]
  );

  return {
    prices,
    getPrice,
    isConnected,
    error,
  };
}

/**
 * Hook for subscribing to real-time data for a single symbol
 */
export function useSymbolPrice(symbol: string) {
  const { prices, isConnected, error } = useMarketData([symbol]);

  const price = prices.get(symbol.toUpperCase());

  return {
    price: price?.price ?? null,
    bidPrice: price?.bidPrice ?? null,
    askPrice: price?.askPrice ?? null,
    lastTradePrice: price?.lastTradePrice ?? null,
    change: price?.change ?? null,
    changePercent: price?.changePercent ?? null,
    lastUpdate: price?.lastUpdate ?? null,
    isConnected,
    error,
  };
}

/**
 * Hook for just the connection state (no subscriptions)
 */
export function useMarketConnection() {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionId, setConnectionId] = useState<string | null>(null);

  useEffect(() => {
    const ws = getMarketWebSocket();

    const handleConnected = (message: any) => {
      if (message.type === 'connected') {
        setIsConnected(true);
        setConnectionId(message.connection_id);
      }
    };

    const handlePong = () => {
      setIsConnected(true);
    };

    ws.on('connected', handleConnected);
    ws.on('pong', handlePong);

    // Check connection status periodically
    const interval = setInterval(() => {
      const state = ws.getState();
      setIsConnected(state.connected);
      setConnectionId(state.connectionId);

      // Send ping to keep connection alive
      if (state.connected) {
        ws.ping();
      }
    }, 30000);

    return () => {
      ws.off('connected', handleConnected);
      ws.off('pong', handlePong);
      clearInterval(interval);
    };
  }, []);

  return { isConnected, connectionId };
}
