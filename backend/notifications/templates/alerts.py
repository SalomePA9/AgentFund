"""
Alert email templates.

Generates emails for important trading events like stop losses,
profit targets, and other significant activities.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from notifications.templates.base import BaseTemplate


class AlertType(Enum):
    """Types of trading alerts."""

    STOP_LOSS = "stop_loss"
    TARGET_HIT = "target_hit"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    AGENT_PAUSED = "agent_paused"
    AGENT_ERROR = "agent_error"
    DAILY_LIMIT = "daily_limit"
    UNUSUAL_ACTIVITY = "unusual_activity"


@dataclass
class AlertData:
    """Data for alert emails."""

    # Alert info
    alert_type: AlertType
    title: str
    message: str

    # Agent info
    agent_id: str
    agent_name: str
    strategy_type: str

    # Trade details (optional)
    ticker: str | None = None
    shares: int | None = None
    price: float | None = None
    entry_price: float | None = None
    pnl: float | None = None
    pnl_pct: float | None = None

    # Additional context
    details: dict[str, Any] | None = None
    timestamp: datetime | None = None
    severity: str = "info"  # info, warning, critical


class AlertTemplate(BaseTemplate):
    """Template for alert emails."""

    # Alert type configurations
    ALERT_CONFIG = {
        AlertType.STOP_LOSS: {
            "icon": "🛑",
            "color": "danger",
            "badge_class": "badge-danger",
        },
        AlertType.TARGET_HIT: {
            "icon": "🎯",
            "color": "success",
            "badge_class": "badge-success",
        },
        AlertType.POSITION_OPENED: {
            "icon": "📈",
            "color": "accent",
            "badge_class": "badge-success",
        },
        AlertType.POSITION_CLOSED: {
            "icon": "📉",
            "color": "warning",
            "badge_class": "badge-warning",
        },
        AlertType.AGENT_PAUSED: {
            "icon": "⏸️",
            "color": "warning",
            "badge_class": "badge-warning",
        },
        AlertType.AGENT_ERROR: {
            "icon": "⚠️",
            "color": "danger",
            "badge_class": "badge-danger",
        },
        AlertType.DAILY_LIMIT: {
            "icon": "📊",
            "color": "warning",
            "badge_class": "badge-warning",
        },
        AlertType.UNUSUAL_ACTIVITY: {
            "icon": "👁️",
            "color": "warning",
            "badge_class": "badge-warning",
        },
    }

    @classmethod
    def render(cls, data: AlertData) -> str:
        """
        Render the alert email.

        Args:
            data: Alert data

        Returns:
            Complete HTML email string
        """
        config = cls.ALERT_CONFIG.get(
            data.alert_type,
            {"icon": "📌", "color": "accent", "badge_class": "badge-warning"},
        )
        color = cls.COLORS.get(config["color"], cls.COLORS["accent"])
        timestamp = data.timestamp or datetime.utcnow()
        time_str = timestamp.strftime("%I:%M %p ET")

        # Build the email body
        body = f"""
        <!-- Alert Header -->
        <div class="card" style="border-left: 4px solid {color};">
            <div style="display: flex; align-items: center; margin-bottom: 16px;">
                <span style="font-size: 32px; margin-right: 16px;">{config['icon']}</span>
                <div>
                    <span class="badge {config['badge_class']}">{data.alert_type.value.replace('_', ' ').upper()}</span>
                    <h1 style="margin-top: 8px; margin-bottom: 0;">{data.title}</h1>
                </div>
            </div>

            <p style="font-size: 16px; color: {cls.COLORS['text_primary']}; margin-bottom: 16px;">
                {data.message}
            </p>

            <div style="font-size: 12px; color: {cls.COLORS['text_muted']};">
                {time_str} · {data.agent_name}
            </div>
        </div>

        {cls._render_trade_details(data)}

        <!-- Agent Info -->
        <div class="card">
            <h3>Agent Information</h3>
            <table style="width: 100%;">
                <tr>
                    <td style="border: none; padding: 8px 0; color: {cls.COLORS['text_muted']};">Agent</td>
                    <td style="border: none; padding: 8px 0; text-align: right; font-weight: 500;">{data.agent_name}</td>
                </tr>
                <tr>
                    <td style="border: none; padding: 8px 0; color: {cls.COLORS['text_muted']};">Strategy</td>
                    <td style="border: none; padding: 8px 0; text-align: right;">{data.strategy_type.replace('_', ' ').title()}</td>
                </tr>
            </table>
        </div>

        {cls._render_additional_details(data)}

        <!-- CTA -->
        <div class="card" style="text-align: center;">
            <a href="{{{{dashboard_url}}}}/agents/{data.agent_id}" class="button">
                View Agent Details
            </a>
        </div>
        """

        preheader = f"{config['icon']} {data.title}: {data.message[:100]}"

        return cls.wrap_html(
            title=f"Alert: {data.title} | AgentFund",
            body=body,
            preheader=preheader,
        )

    @classmethod
    def _render_trade_details(cls, data: AlertData) -> str:
        """Render trade details if available."""
        if not data.ticker:
            return ""

        rows = [
            f"""
            <tr>
                <td style="border: none; padding: 8px 0; color: {cls.COLORS['text_muted']};">Ticker</td>
                <td style="border: none; padding: 8px 0; text-align: right; font-weight: 600; font-size: 18px;">{data.ticker}</td>
            </tr>
            """
        ]

        if data.shares is not None:
            rows.append(f"""
                <tr>
                    <td style="border: none; padding: 8px 0; color: {cls.COLORS['text_muted']};">Shares</td>
                    <td style="border: none; padding: 8px 0; text-align: right;" class="mono">{data.shares:,}</td>
                </tr>
            """)

        if data.entry_price is not None:
            rows.append(f"""
                <tr>
                    <td style="border: none; padding: 8px 0; color: {cls.COLORS['text_muted']};">Entry Price</td>
                    <td style="border: none; padding: 8px 0; text-align: right;" class="mono">${data.entry_price:,.2f}</td>
                </tr>
            """)

        if data.price is not None:
            label = "Exit Price" if data.alert_type in [AlertType.STOP_LOSS, AlertType.TARGET_HIT, AlertType.POSITION_CLOSED] else "Price"
            rows.append(f"""
                <tr>
                    <td style="border: none; padding: 8px 0; color: {cls.COLORS['text_muted']};">{label}</td>
                    <td style="border: none; padding: 8px 0; text-align: right;" class="mono">${data.price:,.2f}</td>
                </tr>
            """)

        if data.pnl is not None:
            pnl_class = "positive" if data.pnl >= 0 else "negative"
            rows.append(f"""
                <tr>
                    <td style="border: none; padding: 8px 0; color: {cls.COLORS['text_muted']};">P&L</td>
                    <td style="border: none; padding: 8px 0; text-align: right;">
                        <span class="mono {pnl_class}">${data.pnl:+,.2f}</span>
                        {f'<span class="mono {pnl_class}" style="margin-left: 8px;">({data.pnl_pct:+.2f}%)</span>' if data.pnl_pct is not None else ''}
                    </td>
                </tr>
            """)

        return f"""
        <div class="card">
            <h3>Trade Details</h3>
            <table style="width: 100%;">
                {''.join(rows)}
            </table>
        </div>
        """

    @classmethod
    def _render_additional_details(cls, data: AlertData) -> str:
        """Render additional details if provided."""
        if not data.details:
            return ""

        rows = []
        for key, value in data.details.items():
            label = key.replace("_", " ").title()
            rows.append(f"""
                <tr>
                    <td style="border: none; padding: 8px 0; color: {cls.COLORS['text_muted']};">{label}</td>
                    <td style="border: none; padding: 8px 0; text-align: right;">{value}</td>
                </tr>
            """)

        return f"""
        <div class="card">
            <h3>Additional Details</h3>
            <table style="width: 100%;">
                {''.join(rows)}
            </table>
        </div>
        """

    @classmethod
    def render_plain_text(cls, data: AlertData) -> str:
        """Render plain text version of the alert."""
        config = cls.ALERT_CONFIG.get(data.alert_type, {"icon": "📌"})
        timestamp = data.timestamp or datetime.utcnow()
        time_str = timestamp.strftime("%I:%M %p ET")

        text = f"""
{config['icon']} AGENTFUND ALERT
========================

