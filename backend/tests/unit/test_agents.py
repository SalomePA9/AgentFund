"""
Unit tests for agents module.
"""

import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock


class TestAgentSchemas:
    """Tests for agent-related Pydantic schemas."""

    def test_strategy_params_defaults(self):
        """Test StrategyParams has correct defaults."""
        from api.agents import StrategyParams

        params = StrategyParams()

        assert params.momentum_lookback_days == 180
        assert params.min_market_cap == 1_000_000_000
        assert params.max_positions == 10
        assert params.sentiment_weight == 0.3

    def test_risk_params_defaults(self):
        """Test RiskParams has correct defaults."""
        from api.agents import RiskParams

        params = RiskParams()

        assert params.stop_loss_type == "ma_200"
        assert params.stop_loss_percentage == 0.10
        assert params.max_position_size_pct == 0.15
        assert params.min_risk_reward_ratio == 2.0

    def test_agent_create_valid(self):
        """Test AgentCreate schema with valid data."""
        from api.agents import AgentCreate

        agent = AgentCreate(
            name="Test Agent",
            strategy_type="momentum",
            allocated_capital=Decimal("10000"),
            time_horizon_days=180
        )

        assert agent.name == "Test Agent"
        assert agent.strategy_type == "momentum"
        assert agent.allocated_capital == Decimal("10000")

    def test_agent_create_with_all_params(self):
        """Test AgentCreate with all parameters."""
        from api.agents import AgentCreate, StrategyParams, RiskParams

        agent = AgentCreate(
            name="Full Agent",
            persona="aggressive",
            strategy_type="quality_momentum",
            strategy_params=StrategyParams(max_positions=15),
            risk_params=RiskParams(stop_loss_percentage=0.15),
            allocated_capital=Decimal("50000"),
            time_horizon_days=365
        )

        assert agent.persona == "aggressive"
        assert agent.strategy_params.max_positions == 15
        assert agent.risk_params.stop_loss_percentage == 0.15


