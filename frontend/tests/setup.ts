import '@testing-library/jest-dom';
import { cleanup } from '@testing-library/react';
import { afterEach, beforeAll, afterAll, vi } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

// =============================================================================
// Mock Next.js Router
// =============================================================================
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({}),
}));

// =============================================================================
// Mock Supabase Client
// =============================================================================
vi.mock('@supabase/supabase-js', () => ({
  createClient: vi.fn(() => ({
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null }, error: null }),
      getUser: vi.fn().mockResolvedValue({ data: { user: null }, error: null }),
      signInWithPassword: vi.fn(),
      signUp: vi.fn(),
      signOut: vi.fn(),
      onAuthStateChange: vi.fn(() => ({
        data: { subscription: { unsubscribe: vi.fn() } },
      })),
    },
    from: vi.fn(() => ({
      select: vi.fn().mockReturnThis(),
      insert: vi.fn().mockReturnThis(),
      update: vi.fn().mockReturnThis(),
      delete: vi.fn().mockReturnThis(),
      eq: vi.fn().mockReturnThis(),
      single: vi.fn().mockResolvedValue({ data: null, error: null }),
    })),
  })),
}));

// =============================================================================
// MSW Server Setup for API Mocking
// =============================================================================
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const handlers = [
  // Auth endpoints
  http.post(`${API_BASE_URL}/api/auth/login`, () => {
    return HttpResponse.json({
      access_token: 'mock-jwt-token',
      token_type: 'bearer',
      user: {
        id: 'user-123',
        email: 'test@example.com',
        total_capital: 100000,
        created_at: new Date().toISOString(),
      },
    });
  }),

  http.post(`${API_BASE_URL}/api/auth/register`, () => {
    return HttpResponse.json({
      id: 'user-123',
      email: 'test@example.com',
      total_capital: 0,
      created_at: new Date().toISOString(),
    });
  }),

  http.get(`${API_BASE_URL}/api/auth/me`, () => {
    return HttpResponse.json({
      id: 'user-123',
      email: 'test@example.com',
      total_capital: 100000,
      created_at: new Date().toISOString(),
    });
  }),

  // Agent endpoints
  http.get(`${API_BASE_URL}/api/agents`, () => {
    return HttpResponse.json([
      {
        id: 'agent-1',
        name: 'Growth AI',
        strategy: 'growth',
        status: 'active',
        allocated_capital: 25000,
        current_value: 26500,
        total_return: 6.0,
        win_rate: 72.5,
        created_at: new Date().toISOString(),
      },
      {
        id: 'agent-2',
        name: 'Value Hunter',
        strategy: 'value',
        status: 'paused',
        allocated_capital: 15000,
        current_value: 15750,
        total_return: 5.0,
        win_rate: 68.0,
        created_at: new Date().toISOString(),
      },
    ]);
  }),

  http.post(`${API_BASE_URL}/api/agents`, async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({
      id: 'agent-new',
      ...body,
      status: 'active',
      current_value: body.allocated_capital,
      total_return: 0,
      win_rate: 0,
      created_at: new Date().toISOString(),
    });
  }),

  http.get(`${API_BASE_URL}/api/agents/:agentId`, ({ params }) => {
    return HttpResponse.json({
      id: params.agentId,
      name: 'Growth AI',
      strategy: 'growth',
      status: 'active',
      allocated_capital: 25000,
      current_value: 26500,
      total_return: 6.0,
      win_rate: 72.5,
      created_at: new Date().toISOString(),
    });
  }),

  // Market data endpoints
  http.get(`${API_BASE_URL}/api/market/stocks/:symbol`, ({ params }) => {
    return HttpResponse.json({
      symbol: params.symbol,
      name: 'Apple Inc.',
      price: 185.92,
      change: 2.34,
      change_percent: 1.27,
      volume: 52000000,
      market_cap: 2890000000000,
    });
  }),

  // Reports endpoints
  http.get(`${API_BASE_URL}/api/reports/daily`, () => {
    return HttpResponse.json({
      date: new Date().toISOString().split('T')[0],
      total_portfolio_value: 100000,
      daily_pnl: 1250,
      daily_return: 1.25,
      top_performers: [
        { symbol: 'AAPL', return: 2.5 },
        { symbol: 'NVDA', return: 1.8 },
      ],
      worst_performers: [
        { symbol: 'TSLA', return: -0.5 },
      ],
      agent_summaries: [],
    });
  }),
];

export const server = setupServer(...handlers);

// =============================================================================
// Test Lifecycle Hooks
// =============================================================================
beforeAll(() => {
  server.listen({ onUnhandledRequest: 'warn' });
});

afterEach(() => {
  cleanup();
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});

// =============================================================================
// Global Test Utilities
// =============================================================================
export const mockLocalStorage = () => {
  const store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      Object.keys(store).forEach((key) => delete store[key]);
    }),
  };
};

export const mockMatchMedia = () => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
};

// Apply common mocks
mockMatchMedia();
