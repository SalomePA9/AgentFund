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
from notifications.scheduler import (
    NotificationScheduler,
    TimezoneHelper,
    process_daily_reports,
)

__all__ = [
    "EmailClient",
    "EmailResult",
    "get_email_client",
    "DeliveryChannel",
    "NotificationPreferences",
    "NotificationType",
    "PreferencesManager",
    "NotificationScheduler",
    "TimezoneHelper",
    "process_daily_reports",
]