class TestAgentEndpoints:
    """Tests for agent API endpoints."""

    @pytest.mark.api
    def test_list_agents(self, client, mock_db, sample_agents, auth_headers, sample_user):
        """Test listing agents."""
        # First mock for auth
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_user
        ]

        # Then mock for agents list (need to reset after first call)
        def side_effect(*args, **kwargs):
            response = MagicMock()
            if "agents" in str(args) or "agents" in str(kwargs):
                response.data = sample_agents
            else:
                response.data = [sample_user]
            return response

        mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.execute.side_effect = side_effect
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = sample_agents

        response = client.get("/api/agents", headers=auth_headers)

        assert response.status_code == 200

    @pytest.mark.api
    def test_list_agents_unauthorized(self, client):
        """Test listing agents without authentication."""
        response = client.get("/api/agents")

        assert response.status_code == 401

    @pytest.mark.api
    def test_create_agent_valid(self, client, mock_db, sample_user, auth_headers):
        """Test creating a valid agent."""
        # Mock user lookup
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_user
        ]

        # Mock agent insert
        created_agent = {
            "id": "new-agent-id",
            "user_id": sample_user["id"],
            "name": "New Agent",
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
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [created_agent]
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [sample_user]

        response = client.post(
            "/api/agents",
            headers=auth_headers,
            json={
                "name": "New Agent",
                "strategy_type": "momentum",
                "allocated_capital": 10000,
                "time_horizon_days": 180,
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Agent"

    @pytest.mark.api
    def test_create_agent_invalid_strategy(self, client, mock_db, sample_user, auth_headers):
        """Test creating agent with invalid strategy type."""
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_user
        ]

        response = client.post(
            "/api/agents",
            headers=auth_headers,
            json={
                "name": "Invalid Agent",
                "strategy_type": "invalid_strategy",
                "allocated_capital": 10000,
                "time_horizon_days": 180,
            }
        )

        assert response.status_code == 400
        assert "Invalid strategy" in response.json()["detail"]

    @pytest.mark.api
    def test_create_agent_invalid_persona(self, client, mock_db, sample_user, auth_headers):
        """Test creating agent with invalid persona."""
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_user
        ]

        response = client.post(
            "/api/agents",
            headers=auth_headers,
            json={
                "name": "Invalid Agent",
                "persona": "invalid_persona",
                "strategy_type": "momentum",
                "allocated_capital": 10000,
                "time_horizon_days": 180,
            }
        )

        assert response.status_code == 400
        assert "Invalid persona" in response.json()["detail"]

    @pytest.mark.api
    def test_get_agent_by_id(self, client, mock_db, sample_agent, sample_user, auth_headers):
        """Test getting a specific agent."""
        # Mock auth
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_user
        ]
        # Mock agent lookup (chained eq for user_id)
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            sample_agent
        ]

        response = client.get(
            f"/api/agents/{sample_agent['id']}",
            headers=auth_headers
        )

        assert response.status_code == 200

    @pytest.mark.api
    def test_get_agent_not_found(self, client, mock_db, sample_user, auth_headers):
        """Test getting non-existent agent."""
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_user
        ]
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

        response = client.get(
            "/api/agents/00000000-0000-0000-0000-000000000000",
            headers=auth_headers
        )

        assert response.status_code == 404

    @pytest.mark.api
    def test_pause_agent(self, client, mock_db, sample_agent, sample_user, auth_headers):
        """Test pausing an agent."""
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_user
        ]

        paused_agent = {**sample_agent, "status": "paused"}
        mock_db.table.return_value.update.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            paused_agent
        ]
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [{}]

        response = client.post(
            f"/api/agents/{sample_agent['id']}/pause",
            headers=auth_headers
        )

        assert response.status_code == 200

    @pytest.mark.api
    def test_resume_agent(self, client, mock_db, sample_agent, sample_user, auth_headers):
        """Test resuming a paused agent."""
        sample_agent["status"] = "paused"
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_user
        ]

        resumed_agent = {**sample_agent, "status": "active"}
        mock_db.table.return_value.update.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            resumed_agent
        ]
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [{}]

        response = client.post(
            f"/api/agents/{sample_agent['id']}/resume",
            headers=auth_headers
        )

        assert response.status_code == 200

    @pytest.mark.api
    def test_delete_agent(self, client, mock_db, sample_agent, sample_user, auth_headers):
        """Test deleting an agent."""
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_user
        ]
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            sample_agent
        ]
        mock_db.table.return_value.delete.return_value.eq.return_value.execute.return_value.data = []
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [sample_user]

        response = client.delete(
            f"/api/agents/{sample_agent['id']}",
            headers=auth_headers
        )

        assert response.status_code == 204

    @pytest.mark.api
    def test_get_agent_positions(self, client, mock_db, sample_agent, sample_positions, sample_user, auth_headers):
        """Test getting agent positions."""
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_user
        ]
        mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = sample_positions

        response = client.get(
            f"/api/agents/{sample_agent['id']}/positions",
            headers=auth_headers
        )

        assert response.status_code == 200

    @pytest.mark.api
    def test_get_agent_activity(self, client, mock_db, sample_agent, sample_activity, sample_user, auth_headers):
        """Test getting agent activity log."""
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            sample_user
        ]
        mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value.data = [
            sample_activity
        ]

        response = client.get(
            f"/api/agents/{sample_agent['id']}/activity",
            headers=auth_headers
        )

        assert response.status_code == 200


class TestAgentModels:
    """Tests for agent domain models."""

    def test_agent_status_enum(self):
        """Test AgentStatus enum values."""
        from models.agent import AgentStatus

        assert AgentStatus.ACTIVE.value == "active"
        assert AgentStatus.PAUSED.value == "paused"
        assert AgentStatus.STOPPED.value == "stopped"
        assert AgentStatus.COMPLETED.value == "completed"

    def test_strategy_type_enum(self):
        """Test StrategyType enum values."""
        from models.agent import StrategyType

        assert StrategyType.MOMENTUM.value == "momentum"
        assert StrategyType.QUALITY_VALUE.value == "quality_value"
        assert StrategyType.QUALITY_MOMENTUM.value == "quality_momentum"
        assert StrategyType.DIVIDEND_GROWTH.value == "dividend_growth"

    def test_persona_enum(self):
        """Test Persona enum values."""
        from models.agent import Persona

        assert Persona.ANALYTICAL.value == "analytical"
        assert Persona.AGGRESSIVE.value == "aggressive"
        assert Persona.CONSERVATIVE.value == "conservative"
        assert Persona.TEACHER.value == "teacher"
        assert Persona.CONCISE.value == "concise"
