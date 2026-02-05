import { describe, it, expect } from 'vitest';
import { cn, formatCurrency, formatPercent, formatNumber, formatDate } from '@/lib/utils';

// =============================================================================
// cn (className merger) Tests
// =============================================================================
describe('cn utility', () => {
  it('should merge class names correctly', () => {
    expect(cn('foo', 'bar')).toBe('foo bar');
  });

  it('should handle conditional classes', () => {
    expect(cn('foo', false && 'bar', 'baz')).toBe('foo baz');
  });

  it('should handle undefined and null values', () => {
    expect(cn('foo', undefined, null, 'bar')).toBe('foo bar');
  });

  it('should merge tailwind classes correctly', () => {
    expect(cn('px-4 py-2', 'px-6')).toBe('py-2 px-6');
  });

  it('should handle array of classes', () => {
    expect(cn(['foo', 'bar'], 'baz')).toBe('foo bar baz');
  });

  it('should handle object syntax', () => {
    expect(cn({ foo: true, bar: false, baz: true })).toBe('foo baz');
  });
});

// =============================================================================
// formatCurrency Tests
// =============================================================================
describe('formatCurrency', () => {
  it('should format positive numbers correctly', () => {
    expect(formatCurrency(1234.56)).toBe('$1,234.56');
  });

  it('should format negative numbers correctly', () => {
    expect(formatCurrency(-1234.56)).toBe('-$1,234.56');
  });

  it('should format zero correctly', () => {
    expect(formatCurrency(0)).toBe('$0.00');
  });

  it('should format large numbers correctly', () => {
    expect(formatCurrency(1234567.89)).toBe('$1,234,567.89');
  });

  it('should handle whole numbers', () => {
    expect(formatCurrency(1000)).toBe('$1,000.00');
  });
});

// =============================================================================
// formatPercent Tests
// =============================================================================
describe('formatPercent', () => {
  it('should format positive percentages correctly', () => {
    expect(formatPercent(12.34)).toBe('+12.34%');
  });

  it('should format negative percentages correctly', () => {
    expect(formatPercent(-5.67)).toBe('-5.67%');
  });

  it('should format zero correctly', () => {
    expect(formatPercent(0)).toBe('0.00%');
  });

  it('should handle small decimals', () => {
    expect(formatPercent(0.12)).toBe('+0.12%');
  });
});

// =============================================================================
// formatNumber Tests
// =============================================================================
describe('formatNumber', () => {
  it('should format numbers with commas', () => {
    expect(formatNumber(1234567)).toBe('1,234,567');
  });

  it('should format decimal numbers', () => {
    expect(formatNumber(1234.56)).toBe('1,234.56');
  });

  it('should format zero', () => {
    expect(formatNumber(0)).toBe('0');
  });

  it('should format negative numbers', () => {
    expect(formatNumber(-1234)).toBe('-1,234');
  });
});

// =============================================================================
// formatDate Tests
// =============================================================================
describe('formatDate', () => {
  it('should format ISO date string correctly', () => {
    const date = '2024-02-15T10:30:00Z';
    const result = formatDate(date);
    expect(result).toContain('Feb');
    expect(result).toContain('15');
    expect(result).toContain('2024');
  });

  it('should format Date object correctly', () => {
    const date = new Date('2024-02-15T10:30:00Z');
    const result = formatDate(date);
    expect(result).toContain('Feb');
    expect(result).toContain('15');
  });

  it('should handle different date formats', () => {
    const date = new Date(2024, 0, 1); // Jan 1, 2024
    const result = formatDate(date);
    expect(result).toContain('Jan');
    expect(result).toContain('1');
    expect(result).toContain('2024');
  });
});
