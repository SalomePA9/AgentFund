"""
Notifications package for AgentFund.

Provides email delivery, in-app notifications, and notification preferences.
"""

from notifications.email_client import (
    EmailClient,
    EmailResult,
    get_email_client,
)
from notifications.preferences import (
    DeliveryChannel,
    NotificationPreferences,
    NotificationType,
    PreferencesManager,
)

__all__ = [
    "EmailClient",
    "EmailResult",
    "get_email_client",
    "DeliveryChannel",
    "NotificationPreferences",
    "NotificationType",
    "PreferencesManager",
]
