"""
Notification scheduler for timed email delivery.

Handles scheduling of daily reports, team summaries, and other
scheduled notifications based on user timezone preferences.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from supabase import Client

from notifications.email_client import EmailClient, get_email_client
from notifications.preferences import (
    NotificationPreferences,
    NotificationType,
    PreferencesManager,
)
from notifications.templates.daily_report import DailyReportData, DailyReportTemplate
from notifications.templates.team_summary import TeamSummaryData, TeamSummaryTemplate

logger = logging.getLogger(__name__)


# Standard timezones for delivery buckets
DELIVERY_TIMEZONES = [
    "America/New_York",  # ET (UTC-5/-4)
    "America/Chicago",  # CT (UTC-6/-5)
    "America/Denver",  # MT (UTC-7/-6)
    "America/Los_Angeles",  # PT (UTC-8/-7)
    "America/Phoenix",  # AZ (UTC-7, no DST)
    "Europe/London",  # GMT/BST (UTC+0/+1)
    "Europe/Paris",  # CET/CEST (UTC+1/+2)
    "Asia/Tokyo",  # JST (UTC+9)
    "Asia/Shanghai",  # CST (UTC+8)
    "Australia/Sydney",  # AEST/AEDT (UTC+10/+11)
]


@dataclass
class DeliveryWindow:
    """A window for notification delivery."""

    start_time: datetime
    end_time: datetime
    timezone: str
    local_hour: int


class TimezoneHelper:
    """
    Helper class for timezone operations.

    Handles conversion between user timezones and UTC for
    scheduling notification delivery.
    """

    @staticmethod
    def get_user_local_time(utc_time: datetime, timezone: str) -> datetime:
        """
        Convert UTC time to user's local time.

        Args:
            utc_time: Time in UTC
            timezone: User's timezone string

        Returns:
            Time in user's local timezone
        """
        try:
            utc = ZoneInfo("UTC")
            user_tz = ZoneInfo(timezone)

            # Ensure UTC time has tzinfo
            if utc_time.tzinfo is None:
                utc_time = utc_time.replace(tzinfo=utc)

            return utc_time.astimezone(user_tz)
        except Exception as e:
            logger.warning(f"Invalid timezone {timezone}, using UTC: {e}")
            return utc_time

    @staticmethod
    def get_utc_time(local_time: datetime, timezone: str) -> datetime:
        """
        Convert user's local time to UTC.

        Args:
            local_time: Time in user's timezone
            timezone: User's timezone string

        Returns:
            Time in UTC
        """
        try:
            user_tz = ZoneInfo(timezone)
            utc = ZoneInfo("UTC")

            # Set timezone if not present
            if local_time.tzinfo is None:
                local_time = local_time.replace(tzinfo=user_tz)

            return local_time.astimezone(utc)
        except Exception as e:
            logger.warning(f"Invalid timezone {timezone}, using UTC: {e}")
            return local_time

    @staticmethod
    def get_delivery_time_utc(
        delivery_time: time,
        timezone: str,
        reference_date: datetime | None = None,
    ) -> datetime:
        """
        Calculate UTC datetime for a local delivery time.

        Args:
            delivery_time: Local delivery time (HH:MM)
            timezone: User's timezone
            reference_date: Date to use (defaults to today)

        Returns:
            UTC datetime for delivery
        """
        if reference_date is None:
            reference_date = datetime.utcnow()

        try:
            user_tz = ZoneInfo(timezone)

            # Create datetime in user's timezone
            local_dt = datetime(
                reference_date.year,
                reference_date.month,
                reference_date.day,
                delivery_time.hour,
                delivery_time.minute,
                tzinfo=user_tz,
            )

            # Convert to UTC
            return local_dt.astimezone(ZoneInfo("UTC"))
        except Exception as e:
            logger.warning(f"Error calculating delivery time: {e}")
            return datetime.combine(reference_date.date(), delivery_time)

    @staticmethod
    def get_users_for_delivery_window(
        prefs_list: list[NotificationPreferences],
        current_utc: datetime,
        window_minutes: int = 15,
    ) -> list[NotificationPreferences]:
        """
        Filter users whose delivery time falls within the current window.

        Args:
            prefs_list: List of user preferences
            current_utc: Current UTC time
            window_minutes: Size of delivery window in minutes

        Returns:
            List of users due for delivery
        """
        result = []

        # Ensure current_utc is timezone-aware
        utc = ZoneInfo("UTC")
        if current_utc.tzinfo is None:
            current_utc = current_utc.replace(tzinfo=utc)

        window_start = current_utc - timedelta(minutes=window_minutes // 2)
        window_end = current_utc + timedelta(minutes=window_minutes // 2)

        for prefs in prefs_list:
            delivery_utc = TimezoneHelper.get_delivery_time_utc(
                prefs.daily_report_time,
                prefs.timezone,
                current_utc,
            )

            # Ensure delivery_utc is also timezone-aware for comparison
            if delivery_utc.tzinfo is None:
                delivery_utc = delivery_utc.replace(tzinfo=utc)

            # Check if within window
            if window_start <= delivery_utc <= window_end:
                result.append(prefs)

        return result


class NotificationScheduler:
    """
    Schedules and sends notifications based on user preferences.

    Handles the logic for determining when to send notifications
    and coordinates with the email client.
    """

    def __init__(
        self,
        db: "Client",
        email_client: EmailClient | None = None,
    ):
        """
        Initialize the scheduler.

        Args:
            db: Supabase client
            email_client: Email client (uses singleton if not provided)
        """
        self.db = db
        self.email_client = email_client or get_email_client()
        self.prefs_manager = PreferencesManager(db)
        self.timezone_helper = TimezoneHelper()

    def get_pending_daily_reports(
        self,
        current_utc: datetime | None = None,
    ) -> list[NotificationPreferences]:
        """
        Get users who should receive daily reports now.

        Args:
            current_utc: Current UTC time (defaults to now)

        Returns:
            List of user preferences for pending delivery
        """
        if current_utc is None:
            current_utc = datetime.utcnow()

        # Get all users with daily reports enabled
        all_prefs = self.prefs_manager.get_users_for_delivery(
            NotificationType.DAILY_REPORT
        )

        # Filter by delivery window
        return self.timezone_helper.get_users_for_delivery_window(
            all_prefs, current_utc
        )

    def send_daily_report(
        self,
        prefs: NotificationPreferences,
        report_data: DailyReportData,
    ) -> bool:
        """
        Send a daily report email.

        Args:
            prefs: User preferences
            report_data: Report data to send

        Returns:
            True if sent successfully
        """
        if not prefs.email_address:
            logger.warning(f"No email address for user {prefs.user_id}")
            return False

        html = DailyReportTemplate.render(report_data)
        text = DailyReportTemplate.render_plain_text(report_data)

        # Replace template placeholders
        html = self._replace_placeholders(html, prefs)
        text = self._replace_placeholders(text, prefs)

        result = self.email_client.send(
            to=prefs.email_address,
            subject=f"Daily Report: {report_data.agent_name} | {report_data.daily_return_pct:+.2f}%",
            html=html,
            text=text,
            tags=[
                {"name": "type", "value": "daily_report"},
                {"name": "agent_id", "value": report_data.agent_id},
            ],
        )

        if result.success:
            logger.info(
                f"Sent daily report for {report_data.agent_name} to {prefs.email_address}"
            )
        else:
            logger.error(f"Failed to send daily report: {result.error}")

        return result.success

    def send_team_summary(
        self,
        prefs: NotificationPreferences,
        summary_data: TeamSummaryData,
    ) -> bool:
        """
        Send a team summary email.

        Args:
            prefs: User preferences
            summary_data: Summary data to send

        Returns:
            True if sent successfully
        """
        if not prefs.email_address:
            logger.warning(f"No email address for user {prefs.user_id}")
            return False

        html = TeamSummaryTemplate.render(summary_data)
        text = TeamSummaryTemplate.render_plain_text(summary_data)

        # Replace template placeholders
        html = self._replace_placeholders(html, prefs)
        text = self._replace_placeholders(text, prefs)

        result = self.email_client.send(
            to=prefs.email_address,
            subject=f"Team Summary | {summary_data.total_daily_return_pct:+.2f}% Today",
            html=html,
            text=text,
            tags=[{"name": "type", "value": "team_summary"}],
        )

        if result.success:
            logger.info(f"Sent team summary to {prefs.email_address}")
        else:
            logger.error(f"Failed to send team summary: {result.error}")

        return result.success

    def _replace_placeholders(
        self, content: str, prefs: NotificationPreferences
    ) -> str:
        """Replace template placeholders with actual URLs."""
        # These would be configured in settings
        dashboard_url = "https://app.agentfund.ai"
        docs_url = "https://docs.agentfund.ai"

        # Generate unsubscribe URL
        unsubscribe_token = prefs.unsubscribe_token or "INVALID_TOKEN"
        unsubscribe_url = f"{dashboard_url}/unsubscribe/{unsubscribe_token}"
        preferences_url = f"{dashboard_url}/settings/notifications"

        replacements = {
            "{{dashboard_url}}": dashboard_url,
            "{{docs_url}}": docs_url,
            "{{unsubscribe_url}}": unsubscribe_url,
            "{{preferences_url}}": preferences_url,
        }

        for placeholder, value in replacements.items():
            content = content.replace(placeholder, value)

        return content


def process_daily_reports(db: "Client") -> dict[str, Any]:
    """
    Process and send all pending daily reports.

    This function should be called by a scheduled job.

    Args:
        db: Supabase client

    Returns:
        Dictionary with processing results
    """
    scheduler = NotificationScheduler(db)
    current_utc = datetime.utcnow()

    results = {
        "processed_at": current_utc.isoformat(),
        "users_checked": 0,
        "reports_sent": 0,
        "errors": 0,
    }

    # Get users due for delivery
    pending_users = scheduler.get_pending_daily_reports(current_utc)
    results["users_checked"] = len(pending_users)

    logger.info(f"Processing daily reports for {len(pending_users)} users")

    for prefs in pending_users:
        try:
            # Fetch user's agents and generate reports
            # This would integrate with the reports API
            agents_result = (
                db.table("agents")
                .select("*")
                .eq("user_id", prefs.user_id)
                .eq("status", "active")
                .execute()
            )

            for agent in agents_result.data or []:
                # Build report data (simplified - would use actual report generator)
                report_data = DailyReportData(
                    agent_id=agent["id"],
                    agent_name=agent["name"],
                    persona=agent.get("persona", "analytical"),
                    strategy_type=agent.get("strategy_type", "momentum"),
                    total_value=float(agent.get("total_value", 0) or 0),
                    daily_return_pct=float(agent.get("daily_return_pct", 0) or 0),
                    total_return_pct=float(
                        (
                            (
                                float(agent.get("total_value", 0) or 0)
                                / float(agent.get("allocated_capital", 1) or 1)
                            )
                            - 1
                        )
                        * 100
                    ),
                    positions_count=0,  # Would fetch from positions table
                )

                if scheduler.send_daily_report(prefs, report_data):
                    results["reports_sent"] += 1
                else:
                    results["errors"] += 1

        except Exception as e:
            logger.error(f"Error processing reports for user {prefs.user_id}: {e}")
            results["errors"] += 1

    logger.info(
        f"Daily report processing complete: {results['reports_sent']} sent, {results['errors']} errors"
    )

    return results
