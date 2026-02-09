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

    # Macro risk overlay
    macro_regime: str | None = None
    macro_scale_factor: float | None = None
    macro_composite_score: float | None = None
    macro_warnings: list[str] | None = None
    credit_spread_signal: float | None = None
    yield_curve_signal: float | None = None
    vol_regime_signal: float | None = None
    vix_level: float | None = None
    vix_regime: str | None = None
    seasonality_signal: float | None = None
    insider_breadth_signal: float | None = None


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

        {cls._render_macro_overlay(data)}

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
            metrics.append(f"""
                <div class="metric">
                    <div class="metric-label">Sharpe Ratio</div>
                    <div class="metric-value">{cls.format_number(data.sharpe_ratio, 2)}</div>
                </div>
            """)

        if data.win_rate is not None:
            metrics.append(f"""
                <div class="metric">
                    <div class="metric-label">Win Rate</div>
                    <div class="metric-value">{cls.format_number(data.win_rate, 1)}%</div>
                </div>
            """)

        if data.max_drawdown is not None:
            metrics.append(f"""
                <div class="metric">
                    <div class="metric-label">Max Drawdown</div>
                    <div class="metric-value negative">{cls.format_number(abs(data.max_drawdown), 2)}%</div>
                </div>
            """)

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
    def _render_macro_overlay(cls, data: DailyReportData) -> str:
        """Render macro risk overlay section."""
        if not data.macro_regime:
            return ""

        # Regime badge colour
        regime_colors = {
            "normal": cls.COLORS.get("success", "#22c55e"),
            "elevated_risk": cls.COLORS.get("warning", "#eab308"),
            "high_risk": cls.COLORS.get("danger", "#ef4444"),
        }
        regime_color = regime_colors.get(
            data.macro_regime, cls.COLORS.get("text_primary", "#fff")
        )
        regime_display = data.macro_regime.replace("_", " ").title()

        # Scale factor description
        scale_str = ""
        if data.macro_scale_factor is not None:
            pct = (data.macro_scale_factor - 1.0) * 100
            direction = "reduced" if pct < 0 else "increased"
            scale_str = f'<div class="metric"><div class="metric-label">Position Sizing</div><div class="metric-value">{direction} {abs(pct):.0f}%</div></div>'

        composite_str = ""
        if data.macro_composite_score is not None:
            composite_str = f'<div class="metric"><div class="metric-label">Composite Score</div><div class="metric-value">{data.macro_composite_score:+.0f} / 100</div></div>'

        # Build signal rows
        signals = []
        signal_map = [
            ("Credit Spreads", data.credit_spread_signal),
            ("Yield Curve", data.yield_curve_signal),
            ("Volatility", data.vol_regime_signal),
            ("Seasonality", data.seasonality_signal),
            ("Insider Breadth", data.insider_breadth_signal),
        ]
        for label, value in signal_map:
            if value is not None:
                if value > 10:
                    sentiment = "bullish"
                    color = cls.COLORS.get("success", "#22c55e")
                elif value < -10:
                    sentiment = "bearish"
                    color = cls.COLORS.get("danger", "#ef4444")
                else:
                    sentiment = "neutral"
                    color = cls.COLORS.get("text_secondary", "#a1a1aa")
                signals.append(
                    f'<tr><td style="padding: 4px 8px;">{label}</td>'
                    f'<td style="padding: 4px 8px; text-align: right;" class="mono">{value:+.0f}</td>'
                    f'<td style="padding: 4px 8px; color: {color};">{sentiment}</td></tr>'
                )

        signal_table = ""
        if signals:
            vix_note = ""
            if data.vix_level is not None:
                vix_regime_str = f" ({data.vix_regime})" if data.vix_regime else ""
                vix_note = f'<p style="font-size: 12px; color: {cls.COLORS.get("text_secondary", "#a1a1aa")}; margin-top: 8px;">VIX: {data.vix_level:.1f}{vix_regime_str}</p>'

            signal_table = f"""
                <div class="divider"></div>
                <h4 style="margin-bottom: 8px;">Signal Readings</h4>
                <table style="width: 100%; font-size: 14px;">
                    {''.join(signals)}
                </table>
                {vix_note}
            """

        # Warnings
        warnings_html = ""
        if data.macro_warnings:
            warning_items = "".join(
                f'<li style="color: {cls.COLORS.get("warning", "#eab308")}; font-size: 13px;">{w}</li>'
                for w in data.macro_warnings
            )
            warnings_html = f'<div class="divider"></div><ul style="margin: 0; padding-left: 16px;">{warning_items}</ul>'

        return f"""
        <div class="card">
            <h3>Macro Risk Overlay</h3>
            <div style="display: flex; flex-wrap: wrap; margin: -4px;">
                <div class="metric">
                    <div class="metric-label">Regime</div>
                    <div class="metric-value" style="color: {regime_color};">{regime_display}</div>
                </div>
                {scale_str}
                {composite_str}
            </div>
            {signal_table}
            {warnings_html}
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
            entry_price = pos.get("entry_price") or 0
            current_price = pos.get("current_price") or 0
            pnl_pct = pos.get("unrealized_pnl_pct", 0)

            rows.append(f"""
                <tr>
                    <td style="font-weight: 500;">{ticker}</td>
                    <td class="mono">{shares}</td>
                    <td class="mono">${entry_price:,.2f}</td>
                    <td class="mono">${current_price:,.2f}</td>
                    <td>{cls.format_percent(pnl_pct)}</td>
                </tr>
            """)

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
            details_raw = act.get("details", "")

            # Format details dict as readable text instead of raw repr
            if isinstance(details_raw, dict):
                detail_parts = []
                if details_raw.get("reason"):
                    detail_parts.append(str(details_raw["reason"]))
                if details_raw.get("order_action"):
                    detail_parts.append(details_raw["order_action"])
                if details_raw.get("target_weight") is not None:
                    detail_parts.append(
                        f"weight: {details_raw['target_weight']:.1%}"
                    )
                if details_raw.get("signal_strength") is not None:
                    detail_parts.append(
                        f"signal: {details_raw['signal_strength']:+.0f}"
                    )
                details = " | ".join(detail_parts) if detail_parts else ""
            else:
                details = str(details_raw)

            # Color by activity type
            if activity_type in ["BUY", "ENTRY"]:
                badge_class = "badge-success"
            elif activity_type in ["SELL", "EXIT", "STOP_LOSS"]:
                badge_class = "badge-danger"
            else:
                badge_class = "badge-warning"

            items.append(f"""
                <div style="display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid {cls.COLORS['border']};">
                    <span class="badge {badge_class}" style="margin-right: 12px;">{activity_type}</span>
                    <span style="font-weight: 500; margin-right: 8px;">{ticker}</span>
                    <span style="color: {cls.COLORS['text_secondary']}; font-size: 14px;">{details}</span>
                </div>
            """)

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

        if data.macro_regime:
            regime_display = data.macro_regime.replace("_", " ").title()
            text += f"""
