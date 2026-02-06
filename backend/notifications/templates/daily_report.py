"""
Daily report email template.

Generates a personalized daily performance report for an agent,
including the LLM-generated summary, metrics, and activity.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from notifications.templates.base import BaseTemplate


@dataclass
class DailyReportData:
    """Data for daily report email."""

    # Agent info
    agent_id: str
    agent_name: str
    persona: str
    strategy_type: str

    # Performance metrics
    total_value: float
    daily_return_pct: float
    total_return_pct: float
    positions_count: int

    # Optional metrics
    sharpe_ratio: float | None = None
    win_rate: float | None = None
    max_drawdown: float | None = None

    # Report content
    report_content: str = ""  # LLM-generated report
    report_date: date | None = None

    # Positions (top 5)
    positions: list[dict[str, Any]] | None = None

    # Recent activities
    activities: list[dict[str, Any]] | None = None


class DailyReportTemplate(BaseTemplate):
    """Template for daily agent report emails."""

    @classmethod
    def render(cls, data: DailyReportData, user_name: str = "Investor") -> str:
        """
        Render the daily report email.

        Args:
            data: Report data
            user_name: Recipient name for greeting

        Returns:
            Complete HTML email string
        """
        report_date = data.report_date or date.today()
        date_str = report_date.strftime("%B %d, %Y")

        # Build the email body
        body = f"""
        <!-- Header -->
        <div class="card">
            <h1>Daily Report: {data.agent_name}</h1>
            <p style="margin-bottom: 0;">{date_str}</p>
        </div>

        <!-- Key Metrics -->
        <div class="card">
            <h3>Performance Summary</h3>
            <div style="display: flex; flex-wrap: wrap; margin: -4px;">
                <div class="metric">
                    <div class="metric-label">Portfolio Value</div>
                    <div class="metric-value">{cls.format_currency(data.total_value)}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Today's Return</div>
                    <div class="metric-value">{cls.format_percent(data.daily_return_pct)}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Total Return</div>
                    <div class="metric-value">{cls.format_percent(data.total_return_pct)}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Open Positions</div>
                    <div class="metric-value">{cls.format_number(data.positions_count)}</div>
                </div>
            </div>

            {cls._render_advanced_metrics(data)}
        </div>

        <!-- Agent Report (LLM-generated) -->
        <div class="card">
            <h3>{data.agent_name}'s Analysis</h3>
            <div style="color: {cls.COLORS['text_primary']}; line-height: 1.7;">
                {data.report_content if data.report_content else '<em style="color: ' + cls.COLORS['text_muted'] + ';">No analysis available for today.</em>'}
            </div>
        </div>

        {cls._render_positions(data)}

        {cls._render_activities(data)}

        <!-- CTA -->
        <div class="card" style="text-align: center;">
            <p style="margin-bottom: 16px;">View full details and chat with {data.agent_name}</p>
            <a href="{{{{dashboard_url}}}}/agents/{data.agent_id}" class="button">
                View Agent Dashboard
            </a>
        </div>
        """

        preheader = f"{data.agent_name}: {data.daily_return_pct:+.2f}% today, ${data.total_value:,.0f} total"

        return cls.wrap_html(
            title=f"Daily Report - {data.agent_name} | AgentFund",
            body=body,
            preheader=preheader,
        )

    @classmethod
    def _render_advanced_metrics(cls, data: DailyReportData) -> str:
        """Render advanced metrics if available."""
        metrics = []

        if data.sharpe_ratio is not None:
            metrics.append(
                f"""
                <div class="metric">
                    <div class="metric-label">Sharpe Ratio</div>
                    <div class="metric-value">{cls.format_number(data.sharpe_ratio, 2)}</div>
                </div>
            """
            )

        if data.win_rate is not None:
            metrics.append(
                f"""
                <div class="metric">
                    <div class="metric-label">Win Rate</div>
                    <div class="metric-value">{cls.format_number(data.win_rate, 1)}%</div>
                </div>
            """
            )

        if data.max_drawdown is not None:
            metrics.append(
                f"""
                <div class="metric">
                    <div class="metric-label">Max Drawdown</div>
                    <div class="metric-value negative">{cls.format_number(abs(data.max_drawdown), 2)}%</div>
                </div>
            """
            )

        if not metrics:
            return ""

        return f"""
            <div class="divider"></div>
            <h3>Risk Metrics</h3>
            <div style="display: flex; flex-wrap: wrap; margin: -4px;">
                {''.join(metrics)}
            </div>
        """

    @classmethod
    def _render_positions(cls, data: DailyReportData) -> str:
        """Render positions table."""
        if not data.positions:
            return ""

        rows = []
        for pos in data.positions[:5]:
            ticker = pos.get("ticker", "???")
            shares = pos.get("shares", 0)
            entry_price = pos.get("entry_price", 0)
            current_price = pos.get("current_price", 0)
            pnl_pct = pos.get("unrealized_pnl_pct", 0)

            rows.append(
                f"""
                <tr>
                    <td style="font-weight: 500;">{ticker}</td>
                    <td class="mono">{shares}</td>
                    <td class="mono">${entry_price:,.2f}</td>
                    <td class="mono">${current_price:,.2f}</td>
                    <td>{cls.format_percent(pnl_pct)}</td>
                </tr>
            """
            )

        return f"""
        <div class="card">
            <h3>Current Positions</h3>
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Shares</th>
                        <th>Entry</th>
                        <th>Current</th>
                        <th>P&L</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
            {f'<p style="margin-top: 12px; margin-bottom: 0; font-size: 12px;">Showing top 5 of {data.positions_count} positions</p>' if data.positions_count > 5 else ''}
        </div>
        """

    @classmethod
    def _render_activities(cls, data: DailyReportData) -> str:
        """Render recent activities."""
        if not data.activities:
            return ""

        items = []
        for act in data.activities[:5]:
            activity_type = act.get("activity_type", "").upper()
            ticker = act.get("ticker", "")
            details = act.get("details", "")

            # Color by activity type
            if activity_type in ["BUY", "ENTRY"]:
                badge_class = "badge-success"
            elif activity_type in ["SELL", "EXIT", "STOP_LOSS"]:
                badge_class = "badge-danger"
            else:
                badge_class = "badge-warning"

            items.append(
                f"""
                <div style="display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid {cls.COLORS['border']};">
                    <span class="badge {badge_class}" style="margin-right: 12px;">{activity_type}</span>
                    <span style="font-weight: 500; margin-right: 8px;">{ticker}</span>
                    <span style="color: {cls.COLORS['text_secondary']}; font-size: 14px;">{details}</span>
                </div>
            """
            )

        return f"""
        <div class="card">
            <h3>Today's Activity</h3>
            {''.join(items)}
        </div>
        """

    @classmethod
    def render_plain_text(cls, data: DailyReportData) -> str:
        """Render plain text version of the report."""
        report_date = data.report_date or date.today()
        date_str = report_date.strftime("%B %d, %Y")

        text = f"""
