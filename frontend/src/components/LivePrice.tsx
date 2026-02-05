'use client';

import { useSymbolPrice } from '@/hooks/useMarketData';
import { cn } from '@/lib/utils';

interface LivePriceProps {
  symbol: string;
  showChange?: boolean;
  showBidAsk?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

/**
 * LivePrice component displays real-time price for a stock symbol.
 * Automatically subscribes to WebSocket updates.
 */
export function LivePrice({
  symbol,
  showChange = true,
  showBidAsk = false,
  size = 'md',
  className,
}: LivePriceProps) {
  const {
    price,
    bidPrice,
    askPrice,
    change,
    changePercent,
    lastUpdate,
    isConnected,
  } = useSymbolPrice(symbol);

  const sizeClasses = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-xl font-semibold',
  };

  const formatPrice = (value: number | null) => {
    if (value === null) return '--';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  const formatChange = (value: number | null) => {
    if (value === null) return '--';
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(2)}`;
  };

  const formatPercent = (value: number | null) => {
    if (value === null) return '--';
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(2)}%`;
  };

  const isPositive = (change ?? 0) >= 0;

  return (
    <div className={cn('font-mono', sizeClasses[size], className)}>
      {/* Main price */}
      <div className="flex items-center gap-2">
        <span className="text-white">{formatPrice(price)}</span>

        {/* Connection indicator */}
        {!isConnected && (
          <span className="inline-block w-2 h-2 rounded-full bg-yellow-500" title="Connecting..." />
        )}
        {isConnected && price !== null && (
          <span className="inline-block w-2 h-2 rounded-full bg-green-500 animate-pulse" title="Live" />
        )}
      </div>

      {/* Change */}
      {showChange && (
        <div
          className={cn(
            'text-sm',
            isPositive ? 'text-green-400' : 'text-red-400'
          )}
        >
          {formatChange(change)} ({formatPercent(changePercent)})
        </div>
      )}

      {/* Bid/Ask */}
      {showBidAsk && (
        <div className="text-xs text-gray-400 mt-1">
          <span>Bid: {formatPrice(bidPrice)}</span>
          <span className="mx-2">|</span>
          <span>Ask: {formatPrice(askPrice)}</span>
        </div>
      )}
    </div>
  );
}

/**
 * LivePriceInline - Compact inline version for tables/lists
 */
export function LivePriceInline({
  symbol,
  showChange = true,
  className,
}: {
  symbol: string;
  showChange?: boolean;
  className?: string;
}) {
  const { price, changePercent, isConnected } = useSymbolPrice(symbol);

  const formatPrice = (value: number | null) => {
    if (value === null) return '--';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(value);
  };

  const isPositive = (changePercent ?? 0) >= 0;

  return (
    <span className={cn('font-mono inline-flex items-center gap-2', className)}>
      <span className="text-white">{formatPrice(price)}</span>
      {showChange && changePercent !== null && (
        <span
          className={cn(
            'text-xs',
            isPositive ? 'text-green-400' : 'text-red-400'
          )}
        >
          {isPositive ? '+' : ''}
          {changePercent.toFixed(2)}%
        </span>
      )}
      {isConnected && price !== null && (
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500" />
      )}
    </span>
  );
}

/**
 * ConnectionStatus - Shows WebSocket connection status
 */
export function ConnectionStatus({ className }: { className?: string }) {
  const { isConnected } = useSymbolPrice('');

  return (
    <div className={cn('flex items-center gap-2 text-sm', className)}>
      <span
        className={cn(
          'w-2 h-2 rounded-full',
          isConnected ? 'bg-green-500' : 'bg-yellow-500'
        )}
      />
      <span className="text-gray-400">
        {isConnected ? 'Live' : 'Connecting...'}
      </span>
    </div>
  );
}
