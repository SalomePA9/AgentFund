"""
Integration tests for complete API flows.

These tests verify end-to-end functionality across multiple endpoints.
"""

from uuid import uuid4

import pytest


@pytest.mark.integration
class TestUserRegistrationFlow:
    """Test complete user registration and authentication flow."""

    def test_complete_registration_login_flow(self, client, mock_db):
        """Test full registration -> login -> get profile flow."""
        user_id = str(uuid4())
        email = "integration@test.com"
        password = "secure_password_123"

        from api.auth import get_password_hash

        hashed = get_password_hash(password)

        # User data for the flow
        user_data = {
            "id": user_id,
            "email": email,
            "password_hash": hashed,
            "total_capital": 0,
            "allocated_capital": 0,
            "settings": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        # 1. Register - empty for existence check, return created user for insert
        mock_db._tables_data["users"] = []
        mock_db._insert_data["users"] = [
            {
                "id": user_id,
                "email": email,
                "created_at": "2024-01-01T00:00:00Z",
            }
        ]

        register_response = client.post(
            "/api/auth/register", json={"email": email, "password": password}
        )
        assert register_response.status_code == 201

        # 2. Login - need user with password hash
        mock_db._tables_data["users"] = [user_data]

        login_response = client.post(
            "/api/auth/login", data={"username": email, "password": password}
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        # 3. Get profile
        profile_response = client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert profile_response.status_code == 200
        assert profile_response.json()["email"] == email


@pytest.mark.integration
class TestAgentLifecycleFlow:
    """Test complete agent creation and management flow."""

    def test_agent_creation_pause_resume_delete_flow(
        self, client, mock_db, sample_user, auth_headers
    ):
        """Test full agent lifecycle: create -> pause -> resume -> delete."""
        agent_id = str(uuid4())

        # Base agent data
        created_agent = {
            "id": agent_id,
            "user_id": sample_user["id"],
            "name": "Lifecycle Test Agent",
            "persona": "analytical",
            "status": "active",
            "strategy_type": "momentum",
            "strategy_params": {},
            "risk_params": {},
            "allocated_capital": 10000.00,
            "cash_balance": 10000.00,
            "time_horizon_days": 180,
            "start_date": "2024-01-01",
            "end_date": "2024-07-01",
            "total_value": 10000.00,
            "total_return_pct": 0.0,
            "daily_return_pct": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "win_rate_pct": 0.0,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        # 1. Create Agent
        mock_db._tables_data["users"] = [sample_user]
        mock_db._tables_data["agents"] = [created_agent]
        mock_db._insert_data["agents"] = [created_agent]

        create_response = client.post(
            "/api/agents",
            headers=auth_headers,
            json={
                "name": "Lifecycle Test Agent",
                "strategy_type": "momentum",
                "allocated_capital": 10000,
                "time_horizon_days": 180,
            },
        )
        assert create_response.status_code == 201
        assert create_response.json()["status"] == "active"

        # 2. Pause Agent
        paused_agent = {**created_agent, "status": "paused"}
        mock_db._tables_data["agents"] = [paused_agent]
        mock_db._insert_data["agent_activity"] = [{}]

        pause_response = client.post(
            f"/api/agents/{agent_id}/pause", headers=auth_headers
        )
        assert pause_response.status_code == 200

        # 3. Resume Agent
        resumed_agent = {**created_agent, "status": "active"}
        mock_db._tables_data["agents"] = [resumed_agent]

        resume_response = client.post(
            f"/api/agents/{agent_id}/resume", headers=auth_headers
        )
        assert resume_response.status_code == 200

        # 4. Delete Agent
        mock_db._tables_data["agents"] = [created_agent]

        delete_response = client.delete(f"/api/agents/{agent_id}", headers=auth_headers)
        assert delete_response.status_code == 204


@pytest.mark.integration
class TestChatFlow:
    """Test chat functionality flow."""

    def test_chat_conversation_flow(
        self, client, mock_db, sample_agent, sample_user, auth_headers
    ):
        """Test sending messages and getting chat history."""
        # Setup mocks - chat API uses agent_chats table
        user_message = {
            "id": str(uuid4()),
            "agent_id": sample_agent["id"],
            "role": "user",
            "message": "How is my portfolio doing?",
            "context_used": None,
            "created_at": "2024-01-01T00:00:00Z",
        }
        agent_response = {
            "id": str(uuid4()),
            "agent_id": sample_agent["id"],
            "role": "agent",
            "message": "Your portfolio is performing well...",
            "context_used": {
                "agent_name": sample_agent["name"],
                "persona": sample_agent["persona"],
                "strategy_type": sample_agent["strategy_type"],
            },
            "created_at": "2024-01-01T00:00:01Z",
        }

        mock_db._tables_data["users"] = [sample_user]
        mock_db._tables_data["agents"] = [sample_agent]
        mock_db._tables_data["positions"] = []
        mock_db._tables_data["agent_activity"] = []
        mock_db._tables_data["agent_chats"] = [user_message, agent_response]
        # Insert returns different messages for first and second insert
        mock_db._insert_data["agent_chats"] = [user_message, agent_response]

        send_response = client.post(
            f"/api/chat/agents/{sample_agent['id']}",
            headers=auth_headers,
            json={"message": "How is my portfolio doing?"},
        )
        assert send_response.status_code == 200
        data = send_response.json()
        assert "user_message" in data
        assert "agent_response" in data


@pytest.mark.integration
class TestMarketDataFlow:
    """Test market data retrieval flows."""

    def test_stock_listing_and_screening_flow(
        self, client, mock_db, sample_stocks, sample_user, auth_headers
    ):
        """Test listing stocks and running screens."""
        mock_db._tables_data["users"] = [sample_user]
        mock_db._tables_data["stocks"] = sample_stocks

        # 1. List stocks
        list_response = client.get("/api/market/stocks", headers=auth_headers)
        assert list_response.status_code == 200
        assert "data" in list_response.json()

        # 2. Screen stocks
        screen_response = client.post(
            "/api/market/screen",
            headers=auth_headers,
            json={
                "strategy_type": "momentum",
                "min_market_cap": 1000000000,
                "limit": 10,
            },
        )
        assert screen_response.status_code == 200


@pytest.mark.integration
class TestReportFlow:
    """Test report retrieval flows."""

    def test_team_summary_flow(
        self, client, mock_db, sample_agents, sample_user, auth_headers
    ):
        """Test getting team summary."""
        mock_db._tables_data["users"] = [sample_user]
        mock_db._tables_data["agents"] = sample_agents
        mock_db._tables_data["agent_activity"] = []

        response = client.get("/api/reports/team-summary", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_portfolio_value" in data
        assert "agent_summaries" in data