MACRO RISK OVERLAY
-------------------
Regime: {regime_display}
"""
            if data.macro_scale_factor is not None:
                pct = (data.macro_scale_factor - 1.0) * 100
                direction = "reduced" if pct < 0 else "increased"
                text += f"Position Sizing: {direction} by {abs(pct):.0f}% (scale {data.macro_scale_factor:.2f})\n"
            if data.macro_composite_score is not None:
                text += f"Composite Score: {data.macro_composite_score:+.0f} / 100\n"

            signal_map = [
                ("Credit Spreads", data.credit_spread_signal),
                ("Yield Curve", data.yield_curve_signal),
                ("Volatility", data.vol_regime_signal),
                ("Seasonality", data.seasonality_signal),
                ("Insider Breadth", data.insider_breadth_signal),
            ]
            signal_lines = []
            for label, value in signal_map:
                if value is not None:
                    sentiment = (
                        "bullish"
                        if value > 10
                        else ("bearish" if value < -10 else "neutral")
                    )
                    signal_lines.append(f"  {label}: {value:+.0f} ({sentiment})")
            if signal_lines:
                text += "Signals:\n" + "\n".join(signal_lines) + "\n"
            if data.vix_level is not None:
                vix_regime_str = f" ({data.vix_regime})" if data.vix_regime else ""
                text += f"  VIX: {data.vix_level:.1f}{vix_regime_str}\n"
            if data.macro_warnings:
                text += "Warnings:\n"
                for w in data.macro_warnings:
                    text += f"  - {w}\n"

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
                details_raw = act.get("details", "")
                if isinstance(details_raw, dict):
                    detail_parts = []
                    if details_raw.get("reason"):
                        detail_parts.append(str(details_raw["reason"]))
                    if details_raw.get("order_action"):
                        detail_parts.append(details_raw["order_action"])
                    details = " | ".join(detail_parts) if detail_parts else ""
                else:
                    details = str(details_raw)
                text += f"[{activity_type}] {ticker} - {details}\n"

        text += """
-------------------
View full details at {{dashboard_url}}

To unsubscribe, visit {{unsubscribe_url}}
"""

        return text.strip()
