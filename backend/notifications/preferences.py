"""
Notification preferences management.

Handles user notification settings including email preferences,
delivery times, and timezone configuration.
"""

import logging
from dataclasses import dataclass, field
from datetime import time
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from supabase import Client

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Types of notifications users can configure."""

    # Email notifications
    DAILY_REPORT = "daily_report"  # Daily agent reports
    TEAM_SUMMARY = "team_summary"  # Team-wide summary
    ALERTS_STOP_LOSS = "alerts_stop_loss"  # Stop loss triggers
    ALERTS_TARGET_HIT = "alerts_target_hit"  # Profit targets
    ALERTS_POSITION = "alerts_position"  # Position opened/closed
    ALERTS_AGENT = "alerts_agent"  # Agent paused/errors
    WEEKLY_DIGEST = "weekly_digest"  # Weekly performance summary
    MARKETING = "marketing"  # Product updates, tips


class DeliveryChannel(Enum):
    """Notification delivery channels."""

    EMAIL = "email"
    IN_APP = "in_app"
    # Future: PUSH = "push", SMS = "sms"


@dataclass
class NotificationPreferences:
    """User notification preferences."""

    user_id: str

    # Email preferences
    email_enabled: bool = True
    email_address: str | None = None

    # Report delivery
    daily_report_enabled: bool = True
    daily_report_time: time = field(default_factory=lambda: time(8, 0))  # 8:00 AM
    team_summary_enabled: bool = True
    weekly_digest_enabled: bool = True
    weekly_digest_day: int = 0  # 0=Monday, 6=Sunday

    # Alert preferences
    alerts_stop_loss: bool = True
    alerts_target_hit: bool = True
    alerts_position: bool = False  # Off by default (can be noisy)
    alerts_agent: bool = True

    # Marketing
    marketing_enabled: bool = True

    # Timezone
    timezone: str = "America/New_York"

    # Unsubscribe token (for email links)
    unsubscribe_token: str | None = None

    @classmethod
    def default(cls, user_id: str) -> "NotificationPreferences":
        """Create default preferences for a new user."""
        return cls(user_id=user_id)

    def is_enabled(self, notification_type: NotificationType) -> bool:
        """Check if a notification type is enabled."""
        if not self.email_enabled:
            return False

        mapping = {
            NotificationType.DAILY_REPORT: self.daily_report_enabled,
            NotificationType.TEAM_SUMMARY: self.team_summary_enabled,
            NotificationType.ALERTS_STOP_LOSS: self.alerts_stop_loss,
            NotificationType.ALERTS_TARGET_HIT: self.alerts_target_hit,
            NotificationType.ALERTS_POSITION: self.alerts_position,
            NotificationType.ALERTS_AGENT: self.alerts_agent,
            NotificationType.WEEKLY_DIGEST: self.weekly_digest_enabled,
            NotificationType.MARKETING: self.marketing_enabled,
        }
        return mapping.get(notification_type, False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "user_id": self.user_id,
            "email_enabled": self.email_enabled,
            "email_address": self.email_address,
            "daily_report_enabled": self.daily_report_enabled,
            "daily_report_time": self.daily_report_time.strftime("%H:%M"),
            "team_summary_enabled": self.team_summary_enabled,
            "weekly_digest_enabled": self.weekly_digest_enabled,
            "weekly_digest_day": self.weekly_digest_day,
            "alerts_stop_loss": self.alerts_stop_loss,
            "alerts_target_hit": self.alerts_target_hit,
            "alerts_position": self.alerts_position,
            "alerts_agent": self.alerts_agent,
            "marketing_enabled": self.marketing_enabled,
            "timezone": self.timezone,
            "unsubscribe_token": self.unsubscribe_token,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NotificationPreferences":
        """Create from dictionary."""
        # Parse time string
        time_str = data.get("daily_report_time", "08:00")
        if isinstance(time_str, str):
            parts = time_str.split(":")
            report_time = time(int(parts[0]), int(parts[1]))
        else:
            report_time = time(8, 0)

        return cls(
            user_id=data["user_id"],
            email_enabled=data.get("email_enabled", True),
            email_address=data.get("email_address"),
            daily_report_enabled=data.get("daily_report_enabled", True),
            daily_report_time=report_time,
            team_summary_enabled=data.get("team_summary_enabled", True),
            weekly_digest_enabled=data.get("weekly_digest_enabled", True),
            weekly_digest_day=data.get("weekly_digest_day", 0),
            alerts_stop_loss=data.get("alerts_stop_loss", True),
            alerts_target_hit=data.get("alerts_target_hit", True),
            alerts_position=data.get("alerts_position", False),
            alerts_agent=data.get("alerts_agent", True),
            marketing_enabled=data.get("marketing_enabled", True),
            timezone=data.get("timezone", "America/New_York"),
            unsubscribe_token=data.get("unsubscribe_token"),
        )


class PreferencesManager:
    """
    Manages notification preferences in the database.

    Handles CRUD operations for user notification settings.
    """

    TABLE_NAME = "notification_preferences"

    def __init__(self, db: "Client"):
        """
        Initialize preferences manager.

        Args:
            db: Supabase client
        """
        self.db = db

    def get(self, user_id: str) -> NotificationPreferences:
        """
        Get user notification preferences.

        Creates default preferences if none exist.

        Args:
            user_id: User ID

        Returns:
            NotificationPreferences for the user
        """
        try:
            result = (
                self.db.table(self.TABLE_NAME)
                .select("*")
                .eq("user_id", user_id)
                .single()
                .execute()
            )

            if result.data:
                return NotificationPreferences.from_dict(result.data)
        except Exception as e:
            logger.debug(f"No preferences found for user {user_id}: {e}")

        # Return defaults if not found
        return NotificationPreferences.default(user_id)

    def save(self, prefs: NotificationPreferences) -> bool:
        """
        Save notification preferences.

        Uses upsert to create or update.

        Args:
            prefs: Preferences to save

        Returns:
            True if successful
        """
        try:
            data = prefs.to_dict()
            self.db.table(self.TABLE_NAME).upsert(data).execute()
            logger.info(f"Saved notification preferences for user {prefs.user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save preferences: {e}")
            return False

    def update(
        self, user_id: str, updates: dict[str, Any]
    ) -> NotificationPreferences | None:
        """
        Update specific preference fields.

        Args:
            user_id: User ID
            updates: Dictionary of field updates

        Returns:
            Updated preferences or None on error
        """
        try:
            # Get current preferences
            prefs = self.get(user_id)

            # Apply updates
            prefs_dict = prefs.to_dict()
            prefs_dict.update(updates)

            # Save and return
            updated_prefs = NotificationPreferences.from_dict(prefs_dict)
            if self.save(updated_prefs):
                return updated_prefs
            return None
        except Exception as e:
            logger.error(f"Failed to update preferences: {e}")
            return None

    def delete(self, user_id: str) -> bool:
        """
        Delete user notification preferences.

        Args:
            user_id: User ID

        Returns:
            True if successful
        """
        try:
            self.db.table(self.TABLE_NAME).delete().eq("user_id", user_id).execute()
            logger.info(f"Deleted notification preferences for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete preferences: {e}")
            return False

    def get_users_for_delivery(
        self,
        notification_type: NotificationType,
        delivery_time: time | None = None,
    ) -> list[NotificationPreferences]:
        """
        Get all users who should receive a notification type.

        Args:
            notification_type: Type of notification
            delivery_time: Specific delivery time to match (for scheduled reports)

        Returns:
            List of preferences for eligible users
        """
        try:
            # Build query based on notification type
            query = self.db.table(self.TABLE_NAME).select("*").eq("email_enabled", True)

            # Add type-specific filters
            if notification_type == NotificationType.DAILY_REPORT:
                query = query.eq("daily_report_enabled", True)
                if delivery_time:
                    time_str = delivery_time.strftime("%H:%M")
                    query = query.eq("daily_report_time", time_str)
            elif notification_type == NotificationType.TEAM_SUMMARY:
                query = query.eq("team_summary_enabled", True)
            elif notification_type == NotificationType.WEEKLY_DIGEST:
                query = query.eq("weekly_digest_enabled", True)
            elif notification_type == NotificationType.ALERTS_STOP_LOSS:
                query = query.eq("alerts_stop_loss", True)
            elif notification_type == NotificationType.ALERTS_TARGET_HIT:
                query = query.eq("alerts_target_hit", True)
            elif notification_type == NotificationType.ALERTS_POSITION:
                query = query.eq("alerts_position", True)
            elif notification_type == NotificationType.ALERTS_AGENT:
                query = query.eq("alerts_agent", True)
            elif notification_type == NotificationType.MARKETING:
                query = query.eq("marketing_enabled", True)

            result = query.execute()

            return [
                NotificationPreferences.from_dict(row) for row in (result.data or [])
            ]
        except Exception as e:
            logger.error(f"Failed to get users for delivery: {e}")
            return []

    def generate_unsubscribe_token(self, user_id: str) -> str | None:
        """
        Generate and save a unique unsubscribe token.

        Args:
            user_id: User ID

        Returns:
            Generated token or None on error
        """
        import secrets

        try:
            token = secrets.token_urlsafe(32)
            self.db.table(self.TABLE_NAME).upsert(
                {"user_id": user_id, "unsubscribe_token": token}
            ).execute()
            return token
        except Exception as e:
            logger.error(f"Failed to generate unsubscribe token: {e}")
            return None

    def get_user_by_unsubscribe_token(
        self, token: str
    ) -> NotificationPreferences | None:
        """
        Find user by unsubscribe token.

        Args:
            token: Unsubscribe token

        Returns:
            User preferences or None if not found
        """
        try:
            result = (
                self.db.table(self.TABLE_NAME)
                .select("*")
                .eq("unsubscribe_token", token)
                .single()
                .execute()
            )

            if result.data:
                return NotificationPreferences.from_dict(result.data)
            return None
        except Exception as e:
            logger.debug(f"No user found for unsubscribe token: {e}")
            return None