DAILY REPORT: {data.agent_name}
{date_str}

PERFORMANCE SUMMARY
-------------------
Portfolio Value: ${data.total_value:,.2f}
Today's Return: {data.daily_return_pct:+.2f}%
Total Return: {data.total_return_pct:+.2f}%
Open Positions: {data.positions_count}
"""

        if data.sharpe_ratio is not None:
            text += f"Sharpe Ratio: {data.sharpe_ratio:.2f}\n"
        if data.win_rate is not None:
            text += f"Win Rate: {data.win_rate:.1f}%\n"
        if data.max_drawdown is not None:
            text += f"Max Drawdown: {abs(data.max_drawdown):.2f}%\n"

        if data.report_content:
            text += f"""
{data.agent_name}'S ANALYSIS
-------------------
{data.report_content}
"""

        if data.positions:
            text += """
CURRENT POSITIONS
-------------------
"""
            for pos in data.positions[:5]:
                ticker = pos.get("ticker", "???")
                shares = pos.get("shares", 0)
                pnl_pct = pos.get("unrealized_pnl_pct", 0)
                text += f"{ticker}: {shares} shares ({pnl_pct:+.2f}%)\n"

        if data.activities:
            text += """
TODAY'S ACTIVITY
-------------------
"""
            for act in data.activities[:5]:
                activity_type = act.get("activity_type", "").upper()
                ticker = act.get("ticker", "")
                details = act.get("details", "")
                text += f"[{activity_type}] {ticker} - {details}\n"

        text += """
-------------------
View full details at {{dashboard_url}}

To unsubscribe, visit {{unsubscribe_url}}
"""

        return text.strip()
