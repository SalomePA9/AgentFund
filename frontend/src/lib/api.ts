/**
 * API client for AgentFund backend
 */

import type {
  Agent,
  AgentCreate,
  Position,
  Activity,
  DailyReport,
  ChatMessage,
  Stock,
  BrokerStatus,
  User,
  PaginatedResponse,
} from '@/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const REQUEST_TIMEOUT_MS = 60_000; // 60 seconds (Render free tier cold-starts can take 50s+)

// ============================================
// Base Fetch Utility
// ============================================

interface FetchOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
  timeoutMs?: number;
}

function fetchWithTimeout(
  url: string,
  options: RequestInit & { timeoutMs?: number } = {}
): Promise<Response> {
  const { timeoutMs = REQUEST_TIMEOUT_MS, ...fetchOptions } = options;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  return fetch(url, { ...fetchOptions, signal: controller.signal }).finally(() =>
    clearTimeout(timeoutId)
  );
}

async function fetchApi<T>(
  endpoint: string,
  options: FetchOptions = {}
): Promise<T> {
  const { params, timeoutMs, ...fetchOptions } = options;

  // Build URL with query params
  let url = `${API_URL}${endpoint}`;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        searchParams.append(key, String(value));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += `?${queryString}`;
    }
  }

  // Get auth token from localStorage
  const token =
    typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;

  let response: Response;
  try {
    response = await fetchWithTimeout(url, {
      ...fetchOptions,
      timeoutMs,
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` }),
        ...fetchOptions.headers,
      },
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error(
        'Request timed out. The server may be starting up — please try again in a moment.'
      );
    }
    throw new Error(
      'Unable to connect to the server. Please try again in a moment.'
    );
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || 'Request failed');
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

// ============================================
// Auth API
// ============================================

export const auth = {
  async register(email: string, password: string): Promise<User> {
    return fetchApi('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  },

  async login(
    email: string,
    password: string
  ): Promise<{ access_token: string; token_type: string }> {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    let response: Response;
    try {
      response = await fetchWithTimeout(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData,
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        throw new Error(
          'Request timed out. The server may be starting up — please try again in a moment.'
        );
      }
      throw new Error(
        'Unable to connect to the server. Please try again in a moment.'
      );
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(error.detail || 'Login failed');
    }

    const data = await response.json();

    // Store token
    if (typeof window !== 'undefined') {
      localStorage.setItem('auth_token', data.access_token);
    }

    return data;
  },

  logout(): void {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('auth_token');
    }
  },

  async me(): Promise<User> {
    return fetchApi('/api/auth/me');
  },

  async updateSettings(
    settings: Partial<{
      timezone: string;
      report_time: string;
      email_reports: boolean;
      email_alerts: boolean;
    }>
  ): Promise<User> {
    return fetchApi('/api/auth/settings', {
      method: 'PUT',
      body: JSON.stringify(settings),
    });
  },
};

// ============================================
// Agents API
// ============================================

export const agents = {
  async list(status?: string): Promise<Agent[]> {
    return fetchApi('/api/agents', { params: { status } });
  },

  async get(id: string): Promise<Agent> {
    return fetchApi(`/api/agents/${id}`);
  },

  async create(data: AgentCreate): Promise<Agent> {
    return fetchApi('/api/agents', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async update(
    id: string,
    data: Partial<AgentCreate>
  ): Promise<Agent> {
    return fetchApi(`/api/agents/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  async delete(id: string): Promise<void> {
    return fetchApi(`/api/agents/${id}`, { method: 'DELETE' });
  },

  async pause(id: string): Promise<Agent> {
    return fetchApi(`/api/agents/${id}/pause`, { method: 'POST' });
  },

  async resume(id: string): Promise<Agent> {
    return fetchApi(`/api/agents/${id}/resume`, { method: 'POST' });
  },

  async getPositions(id: string, status?: string): Promise<Position[]> {
    return fetchApi(`/api/agents/${id}/positions`, { params: { status } });
  },

  async getActivity(
    id: string,
    limit = 50,
    offset = 0
  ): Promise<Activity[]> {
    return fetchApi(`/api/agents/${id}/activity`, { params: { limit, offset } });
  },

  async getPerformance(id: string): Promise<{
    total_value: number;
    total_return_pct: number;
    daily_return_pct: number;
    vs_benchmark_pct: number;
    sharpe_ratio: number;
    max_drawdown_pct: number;
    win_rate_pct: number;
    open_positions: number;
    closed_positions: number;
  }> {
    return fetchApi(`/api/agents/${id}/performance`);
  },
};

// ============================================
// Reports API
// ============================================

export const reports = {
  async getTeamSummary(date?: string): Promise<{
    date: string;
    total_portfolio_value: number;
    total_daily_change: number;
    total_daily_return_pct: number;
    total_return_pct: number;
    agent_summaries: Array<{
      id: string;
      name: string;
      strategy_type: string;
      status: string;
      total_value: number;
      daily_return_pct: number;
      total_return_pct: number;
    }>;
    top_performers: Array<{
      id: string;
      name: string;
      total_return_pct: number;
    }>;
    recent_actions: Array<{
      agent_name: string;
      activity_type: string;
      ticker: string | null;
      details: Record<string, unknown>;
      created_at: string;
    }>;
  }> {
    return fetchApi('/api/reports/team-summary', {
      params: { summary_date: date },
    });
  },

  async listAgentReports(
    agentId: string,
    page = 1,
    perPage = 10
  ): Promise<PaginatedResponse<DailyReport>> {
    return fetchApi(`/api/reports/agents/${agentId}`, {
      params: { page, per_page: perPage },
    });
  },

  async getAgentReport(agentId: string, date: string): Promise<DailyReport> {
    return fetchApi(`/api/reports/agents/${agentId}/${date}`);
  },
};

// ============================================
// Chat API
// ============================================

export const chat = {
  async getHistory(
    agentId: string,
    limit = 50,
    before?: string
  ): Promise<{
    data: ChatMessage[];
    total: number;
    has_more: boolean;
  }> {
    return fetchApi(`/api/chat/agents/${agentId}`, {
      params: { limit, before },
    });
  },

  async sendMessage(
    agentId: string,
    message: string
  ): Promise<{
    user_message: ChatMessage;
    agent_response: ChatMessage;
  }> {
    return fetchApi(`/api/chat/agents/${agentId}`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  },

  async clearHistory(agentId: string): Promise<void> {
    return fetchApi(`/api/chat/agents/${agentId}`, { method: 'DELETE' });
  },
};

// ============================================
// Broker API
// ============================================

export const broker = {
  async connect(
    apiKey: string,
    apiSecret: string,
    paperMode = true
  ): Promise<BrokerStatus> {
    return fetchApi('/api/broker/connect', {
      method: 'POST',
      body: JSON.stringify({
        api_key: apiKey,
        api_secret: apiSecret,
        paper_mode: paperMode,
      }),
    });
  },

  async getStatus(): Promise<BrokerStatus> {
    return fetchApi('/api/broker/status');
  },

  async getAccount(): Promise<{
    id: string;
    status: string;
    portfolio_value: number;
    cash: number;
    buying_power: number;
    equity: number;
    currency: string;
    pattern_day_trader: boolean;
    paper_mode: boolean;
  }> {
    return fetchApi('/api/broker/account');
  },

  async switchMode(): Promise<BrokerStatus> {
    return fetchApi('/api/broker/switch-mode', { method: 'POST' });
  },
};

// ============================================
// Market API
// ============================================

export const market = {
  async listStocks(
    page = 1,
    perPage = 50,
    options?: {
      sector?: string;
      sortBy?: string;
      sortOrder?: 'asc' | 'desc';
    }
  ): Promise<PaginatedResponse<Stock>> {
    return fetchApi('/api/market/stocks', {
      params: {
        page,
        per_page: perPage,
        sector: options?.sector,
        sort_by: options?.sortBy,
        sort_order: options?.sortOrder,
      },
    });
  },

  async getStock(ticker: string): Promise<Stock> {
    return fetchApi(`/api/market/stocks/${ticker}`);
  },

  async screen(options: {
    strategy_type?: string;
    min_market_cap?: number;
    sectors?: string[];
    min_momentum_score?: number;
    min_value_score?: number;
    min_quality_score?: number;
    above_ma_200?: boolean;
    limit?: number;
  }): Promise<Stock[]> {
    return fetchApi('/api/market/screen', {
      method: 'POST',
      body: JSON.stringify(options),
    });
  },

  async getSentiment(ticker: string): Promise<{
    ticker: string;
    news_sentiment: number | null;
    social_sentiment: number | null;
    combined_sentiment: number | null;
    sentiment_velocity: number | null;
    news_headlines: Array<{ title: string; score: number }> | null;
  }> {
    return fetchApi(`/api/market/sentiment/${ticker}`);
  },

  async getSectors(): Promise<{ sectors: string[] }> {
    return fetchApi('/api/market/sectors');
  },
};

// ============================================
// Export all APIs
// ============================================

export const api = {
  auth,
  agents,
  reports,
  chat,
  broker,
  market,
};

export default api;
