"""
Report generator for AI trading agents.

Generates personalized daily reports using Claude API with
persona-specific formatting and content.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from llm.client import ClaudeClient, get_claude_client
from llm.prompts.personas import get_persona

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Context data for report generation."""

    # Agent info
    agent_id: str
    agent_name: str
    persona: str
    strategy_type: str

    # Performance data
    total_value: float
    allocated_capital: float
    daily_return_pct: float
    total_return_pct: float
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    win_rate: float | None = None

    # Positions
    positions: list[dict[str, Any]] | None = None
    positions_count: int = 0

    # Recent activity
    activities: list[dict[str, Any]] | None = None

    # Time info
    report_date: date | None = None
    days_active: int = 0

    # Macro risk overlay context
    macro_regime: str | None = None  # e.g. "normal", "elevated_risk", "high_risk"
    macro_scale_factor: float | None = None  # 0.25 to 1.25
    macro_composite_score: float | None = None  # -100 to +100
    macro_warnings: list[str] | None = None

    # Individual macro signal readings
    credit_spread_signal: float | None = None
    yield_curve_signal: float | None = None
    vol_regime_signal: float | None = None
    vix_level: float | None = None
    vix_regime: str | None = None  # "calm", "elevated", "crisis"
    seasonality_signal: float | None = None
    insider_breadth_signal: float | None = None

    # Per-position uncorrelated signals (symbol → score)
    insider_signals: dict[str, float] | None = None
    short_interest_signals: dict[str, float] | None = None


@dataclass
class GeneratedReport:
    """A generated daily report."""

    content: str
    agent_id: str
    report_date: date
    performance_snapshot: dict[str, Any]
    positions_snapshot: list[dict[str, Any]]
    actions_taken: list[dict[str, Any]]
    tokens_used: int
    generated_at: datetime


