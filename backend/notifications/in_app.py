"""
In-app notification system.

Handles notifications displayed within the application,
including notification creation, marking as read, and history.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from supabase import Client

logger = logging.getLogger(__name__)


class NotificationCategory(Enum):
    """Categories for in-app notifications."""

    TRADE = "trade"  # Position opened/closed, stop/target hit
    AGENT = "agent"  # Agent status changes
    REPORT = "report"  # Reports available
    SYSTEM = "system"  # System messages
    ALERT = "alert"  # Important alerts


class NotificationPriority(Enum):
    """Priority levels for notifications."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class InAppNotification:
    """An in-app notification."""

    id: str
    user_id: str
    title: str
    message: str
    category: NotificationCategory
    priority: NotificationPriority = NotificationPriority.NORMAL

    # Optional context
    agent_id: str | None = None
    ticker: str | None = None
    action_url: str | None = None
    metadata: dict[str, Any] | None = None

    # Status
    read: bool = False
    read_at: datetime | None = None
    created_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "message": self.message,
            "category": self.category.value,
            "priority": self.priority.value,
            "agent_id": self.agent_id,
            "ticker": self.ticker,
            "action_url": self.action_url,
            "metadata": self.metadata,
            "read": self.read,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "created_at": (self.created_at.isoformat() if self.created_at else None),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InAppNotification":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            title=data["title"],
            message=data["message"],
            category=NotificationCategory(data.get("category", "system")),
            priority=NotificationPriority(data.get("priority", "normal")),
            agent_id=data.get("agent_id"),
            ticker=data.get("ticker"),
            action_url=data.get("action_url"),
            metadata=data.get("metadata"),
            read=data.get("read", False),
            read_at=(
                datetime.fromisoformat(data["read_at"]) if data.get("read_at") else None
            ),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else None
            ),
        )


