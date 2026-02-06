"""
Team summary email template.

Generates a combined summary of all agents' performance,
providing a portfolio-wide view.
"""

from dataclasses import dataclass
from datetime import date

from notifications.templates.base import BaseTemplate


@dataclass
class AgentSummary:
    """Summary data for a single agent."""

    agent_id: str
    agent_name: str
    strategy_type: str
    status: str
    total_value: float
    daily_return_pct: float
    total_return_pct: float
    positions_count: int


@dataclass
class TeamSummaryData:
    """Data for team summary email."""

    # Overall metrics
    total_portfolio_value: float
    total_daily_return: float  # Dollar amount
    total_daily_return_pct: float
    total_return_pct: float
    total_positions: int

    # Agent summaries
    agents: list[AgentSummary]

    # Best/worst performers
    best_agent: AgentSummary | None = None
    worst_agent: AgentSummary | None = None

    # Summary content
    summary_content: str = ""  # LLM-generated summary
    summary_date: date | None = None


class TeamSummaryTemplate(BaseTemplate):
    """Template for team summary emails."""

    @classmethod
    def render(cls, data: TeamSummaryData, user_name: str = "Investor") -> str:
        """
        Render the team summary email.

        Args:
            data: Team summary data
            user_name: Recipient name for greeting

        Returns:
            Complete HTML email string
        """
        summary_date = data.summary_date or date.today()
        date_str = summary_date.strftime("%B %d, %Y")

        # Build the email body
        body = f"""
        <!-- Header -->
        <div class="card">
            <h1>Team Summary</h1>
            <p style="margin-bottom: 0;">{date_str}</p>
        </div>

        <!-- Overall Portfolio Metrics -->
        <div class="card">
            <h3>Portfolio Overview</h3>
            <div style="display: flex; flex-wrap: wrap; margin: -4px;">
                <div class="metric">
                    <div class="metric-label">Total Portfolio Value</div>
                    <div class="metric-value" style="font-size: 24px;">
                        {cls.format_currency(data.total_portfolio_value)}
                    </div>
                </div>
                <div class="metric">
                    <div class="metric-label">Today's P&L</div>
                    <div class="metric-value">
                        {cls.format_currency(data.total_daily_return, include_sign=True)}
                    </div>
                </div>
                <div class="metric">
                    <div class="metric-label">Today's Return</div>
                    <div class="metric-value">{cls.format_percent(data.total_daily_return_pct)}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Total Return</div>
                    <div class="metric-value">{cls.format_percent(data.total_return_pct)}</div>
                </div>
            </div>

            <div class="divider"></div>

            <div style="display: flex; flex-wrap: wrap; margin: -4px;">
                <div class="metric">
                    <div class="metric-label">Active Agents</div>
                    <div class="metric-value">{cls.format_number(len(data.agents))}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Total Positions</div>
                    <div class="metric-value">{cls.format_number(data.total_positions)}</div>
                </div>
            </div>
        </div>

        {cls._render_performers(data)}

        <!-- Team Summary (LLM-generated) -->
        <div class="card">
            <h3>Market Analysis</h3>
            <div style="color: {cls.COLORS['text_primary']}; line-height: 1.7;">
                {data.summary_content if data.summary_content else '<em style="color: ' + cls.COLORS['text_muted'] + ';">No analysis available for today.</em>'}
            </div>
        </div>

        <!-- Agent Breakdown -->
        {cls._render_agents_table(data)}

        <!-- CTA -->
        <div class="card" style="text-align: center;">
            <p style="margin-bottom: 16px;">View detailed performance for all agents</p>
            <a href="{{{{dashboard_url}}}}" class="button">
                Open Dashboard
            </a>
        </div>
        """

        preheader = f"Portfolio: {data.total_daily_return_pct:+.2f}% today | ${data.total_portfolio_value:,.0f} total | {len(data.agents)} agents"

        return cls.wrap_html(
            title="Team Summary | AgentFund",
            body=body,
            preheader=preheader,
        )

    @classmethod
    def _render_performers(cls, data: TeamSummaryData) -> str:
        """Render best/worst performers section."""
        if not data.best_agent and not data.worst_agent:
            return ""

        cards = []

        if data.best_agent:
            cards.append(
                f"""
                <div style="flex: 1; min-width: 200px; padding: 16px; background-color: rgba(34, 197, 94, 0.05); border-radius: 8px; border: 1px solid rgba(34, 197, 94, 0.2);">
                    <div style="font-size: 12px; color: {cls.COLORS['success']}; margin-bottom: 4px;">BEST PERFORMER</div>
                    <div style="font-weight: 600; margin-bottom: 4px;">{data.best_agent.agent_name}</div>
                    <div class="mono" style="font-size: 20px; color: {cls.COLORS['success']};">
                        {data.best_agent.daily_return_pct:+.2f}%
                    </div>
                </div>
            """
            )

        if data.worst_agent:
            cards.append(
                f"""
                <div style="flex: 1; min-width: 200px; padding: 16px; background-color: rgba(239, 68, 68, 0.05); border-radius: 8px; border: 1px solid rgba(239, 68, 68, 0.2);">
                    <div style="font-size: 12px; color: {cls.COLORS['danger']}; margin-bottom: 4px;">NEEDS ATTENTION</div>
                    <div style="font-weight: 600; margin-bottom: 4px;">{data.worst_agent.agent_name}</div>
                    <div class="mono" style="font-size: 20px; color: {cls.COLORS['danger']};">
                        {data.worst_agent.daily_return_pct:+.2f}%
                    </div>
                </div>
            """
            )

        return f"""
        <div class="card">
            <h3>Today's Highlights</h3>
            <div style="display: flex; gap: 16px; flex-wrap: wrap;">
                {''.join(cards)}
            </div>
        </div>
        """

    @classmethod
    def _render_agents_table(cls, data: TeamSummaryData) -> str:
        """Render agents comparison table."""
        if not data.agents:
            return ""

        # Sort by daily return
        sorted_agents = sorted(
            data.agents, key=lambda a: a.daily_return_pct, reverse=True
        )

        rows = []
        for agent in sorted_agents:
            status_badge = (
                '<span class="badge badge-success">Active</span>'
                if agent.status == "active"
                else f'<span class="badge badge-warning">{agent.status.title()}</span>'
            )

            rows.append(
                f"""
                <tr>
                    <td>
                        <a href="{{{{dashboard_url}}}}/agents/{agent.agent_id}"
                           style="color: {cls.COLORS['text_primary']}; text-decoration: none; font-weight: 500;">
                            {agent.agent_name}
                        </a>
                        <div style="font-size: 12px; color: {cls.COLORS['text_muted']};">
                            {agent.strategy_type.replace('_', ' ').title()}
                        </div>
                    </td>
                    <td>{status_badge}</td>
                    <td class="mono" style="text-align: right;">
                        ${agent.total_value:,.0f}
                    </td>
                    <td style="text-align: right;">
                        {cls.format_percent(agent.daily_return_pct)}
                    </td>
                    <td style="text-align: right;">
                        {cls.format_percent(agent.total_return_pct)}
                    </td>
                </tr>
            """
            )

        return f"""
        <div class="card">
            <h3>Agent Performance</h3>
            <table>
                <thead>
                    <tr>
                        <th>Agent</th>
                        <th>Status</th>
                        <th style="text-align: right;">Value</th>
                        <th style="text-align: right;">Today</th>
                        <th style="text-align: right;">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        """

    @classmethod
    def render_plain_text(cls, data: TeamSummaryData) -> str:
        """Render plain text version of the summary."""
        summary_date = data.summary_date or date.today()
        date_str = summary_date.strftime("%B %d, %Y")

        text = f"""
TEAM SUMMARY
{date_str}

PORTFOLIO OVERVIEW
------------------
Total Portfolio Value: ${data.total_portfolio_value:,.2f}
Today's P&L: ${data.total_daily_return:+,.2f} ({data.total_daily_return_pct:+.2f}%)
Total Return: {data.total_return_pct:+.2f}%
Active Agents: {len(data.agents)}
Total Positions: {data.total_positions}
"""

        if data.best_agent:
            text += f"""
BEST PERFORMER: {data.best_agent.agent_name} ({data.best_agent.daily_return_pct:+.2f}%)
"""

        if data.worst_agent:
            text += f"""
NEEDS ATTENTION: {data.worst_agent.agent_name} ({data.worst_agent.daily_return_pct:+.2f}%)
"""

        if data.summary_content:
            text += f"""
MARKET ANALYSIS
---------------
{data.summary_content}
"""

        text += """
AGENT PERFORMANCE
-----------------
"""
        sorted_agents = sorted(
            data.agents, key=lambda a: a.daily_return_pct, reverse=True
        )
        for agent in sorted_agents:
            text += f"{agent.agent_name}: ${agent.total_value:,.0f} | Today: {agent.daily_return_pct:+.2f}% | Total: {agent.total_return_pct:+.2f}%\n"

        text += """
------------------
View full details at {{dashboard_url}}

To unsubscribe, visit {{unsubscribe_url}}
"""

        return text.strip()
