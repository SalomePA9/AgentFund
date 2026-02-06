"""
Email client for sending notifications via Resend.

Provides a wrapper around the Resend API with error handling,
retry logic, and tracking.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import resend

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class EmailResult:
    """Result of an email send operation."""

    success: bool
    message_id: str | None = None
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class EmailClient:
    """
    Email client using Resend for delivery.

    Features:
    - Automatic API key configuration
    - Error handling with detailed logging
    - Send tracking for monitoring
    - Support for HTML and plain text emails
    """

    # Default sender address
    DEFAULT_FROM = "AgentFund <notifications@agentfund.ai>"

    # Email send limits
    MAX_RECIPIENTS = 50  # Resend limit per request
    MAX_ATTACHMENTS = 10

    def __init__(self, api_key: str | None = None):
        """
        Initialize email client.

        Args:
            api_key: Resend API key (uses settings if not provided)
        """
        self.api_key = api_key or settings.resend_api_key
        self._configured = False
        self._send_count = 0
        self._error_count = 0

        if self.api_key:
            resend.api_key = self.api_key
            self._configured = True
            logger.info("Resend email client configured")
        else:
            logger.warning("No Resend API key configured - emails disabled")

    @property
    def is_configured(self) -> bool:
        """Check if client is configured with API key."""
        return self._configured

    @property
    def send_count(self) -> int:
        """Get total emails sent."""
        return self._send_count

    @property
    def error_count(self) -> int:
        """Get total send errors."""
        return self._error_count

    def send(
        self,
        to: str | list[str],
        subject: str,
        html: str | None = None,
        text: str | None = None,
        from_email: str | None = None,
        reply_to: str | None = None,
        cc: str | list[str] | None = None,
        bcc: str | list[str] | None = None,
        headers: dict[str, str] | None = None,
        tags: list[dict[str, str]] | None = None,
    ) -> EmailResult:
        """
        Send an email.

        Args:
            to: Recipient email(s)
            subject: Email subject line
            html: HTML content
            text: Plain text content (fallback)
            from_email: Sender email (uses default if not provided)
            reply_to: Reply-to address
            cc: CC recipients
            bcc: BCC recipients
            headers: Custom email headers
            tags: Resend tags for tracking

        Returns:
            EmailResult with success status and message ID
        """
        if not self._configured:
            logger.warning("Email send attempted but client not configured")
            return EmailResult(
                success=False,
                error="Email client not configured - missing API key",
            )

        # Validate inputs
        if not to:
            return EmailResult(success=False, error="No recipient specified")
        if not subject:
            return EmailResult(success=False, error="No subject specified")
        if not html and not text:
            return EmailResult(success=False, error="No content specified")

        # Normalize recipients to list
        recipients = [to] if isinstance(to, str) else list(to)

        if len(recipients) > self.MAX_RECIPIENTS:
            return EmailResult(
                success=False,
                error=f"Too many recipients (max {self.MAX_RECIPIENTS})",
            )

        # Build email params
        params: dict[str, Any] = {
            "from": from_email or self.DEFAULT_FROM,
            "to": recipients,
            "subject": subject,
        }

        if html:
            params["html"] = html
        if text:
            params["text"] = text
        if reply_to:
            params["reply_to"] = reply_to
        if cc:
            params["cc"] = [cc] if isinstance(cc, str) else cc
        if bcc:
            params["bcc"] = [bcc] if isinstance(bcc, str) else bcc
        if headers:
            params["headers"] = headers
        if tags:
            params["tags"] = tags

        try:
            response = resend.Emails.send(params)
            self._send_count += 1

            # Resend returns {"id": "..."} on success
            message_id = response.get("id") if isinstance(response, dict) else None

            logger.info(
                f"Email sent successfully: {subject} -> {recipients[0]}"
                + (f" (+{len(recipients) - 1} more)" if len(recipients) > 1 else "")
            )

            return EmailResult(success=True, message_id=message_id)

        except resend.ResendError as e:
            self._error_count += 1
            error_msg = str(e)
            logger.error(f"Resend API error: {error_msg}")
            return EmailResult(success=False, error=error_msg)

        except Exception as e:
            self._error_count += 1
            error_msg = f"Unexpected error sending email: {e}"
            logger.error(error_msg)
            return EmailResult(success=False, error=error_msg)

    def send_batch(
        self,
        emails: list[dict[str, Any]],
    ) -> list[EmailResult]:
        """
        Send multiple emails in batch.

        Args:
            emails: List of email params (same as send() args)

        Returns:
            List of EmailResult for each email
        """
        results = []
        for email in emails:
            result = self.send(**email)
            results.append(result)
        return results

    def get_stats(self) -> dict[str, Any]:
        """Get email send statistics."""
        return {
            "configured": self._configured,
            "total_sent": self._send_count,
            "total_errors": self._error_count,
            "success_rate": (
                (self._send_count / (self._send_count + self._error_count) * 100)
                if (self._send_count + self._error_count) > 0
                else 100.0
            ),
        }


# Singleton instance
_client_instance: EmailClient | None = None


def get_email_client() -> EmailClient:
    """Get or create the singleton EmailClient instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = EmailClient()
    return _client_instance
