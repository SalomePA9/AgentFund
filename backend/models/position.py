"""Position domain model."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel


class PositionStatus(str, Enum):
    """Position status options."""

    OPEN = "open"
    CLOSED_TARGET = "closed_target"
    CLOSED_STOP = "closed_stop"
    CLOSED_MANUAL = "closed_manual"
    CLOSED_HORIZON = "closed_horizon"


class Position(BaseModel):
    """Trading position domain model."""

    id: str
    agent_id: str
    ticker: str

    # Entry details
    entry_price: Decimal
    entry_date: date
    shares: Decimal
    entry_rationale: str | None = None

    # Targets
    target_price: Decimal | None = None
    stop_loss_price: Decimal | None = None

    # Current state (updated daily)
    current_price: Decimal | None = None
    current_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    unrealized_pnl_pct: float | None = None

    # Status
    status: PositionStatus = PositionStatus.OPEN

    # Exit details (populated when closed)
    exit_price: Decimal | None = None
    exit_date: date | None = None
    exit_rationale: str | None = None
    realized_pnl: Decimal | None = None
    realized_pnl_pct: float | None = None

    # Order tracking
    entry_order_id: str | None = None
    exit_order_id: str | None = None

    created_at: datetime
    updated_at: datetime

    @property
    def is_open(self) -> bool:
        """Check if position is still open."""
        return self.status == PositionStatus.OPEN

    @property
    def cost_basis(self) -> Decimal:
        """Calculate total cost basis."""
        return self.entry_price * self.shares

    @property
    def risk_amount(self) -> Decimal | None:
        """Calculate risk amount (entry to stop)."""
        if self.stop_loss_price is None:
            return None
        return (self.entry_price - self.stop_loss_price) * self.shares

    @property
    def reward_amount(self) -> Decimal | None:
        """Calculate potential reward (entry to target)."""
        if self.target_price is None:
            return None
        return (self.target_price - self.entry_price) * self.shares

    @property
    def risk_reward_ratio(self) -> float | None:
        """Calculate risk/reward ratio."""
        risk = self.risk_amount
        reward = self.reward_amount
        if risk is None or reward is None or risk == 0:
            return None
        return float(reward / risk)

    def update_current_price(self, price: Decimal) -> None:
        """Update position with current market price."""
        self.current_price = price
        self.current_value = price * self.shares
        self.unrealized_pnl = self.current_value - self.cost_basis
        self.unrealized_pnl_pct = float(
            (price / self.entry_price - 1) * 100
        )

    class Config:
        from_attributes = True
