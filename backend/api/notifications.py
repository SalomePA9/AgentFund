"""
Notification API endpoints.

Provides endpoints for managing notification preferences,
viewing in-app notifications, and handling unsubscribe requests.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from supabase import Client

from api.auth import get_current_user
from database import get_db
from notifications import NotificationType, PreferencesManager, get_email_client
from notifications.in_app import InAppNotificationManager, NotificationCategory
from notifications.templates.welcome import WelcomeData, WelcomeTemplate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ============================================================================
# Pydantic Models
# ============================================================================


class PreferencesResponse(BaseModel):
    """Notification preferences response."""

    email_enabled: bool
    daily_report_enabled: bool
    daily_report_time: str  # HH:MM format
    team_summary_enabled: bool
    weekly_digest_enabled: bool
    weekly_digest_day: int
    alerts_stop_loss: bool
    alerts_target_hit: bool
    alerts_position: bool
    alerts_agent: bool
    marketing_enabled: bool
    timezone: str


class PreferencesUpdate(BaseModel):
    """Update notification preferences."""

    email_enabled: bool | None = None
    daily_report_enabled: bool | None = None
    daily_report_time: str | None = None  # HH:MM format
    team_summary_enabled: bool | None = None
    weekly_digest_enabled: bool | None = None
    weekly_digest_day: int | None = Field(None, ge=0, le=6)
    alerts_stop_loss: bool | None = None
    alerts_target_hit: bool | None = None
    alerts_position: bool | None = None
    alerts_agent: bool | None = None
    marketing_enabled: bool | None = None
    timezone: str | None = None


class NotificationResponse(BaseModel):
    """In-app notification response."""

    id: str
    title: str
    message: str
    category: str
    priority: str
    agent_id: str | None = None
    ticker: str | None = None
    action_url: str | None = None
    read: bool
    created_at: str | None = None


class NotificationListResponse(BaseModel):
    """List of notifications response."""

    notifications: list[NotificationResponse]
    unread_count: int
    total: int


class UnsubscribeRequest(BaseModel):
    """Unsubscribe request."""

    token: str
    notification_type: str | None = None  # Specific type or None for all


class SendWelcomeRequest(BaseModel):
    """Request to send welcome email."""

    email: str
    name: str


# ============================================================================
# Preferences Endpoints
# ============================================================================


@router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> PreferencesResponse:
    """Get current user's notification preferences."""
    manager = PreferencesManager(db)
    prefs = manager.get(current_user["id"])

    return PreferencesResponse(
        email_enabled=prefs.email_enabled,
        daily_report_enabled=prefs.daily_report_enabled,
        daily_report_time=prefs.daily_report_time.strftime("%H:%M"),
        team_summary_enabled=prefs.team_summary_enabled,
        weekly_digest_enabled=prefs.weekly_digest_enabled,
        weekly_digest_day=prefs.weekly_digest_day,
        alerts_stop_loss=prefs.alerts_stop_loss,
        alerts_target_hit=prefs.alerts_target_hit,
        alerts_position=prefs.alerts_position,
        alerts_agent=prefs.alerts_agent,
        marketing_enabled=prefs.marketing_enabled,
        timezone=prefs.timezone,
    )