{data.alert_type.value.replace('_', ' ').upper()}: {data.title}

{data.message}

Time: {time_str}
Agent: {data.agent_name}
Strategy: {data.strategy_type.replace('_', ' ').title()}
"""

        if data.ticker:
            text += f"""
TRADE DETAILS
-------------
Ticker: {data.ticker}
"""
            if data.shares is not None:
                text += f"Shares: {data.shares:,}\n"
            if data.entry_price is not None:
                text += f"Entry Price: ${data.entry_price:,.2f}\n"
            if data.price is not None:
                text += f"Price: ${data.price:,.2f}\n"
            if data.pnl is not None:
                pnl_str = f"${data.pnl:+,.2f}"
                if data.pnl_pct is not None:
                    pnl_str += f" ({data.pnl_pct:+.2f}%)"
                text += f"P&L: {pnl_str}\n"

        if data.details:
            text += """
ADDITIONAL DETAILS
------------------
"""
            for key, value in data.details.items():
                label = key.replace("_", " ").title()
                text += f"{label}: {value}\n"

        text += f"""
------------------------
View details at {{{{dashboard_url}}}}/agents/{data.agent_id}

To unsubscribe from alerts, visit {{{{unsubscribe_url}}}}
"""

        return text.strip()

    @classmethod
    def create_stop_loss_alert(
        cls,
        agent_id: str,
        agent_name: str,
        strategy_type: str,
        ticker: str,
        shares: int,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
    ) -> AlertData:
        """Create a stop loss alert data object."""
        return AlertData(
            alert_type=AlertType.STOP_LOSS,
            title=f"Stop Loss Triggered: {ticker}",
            message=f"{agent_name} exited {shares:,} shares of {ticker} at ${exit_price:.2f} due to stop loss. Position P&L: ${pnl:+,.2f} ({pnl_pct:+.2f}%)",
            agent_id=agent_id,
            agent_name=agent_name,
            strategy_type=strategy_type,
            ticker=ticker,
            shares=shares,
            entry_price=entry_price,
            price=exit_price,
            pnl=pnl,
            pnl_pct=pnl_pct,
            severity="warning",
        )

    @classmethod
    def create_target_hit_alert(
        cls,
        agent_id: str,
        agent_name: str,
        strategy_type: str,
        ticker: str,
        shares: int,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
    ) -> AlertData:
        """Create a target hit alert data object."""
        return AlertData(
            alert_type=AlertType.TARGET_HIT,
            title=f"Profit Target Hit: {ticker}",
            message=f"{agent_name} closed {shares:,} shares of {ticker} at ${exit_price:.2f} - target reached! Position P&L: ${pnl:+,.2f} ({pnl_pct:+.2f}%)",
            agent_id=agent_id,
            agent_name=agent_name,
            strategy_type=strategy_type,
            ticker=ticker,
            shares=shares,
            entry_price=entry_price,
            price=exit_price,
            pnl=pnl,
            pnl_pct=pnl_pct,
            severity="info",
        )