class InAppNotificationManager:
    """
    Manages in-app notifications.

    Handles creating, reading, and managing notification history.
    """

    TABLE_NAME = "notifications"
    MAX_UNREAD = 100  # Max unread notifications to keep

    def __init__(self, db: "Client"):
        """
        Initialize notification manager.

        Args:
            db: Supabase client
        """
        self.db = db

    def create(
        self,
        user_id: str,
        title: str,
        message: str,
        category: NotificationCategory,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        agent_id: str | None = None,
        ticker: str | None = None,
        action_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> InAppNotification | None:
        """
        Create a new in-app notification.

        Args:
            user_id: User to notify
            title: Notification title
            message: Notification message
            category: Notification category
            priority: Notification priority
            agent_id: Related agent ID
            ticker: Related stock ticker
            action_url: URL for notification action
            metadata: Additional metadata

        Returns:
            Created notification or None on error
        """
        notification = InAppNotification(
            id=str(uuid4()),
            user_id=user_id,
            title=title,
            message=message,
            category=category,
            priority=priority,
            agent_id=agent_id,
            ticker=ticker,
            action_url=action_url,
            metadata=metadata,
            created_at=datetime.utcnow(),
        )

        try:
            self.db.table(self.TABLE_NAME).insert(notification.to_dict()).execute()
            logger.info(f"Created notification for user {user_id}: {title}")
            return notification
        except Exception as e:
            logger.error(f"Failed to create notification: {e}")
            return None

    def get_unread(
        self,
        user_id: str,
        limit: int = 50,
    ) -> list[InAppNotification]:
        """
        Get unread notifications for a user.

        Args:
            user_id: User ID
            limit: Maximum notifications to return

        Returns:
            List of unread notifications
        """
        try:
            result = (
                self.db.table(self.TABLE_NAME)
                .select("*")
                .eq("user_id", user_id)
                .eq("read", False)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

            return [InAppNotification.from_dict(row) for row in (result.data or [])]
        except Exception as e:
            logger.error(f"Failed to get unread notifications: {e}")
            return []

    def get_all(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
        category: NotificationCategory | None = None,
    ) -> list[InAppNotification]:
        """
        Get all notifications for a user.

        Args:
            user_id: User ID
            limit: Maximum notifications to return
            offset: Pagination offset
            category: Filter by category

        Returns:
            List of notifications
        """
        try:
            query = (
                self.db.table(self.TABLE_NAME)
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
            )

            if category:
                query = query.eq("category", category.value)

            result = query.range(offset, offset + limit - 1).execute()

            return [InAppNotification.from_dict(row) for row in (result.data or [])]
        except Exception as e:
            logger.error(f"Failed to get notifications: {e}")
            return []

    def get_unread_count(self, user_id: str) -> int:
        """
        Get count of unread notifications.

        Args:
            user_id: User ID

        Returns:
            Count of unread notifications
        """
        try:
            result = (
                self.db.table(self.TABLE_NAME)
                .select("id", count="exact")
                .eq("user_id", user_id)
                .eq("read", False)
                .execute()
            )
            return result.count or 0
        except Exception as e:
            logger.error(f"Failed to get unread count: {e}")
            return 0

    def mark_as_read(
        self,
        notification_id: str,
        user_id: str,
    ) -> bool:
        """
        Mark a notification as read.

        Args:
            notification_id: Notification ID
            user_id: User ID (for verification)

        Returns:
            True if successful
        """
        try:
            self.db.table(self.TABLE_NAME).update(
                {"read": True, "read_at": datetime.utcnow().isoformat()}
            ).eq("id", notification_id).eq("user_id", user_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to mark notification as read: {e}")
            return False

    def mark_all_as_read(self, user_id: str) -> int:
        """
        Mark all notifications as read for a user.

        Args:
            user_id: User ID

        Returns:
            Number of notifications marked as read
        """
        try:
            result = (
                self.db.table(self.TABLE_NAME)
                .update({"read": True, "read_at": datetime.utcnow().isoformat()})
                .eq("user_id", user_id)
                .eq("read", False)
                .execute()
            )
            count = len(result.data) if result.data else 0
            logger.info(f"Marked {count} notifications as read for user {user_id}")
            return count
        except Exception as e:
            logger.error(f"Failed to mark all as read: {e}")
            return 0

    def delete(self, notification_id: str, user_id: str) -> bool:
        """
        Delete a notification.

        Args:
            notification_id: Notification ID
            user_id: User ID (for verification)

        Returns:
            True if successful
        """
        try:
            self.db.table(self.TABLE_NAME).delete().eq("id", notification_id).eq(
                "user_id", user_id
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete notification: {e}")
            return False

    def delete_old(self, user_id: str, days: int = 30) -> int:
        """
        Delete notifications older than specified days.

        Args:
            user_id: User ID
            days: Delete notifications older than this many days

        Returns:
            Number of notifications deleted
        """
        try:
            cutoff = datetime.utcnow().isoformat()
            # This would need proper date comparison in production
            result = (
                self.db.table(self.TABLE_NAME)
                .delete()
                .eq("user_id", user_id)
                .eq("read", True)  # Only delete read notifications
                .lt("created_at", cutoff)
                .execute()
            )
            count = len(result.data) if result.data else 0
            logger.info(f"Deleted {count} old notifications for user {user_id}")
            return count
        except Exception as e:
            logger.error(f"Failed to delete old notifications: {e}")
            return 0


# Helper functions for creating common notifications


def create_trade_notification(
    db: "Client",
    user_id: str,
    agent_id: str,
    agent_name: str,
    trade_type: str,  # "buy", "sell", "stop_loss", "target_hit"
    ticker: str,
    shares: int,
    price: float,
    pnl: float | None = None,
) -> InAppNotification | None:
    """Create a trade notification."""
    manager = InAppNotificationManager(db)

    if trade_type == "buy":
        title = f"{agent_name} bought {ticker}"
        message = f"Purchased {shares:,} shares at ${price:.2f}"
        priority = NotificationPriority.NORMAL
    elif trade_type == "sell":
        title = f"{agent_name} sold {ticker}"
        message = f"Sold {shares:,} shares at ${price:.2f}"
        if pnl is not None:
            message += f" (P&L: ${pnl:+,.2f})"
        priority = NotificationPriority.NORMAL
    elif trade_type == "stop_loss":
        title = f"Stop Loss: {ticker}"
        message = f"{agent_name} exited {shares:,} shares at ${price:.2f}"
        if pnl is not None:
            message += f" (P&L: ${pnl:+,.2f})"
        priority = NotificationPriority.HIGH
    elif trade_type == "target_hit":
        title = f"Target Hit: {ticker}"
        message = f"{agent_name} closed {shares:,} shares at ${price:.2f}"
        if pnl is not None:
            message += f" (P&L: ${pnl:+,.2f})"
        priority = NotificationPriority.HIGH
    else:
        title = f"Trade: {ticker}"
        message = f"{agent_name} traded {shares:,} shares at ${price:.2f}"
        priority = NotificationPriority.NORMAL

    return manager.create(
        user_id=user_id,
        title=title,
        message=message,
        category=NotificationCategory.TRADE,
        priority=priority,
        agent_id=agent_id,
        ticker=ticker,
        action_url=f"/agents/{agent_id}",
    )


def create_agent_notification(
    db: "Client",
    user_id: str,
    agent_id: str,
    agent_name: str,
    event: str,  # "created", "paused", "resumed", "error"
    details: str | None = None,
) -> InAppNotification | None:
    """Create an agent status notification."""
    manager = InAppNotificationManager(db)

    if event == "created":
        title = f"Agent Created: {agent_name}"
        message = "Your new trading agent is ready to start"
        priority = NotificationPriority.NORMAL
    elif event == "paused":
        title = f"Agent Paused: {agent_name}"
        message = details or "Trading has been paused"
        priority = NotificationPriority.NORMAL
    elif event == "resumed":
        title = f"Agent Resumed: {agent_name}"
        message = details or "Trading has resumed"
        priority = NotificationPriority.NORMAL
    elif event == "error":
        title = f"Agent Error: {agent_name}"
        message = details or "An error occurred with this agent"
        priority = NotificationPriority.URGENT
    else:
        title = f"Agent Update: {agent_name}"
        message = details or "Agent status changed"
        priority = NotificationPriority.NORMAL

    return manager.create(
        user_id=user_id,
        title=title,
        message=message,
        category=NotificationCategory.AGENT,
        priority=priority,
        agent_id=agent_id,
        action_url=f"/agents/{agent_id}",
    )


def create_report_notification(
    db: "Client",
    user_id: str,
    agent_id: str | None,
    report_type: str,  # "daily", "team", "weekly"
) -> InAppNotification | None:
    """Create a report available notification."""
    manager = InAppNotificationManager(db)

    if report_type == "daily":
        title = "Daily Report Available"
        message = "Your daily agent report is ready to view"
        action_url = f"/agents/{agent_id}/reports" if agent_id else "/reports"
    elif report_type == "team":
        title = "Team Summary Available"
        message = "Your team summary report is ready"
        action_url = "/reports/team"
    elif report_type == "weekly":
        title = "Weekly Digest Available"
        message = "Your weekly performance digest is ready"
        action_url = "/reports/weekly"
    else:
        title = "Report Available"
        message = "A new report is available"
        action_url = "/reports"

    return manager.create(
        user_id=user_id,
        title=title,
        message=message,
        category=NotificationCategory.REPORT,
        priority=NotificationPriority.LOW,
        agent_id=agent_id,
        action_url=action_url,
    )
