"""
Notifications package for AgentFund.

Provides email delivery, in-app notifications, and notification preferences.
"""

from notifications.email_client import (
    EmailClient,
    EmailResult,
    get_email_client,
)
from notifications.in_app import (
    InAppNotification,
    InAppNotificationManager,
    NotificationCategory,
    NotificationPriority,
    create_agent_notification,
    create_report_notification,
    create_trade_notification,
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
    # Email client
    "EmailClient",
    "EmailResult",
    "get_email_client",
    # In-app notifications
    "InAppNotification",
    "InAppNotificationManager",
    "NotificationCategory",
    "NotificationPriority",
    "create_agent_notification",
    "create_report_notification",
    "create_trade_notification",
    # Preferences
    "DeliveryChannel",
    "NotificationPreferences",
    "NotificationType",
    "PreferencesManager",
    # Scheduler
    "NotificationScheduler",
    "TimezoneHelper",
    "process_daily_reports",
]