@router.put("/preferences", response_model=PreferencesResponse)
async def update_preferences(
    updates: PreferencesUpdate,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> PreferencesResponse:
    """Update user's notification preferences."""
    manager = PreferencesManager(db)

    # Build update dict, excluding None values
    update_dict: dict[str, Any] = {}
    for field, value in updates.model_dump().items():
        if value is not None:
            update_dict[field] = value

    # Update and return
    updated = manager.update(current_user["id"], update_dict)

    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update preferences")

    return PreferencesResponse(
        email_enabled=updated.email_enabled,
        daily_report_enabled=updated.daily_report_enabled,
        daily_report_time=updated.daily_report_time.strftime("%H:%M"),
        team_summary_enabled=updated.team_summary_enabled,
        weekly_digest_enabled=updated.weekly_digest_enabled,
        weekly_digest_day=updated.weekly_digest_day,
        alerts_stop_loss=updated.alerts_stop_loss,
        alerts_target_hit=updated.alerts_target_hit,
        alerts_position=updated.alerts_position,
        alerts_agent=updated.alerts_agent,
        marketing_enabled=updated.marketing_enabled,
        timezone=updated.timezone,
    )


# ============================================================================
# In-App Notifications Endpoints
# ============================================================================


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category: str | None = Query(None),
    unread_only: bool = Query(False),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> NotificationListResponse:
    """List user's notifications."""
    manager = InAppNotificationManager(db)

    # Parse category
    cat_filter = None
    if category:
        try:
            cat_filter = NotificationCategory(category)
        except ValueError:
            pass

    # Get notifications
    if unread_only:
        notifications = manager.get_unread(current_user["id"], limit)
    else:
        notifications = manager.get_all(current_user["id"], limit, offset, cat_filter)

    # Get unread count
    unread_count = manager.get_unread_count(current_user["id"])

    return NotificationListResponse(
        notifications=[
            NotificationResponse(
                id=n.id,
                title=n.title,
                message=n.message,
                category=n.category.value,
                priority=n.priority.value,
                agent_id=n.agent_id,
                ticker=n.ticker,
                action_url=n.action_url,
                read=n.read,
                created_at=n.created_at.isoformat() if n.created_at else None,
            )
            for n in notifications
        ],
        unread_count=unread_count,
        total=len(notifications),
    )


@router.get("/unread/count")
async def get_unread_count(
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict[str, int]:
    """Get count of unread notifications."""
    manager = InAppNotificationManager(db)
    count = manager.get_unread_count(current_user["id"])
    return {"count": count}


@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict[str, bool]:
    """Mark a notification as read."""
    manager = InAppNotificationManager(db)
    success = manager.mark_as_read(notification_id, current_user["id"])
    return {"success": success}


@router.post("/read-all")
async def mark_all_as_read(
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict[str, int]:
    """Mark all notifications as read."""
    manager = InAppNotificationManager(db)
    count = manager.mark_all_as_read(current_user["id"])
    return {"marked_read": count}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict[str, bool]:
    """Delete a notification."""
    manager = InAppNotificationManager(db)
    success = manager.delete(notification_id, current_user["id"])
    return {"success": success}


# ============================================================================
# Unsubscribe Endpoints
# ============================================================================


@router.post("/unsubscribe")
async def unsubscribe(
    request: UnsubscribeRequest,
    db: Client = Depends(get_db),
) -> dict[str, str]:
    """
    Unsubscribe from notifications using token from email.

    No authentication required - token serves as verification.
    """
    manager = PreferencesManager(db)

    # Find user by token
    prefs = manager.get_user_by_unsubscribe_token(request.token)
    if not prefs:
        raise HTTPException(status_code=404, detail="Invalid unsubscribe token")

    # Update preferences based on request
    if request.notification_type:
        # Unsubscribe from specific type
        try:
            notif_type = NotificationType(request.notification_type)
            update_map = {
                NotificationType.DAILY_REPORT: "daily_report_enabled",
                NotificationType.TEAM_SUMMARY: "team_summary_enabled",
                NotificationType.WEEKLY_DIGEST: "weekly_digest_enabled",
                NotificationType.ALERTS_STOP_LOSS: "alerts_stop_loss",
                NotificationType.ALERTS_TARGET_HIT: "alerts_target_hit",
                NotificationType.ALERTS_POSITION: "alerts_position",
                NotificationType.ALERTS_AGENT: "alerts_agent",
                NotificationType.MARKETING: "marketing_enabled",
            }
            field = update_map.get(notif_type)
            if field:
                manager.update(prefs.user_id, {field: False})
                return {
                    "message": f"Unsubscribed from {request.notification_type} notifications"
                }
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid notification type")
    else:
        # Unsubscribe from all emails
        manager.update(prefs.user_id, {"email_enabled": False})
        return {"message": "Unsubscribed from all email notifications"}

    return {"message": "Unsubscribe request processed"}


@router.get("/unsubscribe/{token}")
async def unsubscribe_page(
    token: str,
    db: Client = Depends(get_db),
) -> dict[str, Any]:
    """
    Get unsubscribe page data.

    Returns user info and current preferences for the unsubscribe page.
    """
    manager = PreferencesManager(db)

    prefs = manager.get_user_by_unsubscribe_token(token)
    if not prefs:
        raise HTTPException(status_code=404, detail="Invalid unsubscribe token")

    return {
        "valid": True,
        "email_enabled": prefs.email_enabled,
        "preferences": {
            "daily_report": prefs.daily_report_enabled,
            "team_summary": prefs.team_summary_enabled,
            "weekly_digest": prefs.weekly_digest_enabled,
            "alerts": prefs.alerts_stop_loss
            or prefs.alerts_target_hit
            or prefs.alerts_agent,
            "marketing": prefs.marketing_enabled,
        },
    }


# ============================================================================
# Email Testing Endpoints (Development)
# ============================================================================


@router.post("/send-welcome", include_in_schema=False)
async def send_welcome_email(
    request: SendWelcomeRequest,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict[str, Any]:
    """
    Send a welcome email (development/testing endpoint).

    Requires authentication and is hidden from API docs.
    """
    email_client = get_email_client()

    if not email_client.is_configured:
        raise HTTPException(status_code=503, detail="Email service not configured")

    # Generate email content
    data = WelcomeData(user_name=request.name, user_email=request.email)
    html = WelcomeTemplate.render(data)
    text = WelcomeTemplate.render_plain_text(data)

    # Replace placeholders
    placeholders = {
        "{{dashboard_url}}": "https://app.agentfund.ai",
        "{{docs_url}}": "https://docs.agentfund.ai",
        "{{unsubscribe_url}}": "https://app.agentfund.ai/unsubscribe",
        "{{preferences_url}}": "https://app.agentfund.ai/settings/notifications",
    }
    for placeholder, value in placeholders.items():
        html = html.replace(placeholder, value)
        text = text.replace(placeholder, value)

    # Send email
    result = email_client.send(
        to=request.email,
        subject="Welcome to AgentFund!",
        html=html,
        text=text,
    )

    return {
        "success": result.success,
        "message_id": result.message_id,
        "error": result.error,
    }


@router.get("/email/status")
async def get_email_status(
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Get email service status."""
    client = get_email_client()
    return client.get_stats()
