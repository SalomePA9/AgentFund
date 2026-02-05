"""
Pytest configuration and fixtures for AgentFund backend tests.

This module provides shared fixtures, test utilities, and configuration
for all backend tests including unit, integration, and API tests.
"""

import asyncio
import os
from datetime import date, datetime, timedelta
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Set test environment before importing app
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only-32-chars")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-32-chars-here")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key")
os.environ.setdefault("DEBUG", "true")


# ============================================
# Event Loop Configuration
# ============================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================
# Application Fixtures
# ============================================


@pytest.fixture
def app() -> FastAPI:
    """Create a test FastAPI application instance."""
    from main import create_app

    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    """Create a synchronous test client."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create an asynchronous test client."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


# ============================================
# Database Fixtures (Mocked)
# ============================================


@pytest.fixture
def mock_supabase():
    """
    Create a mock Supabase client.

    This fixture provides a fully mocked Supabase client that can be
    configured to return specific data for each test.
    """
    mock_client = MagicMock()

    # Mock table operations
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table

    # Chain-able methods
    mock_table.select.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.delete.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.neq.return_value = mock_table
    mock_table.gt.return_value = mock_table
    mock_table.gte.return_value = mock_table
    mock_table.lt.return_value = mock_table
    mock_table.lte.return_value = mock_table
    mock_table.in_.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.range.return_value = mock_table

    # Default execute response
    mock_response = MagicMock()
    mock_response.data = []
    mock_response.count = 0
    mock_table.execute.return_value = mock_response

    return mock_client


@pytest.fixture
def mock_db(mock_supabase):
    """Patch the database module to use mock client."""
    with patch("database.get_supabase_client", return_value=mock_supabase):
        with patch("database.get_db", return_value=mock_supabase):
            yield mock_supabase


# ============================================
# User Fixtures
# ============================================


@pytest.fixture
def sample_user() -> dict:
    """Create a sample user dictionary."""
    return {
        "id": str(uuid4()),
        "email": "test@example.com",
        "password_hash": "$2b$12$test.hash.value",
        "total_capital": 100000.00,
        "allocated_capital": 50000.00,
        "settings": {
            "timezone": "America/New_York",
            "report_time": "07:00",
            "email_reports": True,
            "email_alerts": True,
        },
        "alpaca_api_key": None,
        "alpaca_api_secret": None,
        "alpaca_paper_mode": True,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def sample_user_with_broker(sample_user) -> dict:
    """Create a sample user with broker credentials."""
    return {
        **sample_user,
        "alpaca_api_key": "encrypted_api_key",
        "alpaca_api_secret": "encrypted_api_secret",
        "alpaca_paper_mode": True,
    }


@pytest.fixture
def auth_token(sample_user) -> str:
    """Create a valid JWT token for testing."""
    from api.auth import create_access_token

    return create_access_token(data={"sub": sample_user["id"]})


@pytest.fixture
def auth_headers(auth_token) -> dict:
    """Create authorization headers with valid token."""
    return {"Authorization": f"Bearer {auth_token}"}


# ============================================
# Agent Fixtures
# ============================================


@pytest.fixture
def sample_agent(sample_user) -> dict:
    """Create a sample agent dictionary."""
    start_date = date.today()
    end_date = start_date + timedelta(days=180)

    return {
        "id": str(uuid4()),
        "user_id": sample_user["id"],
        "name": "Test Momentum Agent",
        "persona": "analytical",
        "status": "active",
        "strategy_type": "momentum",
        "strategy_params": {
            "momentum_lookback_days": 180,
            "min_market_cap": 1000000000,
            "sectors": "all",
            "exclude_tickers": [],
            "max_positions": 10,
            "sentiment_weight": 0.3,
            "rebalance_frequency": "weekly",
        },
        "risk_params": {
            "stop_loss_type": "ma_200",
            "stop_loss_percentage": 0.10,
            "max_position_size_pct": 0.15,
            "min_risk_reward_ratio": 2.0,
            "max_sector_concentration": 0.50,
        },
        "allocated_capital": 25000.00,
        "cash_balance": 5000.00,
        "time_horizon_days": 180,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_value": 26250.00,
        "total_return_pct": 5.0,
        "daily_return_pct": 0.25,
        "sharpe_ratio": 1.5,
        "max_drawdown_pct": 3.0,
        "win_rate_pct": 65.0,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def sample_agents(sample_user) -> list[dict]:
    """Create multiple sample agents."""
    agents = []
    strategies = ["momentum", "quality_value", "quality_momentum", "dividend_growth"]

    for i, strategy in enumerate(strategies):
        start_date = date.today()
        end_date = start_date + timedelta(days=180 + i * 30)

        agents.append(
            {
                "id": str(uuid4()),
                "user_id": sample_user["id"],
                "name": f"Test {strategy.replace('_', ' ').title()} Agent",
                "persona": ["analytical", "aggressive", "conservative", "teacher"][i],
                "status": "active" if i < 3 else "paused",
                "strategy_type": strategy,
                "strategy_params": {"max_positions": 10},
                "risk_params": {"stop_loss_percentage": 0.10},
                "allocated_capital": 25000.00,
                "cash_balance": 5000.00 + i * 1000,
                "time_horizon_days": 180 + i * 30,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_value": 25000.00 + i * 500,
                "total_return_pct": 2.0 + i * 1.5,
                "daily_return_pct": 0.1 * (i + 1),
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
        )

    return agents


# ============================================
# Position Fixtures
# ============================================


@pytest.fixture
def sample_position(sample_agent) -> dict:
    """Create a sample position dictionary."""
    return {
        "id": str(uuid4()),
        "agent_id": sample_agent["id"],
        "ticker": "AAPL",
        "entry_price": 185.50,
        "entry_date": (date.today() - timedelta(days=30)).isoformat(),
        "shares": 10.0,
        "entry_rationale": "Strong momentum, above 200-day MA",
        "target_price": 210.00,
        "stop_loss_price": 175.00,
        "current_price": 192.30,
        "current_value": 1923.00,
        "unrealized_pnl": 68.00,
        "unrealized_pnl_pct": 3.66,
        "status": "open",
        "exit_price": None,
        "exit_date": None,
        "exit_rationale": None,
        "realized_pnl": None,
        "realized_pnl_pct": None,
        "entry_order_id": "order_123",
        "exit_order_id": None,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def sample_positions(sample_agent) -> list[dict]:
    """Create multiple sample positions."""
    tickers = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN"]
    positions = []

    for i, ticker in enumerate(tickers):
        entry_price = 100.0 + i * 50
        current_price = entry_price * (1 + (i - 2) * 0.05)
        shares = 10 - i

        positions.append(
            {
                "id": str(uuid4()),
                "agent_id": sample_agent["id"],
                "ticker": ticker,
                "entry_price": entry_price,
                "entry_date": (date.today() - timedelta(days=30 - i * 5)).isoformat(),
                "shares": shares,
                "entry_rationale": f"Entry rationale for {ticker}",
                "target_price": entry_price * 1.15,
                "stop_loss_price": entry_price * 0.90,
                "current_price": current_price,
                "current_value": current_price * shares,
                "unrealized_pnl": (current_price - entry_price) * shares,
                "unrealized_pnl_pct": ((current_price / entry_price) - 1) * 100,
                "status": "open" if i < 4 else "closed_target",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
        )

    return positions


# ============================================
# Stock/Market Data Fixtures
# ============================================


@pytest.fixture
def sample_stock() -> dict:
    """Create a sample stock dictionary."""
    return {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "market_cap": 2800000000000,
        "price": 185.50,
        "ma_30": 182.00,
        "ma_100": 178.50,
        "ma_200": 172.00,
        "atr": 3.50,
        "momentum_score": 78.5,
        "value_score": 45.2,
        "quality_score": 88.3,
        "composite_score": 70.7,
        "pe_ratio": 28.5,
        "pb_ratio": 42.1,
        "roe": 0.145,
        "profit_margin": 0.253,
        "debt_to_equity": 1.52,
        "dividend_yield": 0.0051,
        "news_sentiment": 25.5,
        "social_sentiment": 18.2,
        "combined_sentiment": 22.4,
        "updated_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def sample_stocks() -> list[dict]:
    """Create multiple sample stocks."""
    stocks_data = [
        ("AAPL", "Apple Inc.", "Technology", 2800000000000, 185.50, 78.5, 45.2, 88.3),
        ("NVDA", "NVIDIA Corp", "Technology", 1200000000000, 875.00, 92.1, 32.1, 75.8),
        (
            "MSFT",
            "Microsoft Corp",
            "Technology",
            2900000000000,
            405.00,
            72.3,
            48.9,
            91.2,
        ),
        (
            "GOOGL",
            "Alphabet Inc",
            "Technology",
            1700000000000,
            142.50,
            65.8,
            55.3,
            85.4,
        ),
        ("JPM", "JPMorgan Chase", "Financial", 450000000000, 185.00, 58.2, 72.1, 78.9),
    ]

    return [
        {
            "ticker": ticker,
            "name": name,
            "sector": sector,
            "market_cap": market_cap,
            "price": price,
            "momentum_score": momentum,
            "value_score": value,
            "quality_score": quality,
            "composite_score": (momentum + value + quality) / 3,
            "ma_200": price * 0.95,
            "updated_at": datetime.utcnow().isoformat(),
        }
        for ticker, name, sector, market_cap, price, momentum, value, quality in stocks_data
    ]


# ============================================
# Broker Fixtures
# ============================================


@pytest.fixture
def mock_alpaca():
    """Create a mock Alpaca API client."""
    mock_api = MagicMock()

    # Mock account
    mock_account = MagicMock()
    mock_account.id = "test-account-id"
    mock_account.status = "ACTIVE"
    mock_account.portfolio_value = "100000.00"
    mock_account.cash = "25000.00"
    mock_account.buying_power = "50000.00"
    mock_account.equity = "100000.00"
    mock_account.currency = "USD"
    mock_account.pattern_day_trader = False
    mock_api.get_account.return_value = mock_account

    # Mock clock
    mock_clock = MagicMock()
    mock_clock.is_open = True
    mock_api.get_clock.return_value = mock_clock

    # Mock positions
    mock_api.list_positions.return_value = []

    # Mock orders
    mock_order = MagicMock()
    mock_order.id = "order-123"
    mock_order.client_order_id = "client-order-123"
    mock_order.symbol = "AAPL"
    mock_order.qty = "10"
    mock_order.side = "buy"
    mock_order.type = "market"
    mock_order.status = "filled"
    mock_order.filled_qty = "10"
    mock_order.filled_avg_price = "185.50"
    mock_order.created_at = datetime.utcnow().isoformat()
    mock_api.submit_order.return_value = mock_order
    mock_api.get_order.return_value = mock_order
    mock_api.list_orders.return_value = []

    return mock_api


# ============================================
# LLM Fixtures
# ============================================


@pytest.fixture
def mock_claude():
    """Create a mock Claude/Anthropic client."""
    mock_client = MagicMock()

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="This is a mock LLM response for testing.")]
    mock_client.messages.create.return_value = mock_response

    return mock_client


# ============================================
# Activity & Report Fixtures
# ============================================


@pytest.fixture
def sample_activity(sample_agent) -> dict:
    """Create a sample activity log entry."""
    return {
        "id": str(uuid4()),
        "agent_id": sample_agent["id"],
        "activity_type": "buy",
        "ticker": "AAPL",
        "details": {
            "shares": 10,
            "price": 185.50,
            "reason": "Strong momentum entry signal",
        },
        "created_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def sample_report(sample_agent) -> dict:
    """Create a sample daily report."""
    return {
        "id": str(uuid4()),
        "agent_id": sample_agent["id"],
        "report_date": date.today().isoformat(),
        "report_content": "Today was a solid trading day. The portfolio gained 0.5%...",
        "performance_snapshot": {
            "total_value": 26250.00,
            "daily_return": 0.25,
            "daily_return_pct": 0.25,
            "total_return_pct": 5.0,
            "vs_benchmark": 1.2,
            "sharpe_ratio": 1.5,
            "max_drawdown": 3.0,
        },
        "positions_snapshot": [
            {
                "ticker": "AAPL",
                "entry_price": 180.00,
                "current_price": 185.50,
                "return_pct": 3.05,
            },
            {
                "ticker": "NVDA",
                "entry_price": 850.00,
                "current_price": 875.00,
                "return_pct": 2.94,
            },
        ],
        "actions_taken": [
            {"type": "buy", "ticker": "MSFT", "price": 405.00, "shares": 5},
        ],
        "created_at": datetime.utcnow().isoformat(),
    }


# ============================================
# Chat Fixtures
# ============================================


@pytest.fixture
def sample_chat_messages(sample_agent) -> list[dict]:
    """Create sample chat messages."""
    agent_id = sample_agent["id"]
    base_time = datetime.utcnow()

    return [
        {
            "id": str(uuid4()),
            "agent_id": agent_id,
            "role": "user",
            "message": "How is my portfolio doing today?",
            "context_used": None,
            "created_at": (base_time - timedelta(minutes=5)).isoformat(),
        },
        {
            "id": str(uuid4()),
            "agent_id": agent_id,
            "role": "agent",
            "message": "Based on my analysis, your portfolio is up 0.25% today...",
            "context_used": {"positions": 5, "total_value": 26250.00},
            "created_at": (base_time - timedelta(minutes=4)).isoformat(),
        },
        {
            "id": str(uuid4()),
            "agent_id": agent_id,
            "role": "user",
            "message": "Should I be worried about the tech sector?",
            "context_used": None,
            "created_at": (base_time - timedelta(minutes=2)).isoformat(),
        },
        {
            "id": str(uuid4()),
            "agent_id": agent_id,
            "role": "agent",
            "message": "Looking at the data, tech remains strong with positive momentum...",
            "context_used": {"sector": "Technology", "sentiment": 25.5},
            "created_at": (base_time - timedelta(minutes=1)).isoformat(),
        },
    ]


# ============================================
# Test Utilities
# ============================================


class MockSupabaseResponse:
    """Helper class to create mock Supabase responses."""

    def __init__(self, data: list | None = None, count: int | None = None):
        self.data = data or []
        self.count = count if count is not None else len(self.data)


def configure_mock_table(mock_client, table_name: str, data: list):
    """
    Configure a mock Supabase client to return specific data for a table.

    Usage:
        configure_mock_table(mock_supabase, "users", [sample_user])
    """
    mock_response = MockSupabaseResponse(data=data)
    mock_client.table.return_value.execute.return_value = mock_response
    return mock_response


@pytest.fixture
def configure_mock_db(mock_supabase):
    """Factory fixture to configure mock database responses."""

    def _configure(table_name: str, data: list):
        return configure_mock_table(mock_supabase, table_name, data)

    return _configure
