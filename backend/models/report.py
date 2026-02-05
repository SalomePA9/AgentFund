"""Daily report domain model."""

from datetime import date, datetime

from pydantic import BaseModel


class PerformanceSnapshot(BaseModel):
    """Performance metrics snapshot."""

    total_value: float
    daily_return: float
    daily_return_pct: float
    total_return_pct: float
    vs_benchmark: float
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None


class PositionSnapshot(BaseModel):
    """Position snapshot for report."""

    ticker: str
    entry_price: float
    current_price: float
    shares: float
    return_pct: float
    status: str


class ActionTaken(BaseModel):
    """Action taken during the day."""

    type: str  # buy, sell, stop_hit, target_hit
    ticker: str
    price: float
    shares: float | None = None
    reason: str | None = None
    pnl: float | None = None


class DailyReport(BaseModel):
    """Daily report domain model."""

    id: str
    agent_id: str
    report_date: date
    report_content: str  # LLM-generated narrative

    performance_snapshot: PerformanceSnapshot
    positions_snapshot: list[PositionSnapshot]
    actions_taken: list[ActionTaken] = []

    created_at: datetime

    @property
    def has_actions(self) -> bool:
        """Check if any actions were taken."""
        return len(self.actions_taken) > 0

    @property
    def buy_count(self) -> int:
        """Count buy actions."""
        return sum(1 for a in self.actions_taken if a.type == "buy")

    @property
    def sell_count(self) -> int:
        """Count sell actions."""
        return sum(
            1
            for a in self.actions_taken
            if a.type in ["sell", "stop_hit", "target_hit"]
        )

    class Config:
        from_attributes = True
