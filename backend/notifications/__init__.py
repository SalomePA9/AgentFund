"""
Notifications package for AgentFund.

Provides email delivery, in-app notifications, and notification preferences.
"""

from notifications.email_client import (
    EmailClient,
    EmailResult,
    get_email_client,
)

__all__ = [
    "EmailClient",
    "EmailResult",
    "get_email_client",
]
