"""User domain model."""

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, EmailStr


class UserSettings(BaseModel):
    """User settings configuration."""

    timezone: str = "America/New_York"
    report_time: str = "07:00"
    email_reports: bool = True
    email_alerts: bool = True


class User(BaseModel):
    """User domain model."""

    id: str
    email: EmailStr
    total_capital: Decimal = Decimal("0")
    allocated_capital: Decimal = Decimal("0")
    settings: UserSettings = UserSettings()
    alpaca_api_key: str | None = None
    alpaca_api_secret: str | None = None
    alpaca_paper_mode: bool = True
    created_at: datetime
    updated_at: datetime

    @property
    def available_capital(self) -> Decimal:
        """Calculate available (unallocated) capital."""
        return self.total_capital - self.allocated_capital

    class Config:
        from_attributes = True