class ReportGenerator:
    """
    Generates personalized daily reports for trading agents.

    Uses Claude API with persona-specific prompts to create
    engaging, informative reports tailored to each agent's
    communication style.
    """

    # Use Sonnet for reports (better quality than Haiku)
    REPORT_MODEL = "claude-3-5-sonnet-20241022"

    def __init__(self, client: ClaudeClient | None = None):
        """
        Initialize report generator.

        Args:
            client: Claude client instance (uses singleton if not provided)
        """
        self.client = client or get_claude_client()

    def _build_performance_summary(self, ctx: AgentContext) -> str:
        """Build performance summary text for the prompt."""
        lines = [
            f"Portfolio Value: ${ctx.total_value:,.2f}",
            f"Allocated Capital: ${ctx.allocated_capital:,.2f}",
            f"Daily Return: {ctx.daily_return_pct:+.2f}%",
            f"Total Return: {ctx.total_return_pct:+.2f}%",
        ]

        if ctx.sharpe_ratio is not None:
            lines.append(f"Sharpe Ratio: {ctx.sharpe_ratio:.2f}")
        if ctx.max_drawdown is not None:
            lines.append(f"Max Drawdown: {ctx.max_drawdown:.2f}%")
        if ctx.win_rate is not None:
            lines.append(f"Win Rate: {ctx.win_rate:.1f}%")

        lines.append(f"Active Positions: {ctx.positions_count}")
        lines.append(f"Days Active: {ctx.days_active}")

        return "\n".join(lines)

    def _build_positions_summary(self, ctx: AgentContext) -> str:
        """Build positions summary text for the prompt."""
        if not ctx.positions:
            return "No open positions."

        lines = ["Current Positions:"]
        for pos in ctx.positions[:10]:  # Limit to 10 positions
            ticker = pos.get("ticker", "???")
            shares = pos.get("shares", 0)
            entry = pos.get("entry_price") or 0
            current = pos.get("current_price") or entry
            pnl_pct = ((current / entry) - 1) * 100 if entry > 0 else 0

            lines.append(
                f"- {ticker}: {shares} shares @ ${entry:.2f} "
                f"(now ${current:.2f}, {pnl_pct:+.1f}%)"
            )

        if len(ctx.positions) > 10:
            lines.append(f"  ... and {len(ctx.positions) - 10} more positions")

        return "\n".join(lines)

    def _build_macro_summary(self, ctx: AgentContext) -> str:
        """Build macro risk overlay and uncorrelated signals summary for the prompt."""
        lines: list[str] = []

        # Macro overlay headline
        if ctx.macro_regime:
            regime_display = ctx.macro_regime.replace("_", " ").title()
            lines.append(f"Macro Regime: {regime_display}")
        if ctx.macro_scale_factor is not None:
            pct_adj = (ctx.macro_scale_factor - 1.0) * 100
            direction = "reduced" if pct_adj < 0 else "increased"
            lines.append(
                f"Position Size Adjustment: {direction} by {abs(pct_adj):.1f}% "
                f"(scale factor {ctx.macro_scale_factor:.2f})"
            )
        if ctx.macro_composite_score is not None:
            lines.append(
                f"Macro Composite Score: {ctx.macro_composite_score:+.1f} / 100"
            )

        # Individual signals
        signal_lines: list[str] = []
        if ctx.credit_spread_signal is not None:
            label = (
                "bullish"
                if ctx.credit_spread_signal > 10
                else ("bearish" if ctx.credit_spread_signal < -10 else "neutral")
            )
            signal_lines.append(
                f"  Credit Spreads: {ctx.credit_spread_signal:+.0f} ({label})"
            )
        if ctx.yield_curve_signal is not None:
            label = (
                "bullish"
                if ctx.yield_curve_signal > 10
                else ("bearish" if ctx.yield_curve_signal < -10 else "neutral")
            )
            signal_lines.append(
                f"  Yield Curve (10Y-2Y): {ctx.yield_curve_signal:+.0f} ({label})"
            )
        if ctx.vol_regime_signal is not None:
            vix_str = f", VIX at {ctx.vix_level:.1f}" if ctx.vix_level else ""
            regime_str = f" [{ctx.vix_regime}]" if ctx.vix_regime else ""
            signal_lines.append(
                f"  Volatility Regime: {ctx.vol_regime_signal:+.0f}{regime_str}{vix_str}"
            )
        if ctx.seasonality_signal is not None:
            signal_lines.append(f"  Seasonality: {ctx.seasonality_signal:+.0f}")
        if ctx.insider_breadth_signal is not None:
            signal_lines.append(f"  Insider Breadth: {ctx.insider_breadth_signal:+.0f}")

        if signal_lines:
            lines.append("Signal Readings:")
            lines.extend(signal_lines)

        # Macro warnings
        if ctx.macro_warnings:
            lines.append("Warnings:")
            for w in ctx.macro_warnings:
                lines.append(f"  - {w}")

        # Per-position uncorrelated signals
        position_signals: list[str] = []
        if ctx.insider_signals:
            for sym, score in sorted(
                ctx.insider_signals.items(), key=lambda x: abs(x[1]), reverse=True
            )[:5]:
                direction = "buying" if score > 0 else "selling"
                position_signals.append(
                    f"  {sym}: insider {direction} (score {score:+.0f})"
                )
        if ctx.short_interest_signals:
            for sym, score in sorted(
                ctx.short_interest_signals.items(),
                key=lambda x: abs(x[1]),
                reverse=True,
            )[:5]:
                if abs(score) > 20:
                    level = (
                        "extreme"
                        if abs(score) > 70
                        else ("high" if abs(score) > 40 else "elevated")
                    )
                    position_signals.append(
                        f"  {sym}: {level} short interest (score {score:+.0f})"
                    )

        if position_signals:
            lines.append("Notable Stock-Level Signals:")
            lines.extend(position_signals)

        if not lines:
            return "Macro overlay data not available."

        return "\n".join(lines)

    def _build_activity_summary(self, ctx: AgentContext) -> str:
        """Build recent activity summary for the prompt."""
        if not ctx.activities:
            return "No recent activity."

        lines = ["Recent Activity:"]
        for act in ctx.activities[:5]:  # Limit to 5 activities
            activity_type = act.get("activity_type", "unknown")
            ticker = act.get("ticker", "")
            details = act.get("details", {})

            if activity_type == "buy":
                shares = details.get("shares", 0)
                price = details.get("price", 0)
                lines.append(f"- BOUGHT {shares} {ticker} @ ${price:.2f}")
            elif activity_type == "sell":
                shares = details.get("shares", 0)
                price = details.get("price", 0)
                pnl = details.get("realized_pnl", 0)
                lines.append(
                    f"- SOLD {shares} {ticker} @ ${price:.2f} (P&L: ${pnl:+,.2f})"
                )
            elif activity_type == "stop_triggered":
                lines.append(f"- STOP triggered for {ticker}")
            elif activity_type == "target_hit":
                lines.append(f"- TARGET hit for {ticker}")
            else:
                lines.append(f"- {activity_type}: {ticker}")

        return "\n".join(lines)

    def generate_daily_report(
        self,
        context: AgentContext,
        include_positions: bool = True,
        include_activity: bool = True,
    ) -> GeneratedReport:
        """
        Generate a daily report for an agent.

        Args:
            context: Agent context with performance data
            include_positions: Whether to include position details
            include_activity: Whether to include recent activity

        Returns:
            GeneratedReport with content and metadata
        """
        if not self.client.is_configured:
            # Return placeholder if LLM not configured
            return self._generate_placeholder_report(context)

        persona = get_persona(context.persona)
        report_date = context.report_date or date.today()

        # Build the system prompt
        system_prompt = f"""{persona.system_prompt}

You are {context.agent_name}, a {context.strategy_type.replace('_', ' ')} trading agent.

{persona.report_style}

Generate a daily report for {report_date.strftime('%B %d, %Y')}.
The report should be engaging, informative, and match your persona's style.
Keep it concise but insightful - aim for 200-400 words.

IMPORTANT: You have access to macro risk overlay data and uncorrelated signal readings.
Integrate these into your analysis naturally — explain how market conditions (credit spreads,
VIX, yield curve) are affecting your positioning, and mention any notable stock-level signals
(insider buying/selling, short interest) for your held positions. If the macro overlay has
reduced or increased your position sizes, explain why in terms the reader can understand."""

        # Build the user message with context
        performance = self._build_performance_summary(context)
        positions = (
            self._build_positions_summary(context)
            if include_positions
            else "Position details not included."
        )
        activity = (
            self._build_activity_summary(context)
            if include_activity
            else "Activity details not included."
        )
        macro = self._build_macro_summary(context)

        user_message = f"""Generate my daily report based on today's data:

PERFORMANCE:
{performance}

{positions}

{activity}

MACRO RISK OVERLAY & UNCORRELATED SIGNALS:
{macro}

Write the report in first person as {context.agent_name}. Weave the macro overlay and
uncorrelated signal context into the narrative — don't just list the numbers."""

        # Generate report
        try:
            content, usage = self.client.send_message(
                messages=[{"role": "user", "content": user_message}],
                system=system_prompt,
                model=self.REPORT_MODEL,
                max_tokens=1536,
                temperature=0.7,
                use_cache=False,  # Reports should be fresh
            )

            logger.info(
                f"Generated report for {context.agent_name}: "
                f"{usage.total_tokens} tokens"
            )

            return GeneratedReport(
                content=content,
                agent_id=context.agent_id,
                report_date=report_date,
                performance_snapshot={
                    "total_value": context.total_value,
                    "allocated_capital": context.allocated_capital,
                    "daily_return_pct": context.daily_return_pct,
                    "total_return_pct": context.total_return_pct,
                    "sharpe_ratio": context.sharpe_ratio,
                    "max_drawdown": context.max_drawdown,
                    "win_rate": context.win_rate,
                    "positions_count": context.positions_count,
                    "macro_regime": context.macro_regime,
                    "macro_scale_factor": context.macro_scale_factor,
                    "macro_composite_score": context.macro_composite_score,
                    "macro_warnings": context.macro_warnings,
                    "credit_spread_signal": context.credit_spread_signal,
                    "yield_curve_signal": context.yield_curve_signal,
                    "vol_regime_signal": context.vol_regime_signal,
                    "vix_level": context.vix_level,
                    "vix_regime": context.vix_regime,
                    "seasonality_signal": context.seasonality_signal,
                    "insider_breadth_signal": context.insider_breadth_signal,
                },
                positions_snapshot=context.positions or [],
                actions_taken=context.activities or [],
                tokens_used=usage.total_tokens,
                generated_at=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"Failed to generate report: {e}")
            return self._generate_placeholder_report(context)

    def _generate_placeholder_report(self, context: AgentContext) -> GeneratedReport:
        """Generate a placeholder report when LLM is not available."""
        report_date = context.report_date or date.today()

        # Simple template-based report
        daily_emoji = "📈" if context.daily_return_pct >= 0 else "📉"
        total_emoji = "✅" if context.total_return_pct >= 0 else "⚠️"

        content = f"""Daily Report - {report_date.strftime('%B %d, %Y')}

{daily_emoji} Today's Performance: {context.daily_return_pct:+.2f}%
{total_emoji} Total Return: {context.total_return_pct:+.2f}%

Portfolio Value: ${context.total_value:,.2f}
Active Positions: {context.positions_count}

Strategy: {context.strategy_type.replace('_', ' ').title()}

---
Note: Full AI-generated reports will be available once the Anthropic API key is configured."""

        return GeneratedReport(
            content=content,
            agent_id=context.agent_id,
            report_date=report_date,
            performance_snapshot={
                "total_value": context.total_value,
                "daily_return_pct": context.daily_return_pct,
                "total_return_pct": context.total_return_pct,
                "positions_count": context.positions_count,
            },
            positions_snapshot=context.positions or [],
            actions_taken=context.activities or [],
            tokens_used=0,
            generated_at=datetime.utcnow(),
        )

    def generate_team_summary(
        self,
        agents: list[AgentContext],
        summary_date: date | None = None,
    ) -> str:
        """
        Generate a team summary across all agents.

        Args:
            agents: List of agent contexts
            summary_date: Date for the summary

        Returns:
            Team summary text
        """
        if not self.client.is_configured or not agents:
            return self._generate_placeholder_team_summary(agents, summary_date)

        summary_date = summary_date or date.today()

        # Aggregate metrics
        total_value = sum(a.total_value for a in agents)
        total_allocated = sum(a.allocated_capital for a in agents)
        avg_return = (
            sum(a.daily_return_pct for a in agents) / len(agents) if agents else 0
        )

        # Build agent summaries
        agent_lines = []
        for agent in sorted(agents, key=lambda a: a.daily_return_pct, reverse=True):
            emoji = "🟢" if agent.daily_return_pct >= 0 else "🔴"
            agent_lines.append(
                f"- {agent.agent_name} ({agent.strategy_type}): "
                f"{emoji} {agent.daily_return_pct:+.2f}%"
            )

        system_prompt = """You are a portfolio manager summarizing the day's
performance across all trading agents. Be concise but insightful.
Highlight top performers and any concerns. Keep it under 200 words."""

        user_message = f"""Generate a team summary for {summary_date.strftime('%B %d, %Y')}:

TEAM OVERVIEW:
Total Portfolio Value: ${total_value:,.2f}
Total Allocated: ${total_allocated:,.2f}
Average Daily Return: {avg_return:+.2f}%
Number of Agents: {len(agents)}

INDIVIDUAL PERFORMANCE:
{chr(10).join(agent_lines)}

Write a brief executive summary of today's team performance."""

        try:
            content, _ = self.client.send_message(
                messages=[{"role": "user", "content": user_message}],
                system=system_prompt,
                model=self.REPORT_MODEL,
                max_tokens=512,
                temperature=0.7,
            )
            return content

        except Exception as e:
            logger.error(f"Failed to generate team summary: {e}")
            return self._generate_placeholder_team_summary(agents, summary_date)

    def _generate_placeholder_team_summary(
        self,
        agents: list[AgentContext],
        summary_date: date | None = None,
    ) -> str:
        """Generate placeholder team summary."""
        summary_date = summary_date or date.today()

        if not agents:
            return f"Team Summary - {summary_date}\n\nNo active agents."

        total_value = sum(a.total_value for a in agents)
        avg_return = sum(a.daily_return_pct for a in agents) / len(agents)

        return f"""Team Summary - {summary_date.strftime('%B %d, %Y')}

Total Portfolio Value: ${total_value:,.2f}
Average Daily Return: {avg_return:+.2f}%
Active Agents: {len(agents)}

---
Note: AI-generated summaries available with Anthropic API key."""


# Singleton instance
_generator_instance: ReportGenerator | None = None


def get_report_generator() -> ReportGenerator:
    """Get or create the singleton ReportGenerator instance."""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = ReportGenerator()
    return _generator_instance
