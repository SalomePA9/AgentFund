"""
Email templates for AgentFund notifications.

All templates follow the AgentFund dark mode aesthetic with
premium feel and financial data clarity.
"""

from notifications.templates.base import BaseTemplate
from notifications.templates.daily_report import DailyReportTemplate
from notifications.templates.team_summary import TeamSummaryTemplate
from notifications.templates.alerts import AlertTemplate
from notifications.templates.welcome import WelcomeTemplate

__all__ = [
    "BaseTemplate",
    "DailyReportTemplate",
    "TeamSummaryTemplate",
    "AlertTemplate",
    "WelcomeTemplate",
]
