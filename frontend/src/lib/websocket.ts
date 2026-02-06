/**
 * WebSocket Client for Real-Time Market Data
 *
 * Connects to the backend WebSocket server which relays
 * Alpaca's real-time market data stream.
 */

type MessageHandler = (data: any) => void;

export interface Quote {
  type: 'quote';
  symbol: string;
  bid_price: number;
  bid_size: number;
  ask_price: number;
  ask_size: number;
  timestamp: string;
}

export interface Trade {
  type: 'trade';
  symbol: string;
  price: number;
  size: number;
  timestamp: string;
}

export interface PriceUpdate {
  type: 'quote' | 'trade';
  symbol: string;
  data: Quote | Trade;
  timestamp: string;
}

export interface ConnectionState {
  connected: boolean;
  connectionId: string | null;
  subscribedSymbols: string[];
}

class MarketWebSocket {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000;
  private maxReconnectDelay = 30000;
  private messageHandlers: Map<string, Set<MessageHandler>> = new Map();
  private subscribedSymbols: Set<string> = new Set();
  private connectionId: string | null = null;
  private isConnecting = false;

  constructor(url?: string) {
    this.url = url || this.getDefaultUrl();
  }

  private getDefaultUrl(): string {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const wsProtocol = apiUrl.startsWith('https') ? 'wss' : 'ws';
    const host = apiUrl.replace(/^https?:\/\//, '');
    return `${wsProtocol}://${host}/api/ws/market`;
  }

  /**
   * Connect to the WebSocket server
   */
  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      if (this.isConnecting) {
        // Wait for existing connection attempt
        const checkConnection = setInterval(() => {
          if (this.ws?.readyState === WebSocket.OPEN) {
            clearInterval(checkConnection);
            resolve();
          }
        }, 100);
        return;
      }

      this.isConnecting = true;

      try {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          console.log('[WebSocket] Connected to market data stream');
          this.reconnectAttempts = 0;
          this.reconnectDelay = 1000;
          this.isConnecting = false;

          // Resubscribe to symbols after reconnection
          if (this.subscribedSymbols.size > 0) {
            this.subscribe(Array.from(this.subscribedSymbols));
          }

          resolve();
        };

        this.ws.onclose = (event) => {
          console.log(`[WebSocket] Connection closed: ${event.code} ${event.reason}`);
          this.connectionId = null;
          this.isConnecting = false;
          this.handleReconnect();
        };

        this.ws.onerror = (error) => {
          console.error('[WebSocket] Error:', error);
          this.isConnecting = false;
          reject(error);
        };

        this.ws.onmessage = (event) => {
          this.handleMessage(event.data);
        };
      } catch (error) {
        this.isConnecting = false;
        reject(error);
      }
    });
  }

  /**
   * Disconnect from the WebSocket server
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.connectionId = null;
    this.subscribedSymbols.clear();
  }

  /**
   * Subscribe to real-time data for symbols
   */
  subscribe(symbols: string[]): void {
    symbols.forEach((s) => this.subscribedSymbols.add(s.toUpperCase()));

    if (this.ws?.readyState === WebSocket.OPEN) {
      this.send({
        action: 'subscribe',
        symbols: symbols.map((s) => s.toUpperCase()),
      });
    }
  }

  /**
   * Unsubscribe from real-time data for symbols
   */
  unsubscribe(symbols: string[]): void {
    symbols.forEach((s) => this.subscribedSymbols.delete(s.toUpperCase()));

    if (this.ws?.readyState === WebSocket.OPEN) {
      this.send({
        action: 'unsubscribe',
        symbols: symbols.map((s) => s.toUpperCase()),
      });
    }
  }

  /**
   * Get current price for a symbol from cache
   */
  async getPrice(symbol: string): Promise<number | null> {
    return new Promise((resolve) => {
      if (this.ws?.readyState !== WebSocket.OPEN) {
        resolve(null);
        return;
      }

      const handler = (data: any) => {
        if (data.type === 'price' && data.symbol === symbol.toUpperCase()) {
          this.off('price', handler);
          resolve(data.price);
        }
      };

      this.on('price', handler);
      this.send({ action: 'get_price', symbol: symbol.toUpperCase() });

      // Timeout after 5 seconds
      setTimeout(() => {
        this.off('price', handler);
        resolve(null);
      }, 5000);
    });
  }

  /**
   * Get snapshot (quote + trade) for a symbol
   */
  async getSnapshot(symbol: string): Promise<any | null> {
    return new Promise((resolve) => {
      if (this.ws?.readyState !== WebSocket.OPEN) {
        resolve(null);
        return;
      }

      const handler = (data: any) => {
        if (data.type === 'snapshot' && data.symbol === symbol.toUpperCase()) {
          this.off('snapshot', handler);
          resolve(data.data);
        }
      };

      this.on('snapshot', handler);
      this.send({ action: 'get_snapshot', symbol: symbol.toUpperCase() });

      // Timeout after 5 seconds
      setTimeout(() => {
        this.off('snapshot', handler);
        resolve(null);
      }, 5000);
    });
  }

  /**
   * Send ping to keep connection alive
   */
  ping(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.send({ action: 'ping' });
    }
  }

  /**
   * Register a message handler for a specific message type
   */
  on(type: string, handler: MessageHandler): void {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, new Set());
    }
    this.messageHandlers.get(type)!.add(handler);
  }

  /**
   * Remove a message handler
   */
  off(type: string, handler: MessageHandler): void {
    this.messageHandlers.get(type)?.delete(handler);
  }

  /**
   * Get current connection state
   */
  getState(): ConnectionState {
    return {
      connected: this.ws?.readyState === WebSocket.OPEN,
      connectionId: this.connectionId,
      subscribedSymbols: Array.from(this.subscribedSymbols),
    };
  }

  private send(data: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  private handleMessage(data: string): void {
    try {
      const message = JSON.parse(data);
      const type = message.type;

      // Handle connection message
      if (type === 'connected') {
        this.connectionId = message.connection_id;
      }

      // Dispatch to registered handlers
      const handlers = this.messageHandlers.get(type);
      if (handlers) {
        handlers.forEach((handler) => handler(message));
      }

      // Also dispatch to 'all' handlers
      const allHandlers = this.messageHandlers.get('all');
      if (allHandlers) {
        allHandlers.forEach((handler) => handler(message));
      }
    } catch (error) {
      console.error('[WebSocket] Failed to parse message:', error);
    }
  }

  private handleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WebSocket] Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
      this.maxReconnectDelay
    );

    console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

    setTimeout(() => {
      this.connect().catch((error) => {
        console.error('[WebSocket] Reconnection failed:', error);
      });
    }, delay);
  }
}

// Singleton instance
let marketWsInstance: MarketWebSocket | null = null;

/**
 * Get the singleton MarketWebSocket instance
 */
export function getMarketWebSocket(): MarketWebSocket {
  if (!marketWsInstance) {
    marketWsInstance = new MarketWebSocket();
  }
  return marketWsInstance;
}

/**
 * Create a new MarketWebSocket instance (for testing or custom URLs)
 */
export function createMarketWebSocket(url?: string): MarketWebSocket {
  return new MarketWebSocket(url);
}

export { MarketWebSocket };
