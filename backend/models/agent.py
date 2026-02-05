"""Agent domain model."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel


class AgentStatus(str, Enum):
    """Agent status options."""

    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"


class StrategyType(str, Enum):
    """Available trading strategies."""

    MOMENTUM = "momentum"
    QUALITY_VALUE = "quality_value"
    QUALITY_MOMENTUM = "quality_momentum"
    DIVIDEND_GROWTH = "dividend_growth"


class Persona(str, Enum):
    """Agent persona/communication styles."""

    ANALYTICAL = "analytical"
    AGGRESSIVE = "aggressive"
    CONSERVATIVE = "conservative"
    TEACHER = "teacher"
    CONCISE = "concise"


class StrategyParams(BaseModel):
    """Strategy configuration parameters."""

    momentum_lookback_days: int = 180
    min_market_cap: int = 1_000_000_000
    sectors: str | list[str] = "all"
    exclude_tickers: list[str] = []
    max_positions: int = 10
    sentiment_weight: float = 0.3
    rebalance_frequency: str = "weekly"


class RiskParams(BaseModel):
    """Risk management parameters."""

    stop_loss_type: str = "ma_200"
    stop_loss_percentage: float = 0.10
    max_position_size_pct: float = 0.15
    min_risk_reward_ratio: float = 2.0
    max_sector_concentration: float = 0.50


class Agent(BaseModel):
    """Trading agent domain model."""

    id: str
    user_id: str
    name: str
    persona: Persona = Persona.ANALYTICAL
    status: AgentStatus = AgentStatus.ACTIVE
    strategy_type: StrategyType
    strategy_params: StrategyParams = StrategyParams()
    risk_params: RiskParams = RiskParams()
    allocated_capital: Decimal
    cash_balance: Decimal
    time_horizon_days: int
    start_date: date
    end_date: date

    # Performance metrics (updated daily)
    total_value: Decimal | None = None
    total_return_pct: float | None = None
    daily_return_pct: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown_pct: float | None = None
    win_rate_pct: float | None = None

    created_at: datetime
    updated_at: datetime

    @property
    def days_remaining(self) -> int:
        """Calculate days remaining in time horizon."""
        return max(0, (self.end_date - date.today()).days)

    @property
    def is_active(self) -> bool:
        """Check if agent is actively trading."""
        return self.status == AgentStatus.ACTIVE

    @property
    def total_return(self) -> Decimal:
        """Calculate total return amount."""
        if self.total_value is None:
            return Decimal("0")
        return self.total_value - self.allocated_capital

    class Config:
        from_attributes = True
