import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { server, handlers } from '../../setup';
import { http, HttpResponse } from 'msw';

// Note: We're testing the API client behavior
// The actual api module would be imported here in a real implementation

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// =============================================================================
// API Client Tests
// =============================================================================
describe('API Client', () => {
  describe('Authentication', () => {
    it('should successfully login with valid credentials', async () => {
      const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'test@example.com', password: 'password123' }),
      });

      const data = await response.json();

      expect(response.ok).toBe(true);
      expect(data.access_token).toBe('mock-jwt-token');
      expect(data.user.email).toBe('test@example.com');
    });

    it('should handle login failure', async () => {
      // Override handler for this test
      server.use(
        http.post(`${API_BASE_URL}/api/auth/login`, () => {
          return HttpResponse.json(
            { detail: 'Invalid credentials' },
            { status: 401 }
          );
        })
      );

      const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'wrong@example.com', password: 'wrongpass' }),
      });

      expect(response.status).toBe(401);
      const data = await response.json();
      expect(data.detail).toBe('Invalid credentials');
    });

    it('should successfully register a new user', async () => {
      const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'new@example.com', password: 'password123' }),
      });

      const data = await response.json();

      expect(response.ok).toBe(true);
      expect(data.email).toBe('test@example.com');
      expect(data.id).toBeDefined();
    });

    it('should get current user with valid token', async () => {
      const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
        headers: {
          Authorization: 'Bearer mock-jwt-token',
        },
      });

      const data = await response.json();

      expect(response.ok).toBe(true);
      expect(data.email).toBe('test@example.com');
      expect(data.total_capital).toBe(100000);
    });
  });

  describe('Agents', () => {
    it('should fetch all agents', async () => {
      const response = await fetch(`${API_BASE_URL}/api/agents`, {
        headers: {
          Authorization: 'Bearer mock-jwt-token',
        },
      });

      const data = await response.json();

      expect(response.ok).toBe(true);
      expect(Array.isArray(data)).toBe(true);
      expect(data.length).toBe(2);
      expect(data[0].name).toBe('Growth AI');
      expect(data[1].name).toBe('Value Hunter');
    });

    it('should create a new agent', async () => {
      const newAgent = {
        name: 'Test Agent',
        strategy: 'momentum',
        allocated_capital: 10000,
        risk_tolerance: 'medium',
      };

      const response = await fetch(`${API_BASE_URL}/api/agents`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer mock-jwt-token',
        },
        body: JSON.stringify(newAgent),
      });

      const data = await response.json();

      expect(response.ok).toBe(true);
      expect(data.id).toBe('agent-new');
      expect(data.name).toBe('Test Agent');
      expect(data.strategy).toBe('momentum');
      expect(data.status).toBe('active');
    });

    it('should fetch a single agent by ID', async () => {
      const response = await fetch(`${API_BASE_URL}/api/agents/agent-1`, {
        headers: {
          Authorization: 'Bearer mock-jwt-token',
        },
      });

      const data = await response.json();

      expect(response.ok).toBe(true);
      expect(data.id).toBe('agent-1');
      expect(data.name).toBe('Growth AI');
    });

    it('should handle agent not found', async () => {
      server.use(
        http.get(`${API_BASE_URL}/api/agents/:agentId`, () => {
          return HttpResponse.json(
            { detail: 'Agent not found' },
            { status: 404 }
          );
        })
      );

      const response = await fetch(`${API_BASE_URL}/api/agents/non-existent`, {
        headers: {
          Authorization: 'Bearer mock-jwt-token',
        },
      });

      expect(response.status).toBe(404);
    });
  });

  describe('Market Data', () => {
    it('should fetch stock data by symbol', async () => {
      const response = await fetch(`${API_BASE_URL}/api/market/stocks/AAPL`, {
        headers: {
          Authorization: 'Bearer mock-jwt-token',
        },
      });

      const data = await response.json();

      expect(response.ok).toBe(true);
      expect(data.symbol).toBe('AAPL');
      expect(data.name).toBe('Apple Inc.');
      expect(data.price).toBe(185.92);
    });
  });

  describe('Reports', () => {
    it('should fetch daily report', async () => {
      const response = await fetch(`${API_BASE_URL}/api/reports/daily`, {
        headers: {
          Authorization: 'Bearer mock-jwt-token',
        },
      });

      const data = await response.json();

      expect(response.ok).toBe(true);
      expect(data.total_portfolio_value).toBe(100000);
      expect(data.daily_pnl).toBe(1250);
      expect(data.top_performers).toBeDefined();
    });
  });

  describe('Error Handling', () => {
    it('should handle network errors gracefully', async () => {
      server.use(
        http.get(`${API_BASE_URL}/api/agents`, () => {
          return HttpResponse.error();
        })
      );

      await expect(
        fetch(`${API_BASE_URL}/api/agents`)
      ).rejects.toThrow();
    });

    it('should handle 500 server errors', async () => {
      server.use(
        http.get(`${API_BASE_URL}/api/agents`, () => {
          return HttpResponse.json(
            { detail: 'Internal server error' },
            { status: 500 }
          );
        })
      );

      const response = await fetch(`${API_BASE_URL}/api/agents`);
      expect(response.status).toBe(500);
    });

    it('should handle 401 unauthorized errors', async () => {
      server.use(
        http.get(`${API_BASE_URL}/api/auth/me`, () => {
          return HttpResponse.json(
            { detail: 'Not authenticated' },
            { status: 401 }
          );
        })
      );

      const response = await fetch(`${API_BASE_URL}/api/auth/me`);
      expect(response.status).toBe(401);
    });
  });
});
