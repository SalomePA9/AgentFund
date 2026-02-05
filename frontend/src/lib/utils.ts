/**
 * Utility functions for AgentFund frontend
 */

import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge Tailwind CSS classes with clsx
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * Format a number as currency (USD)
 */
export function formatCurrency(
  value: number | null | undefined,
  options?: { decimals?: number; showSign?: boolean }
): string {
  if (value === null || value === undefined) {
    return '-';
  }

  const { decimals = 2, showSign = false } = options || {};
  const sign = showSign && value > 0 ? '+' : '';

  return `${sign}$${value.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}

/**
 * Format a number as percentage
 */
export function formatPercent(
  value: number | null | undefined,
  options?: { decimals?: number; showSign?: boolean }
): string {
  if (value === null || value === undefined) {
    return '-';
  }

  const { decimals = 2, showSign = true } = options || {};
  const sign = showSign && value > 0 ? '+' : '';

  return `${sign}${value.toFixed(decimals)}%`;
}

/**
 * Format a number with locale-specific separators
 */
export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '-';
  }
  return value.toLocaleString('en-US');
}

/**
 * Format a large number with abbreviations (K, M, B)
 */
export function formatCompactNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '-';
  }

  if (value >= 1_000_000_000) {
    return `${(value / 1_000_000_000).toFixed(1)}B`;
  }
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1)}K`;
  }

  return value.toString();
}

/**
 * Format a date string
 */
export function formatDate(
  date: string | Date | null | undefined,
  options?: { format?: 'short' | 'long' | 'relative' }
): string {
  if (!date) {
    return '-';
  }

  const d = typeof date === 'string' ? new Date(date) : date;
  const { format = 'short' } = options || {};

  if (format === 'relative') {
    return formatRelativeTime(d);
  }

  if (format === 'long') {
    return d.toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  }

  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

/**
 * Format relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(date: Date): string {
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (seconds < 60) {
    return 'just now';
  }
  if (minutes < 60) {
    return `${minutes}m ago`;
  }
  if (hours < 24) {
    return `${hours}h ago`;
  }
  if (days < 7) {
    return `${days}d ago`;
  }

  return formatDate(date);
}

/**
 * Get CSS class for positive/negative values
 */
export function getValueColorClass(
  value: number | null | undefined
): string {
  if (value === null || value === undefined) {
    return 'text-zinc-400';
  }
  if (value > 0) {
    return 'text-success';
  }
  if (value < 0) {
    return 'text-error';
  }
  return 'text-zinc-400';
}

/**
 * Calculate days remaining from a date
 */
export function daysRemaining(endDate: string | Date): number {
  const end = typeof endDate === 'string' ? new Date(endDate) : endDate;
  const now = new Date();
  const diff = end.getTime() - now.getTime();
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
}

/**
 * Capitalize first letter of each word
 */
export function capitalize(str: string): string {
  return str
    .split(' ')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

/**
 * Format strategy type for display
 */
export function formatStrategyType(strategyType: string): string {
  return strategyType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Get status badge variant
 */
export function getStatusVariant(
  status: string
): 'success' | 'warning' | 'error' | 'neutral' {
  switch (status) {
    case 'active':
      return 'success';
    case 'paused':
      return 'warning';
    case 'stopped':
    case 'completed':
      return 'neutral';
    default:
      return 'neutral';
  }
}

/**
 * Debounce function
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null;

  return (...args: Parameters<T>) => {
    if (timeout) {
      clearTimeout(timeout);
    }
    timeout = setTimeout(() => func(...args), wait);
  };
}

/**
 * Check if we're running on the client side
 */
export function isClient(): boolean {
  return typeof window !== 'undefined';
}
