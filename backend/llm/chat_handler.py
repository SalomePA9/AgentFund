"""
Chat handler for AI trading agent conversations.

Manages chat interactions with trading agents, providing context-aware
responses in the agent's persona voice.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from llm.client import ClaudeClient, TokenUsage, get_claude_client
from llm.prompts.personas import get_persona

logger = logging.getLogger(__name__)


@dataclass
class ChatContext:
    """Context for agent chat conversations."""

    # Agent info
    agent_id: str
    agent_name: str
    persona: str
    strategy_type: str

    # Current state
    status: str  # active, paused, stopped
    total_value: float
    allocated_capital: float
    daily_return_pct: float
    total_return_pct: float

    # Positions summary
    positions_count: int = 0
    top_positions: list[dict[str, Any]] = field(default_factory=list)

    # Recent activity
    recent_activities: list[dict[str, Any]] = field(default_factory=list)

    # Performance metrics
    sharpe_ratio: float | None = None
    win_rate: float | None = None
    max_drawdown: float | None = None


@dataclass
class ChatMessage:
    """A chat message."""

    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ChatResponse:
    """Response from the chat handler."""

    content: str
    usage: TokenUsage
    context_used: dict[str, Any]


class AgentChatHandler:
    """
    Handles chat conversations with trading agents.

    Provides context-aware responses using the agent's persona,
    current positions, and performance data.
    """

    # Use Haiku for chat (fast, cheap)
    CHAT_MODEL = "claude-3-haiku-20240307"

    # Maximum conversation history to include
    MAX_HISTORY_MESSAGES = 10

    def __init__(self, client: ClaudeClient | None = None):
        """
        Initialize chat handler.

        Args:
            client: Claude client instance (uses singleton if not provided)
        """
        self.client = client or get_claude_client()

    def _build_context_summary(self, ctx: ChatContext) -> str:
        """Build context summary for the system prompt."""
        lines = [
            f"Current Status: {ctx.status.upper()}",
            f"Portfolio Value: ${ctx.total_value:,.2f}",
            f"Allocated Capital: ${ctx.allocated_capital:,.2f}",
            f"Daily Return: {ctx.daily_return_pct:+.2f}%",
            f"Total Return: {ctx.total_return_pct:+.2f}%",
            f"Open Positions: {ctx.positions_count}",
        ]

        if ctx.sharpe_ratio is not None:
            lines.append(f"Sharpe Ratio: {ctx.sharpe_ratio:.2f}")
        if ctx.win_rate is not None:
            lines.append(f"Win Rate: {ctx.win_rate:.1f}%")
        if ctx.max_drawdown is not None:
            lines.append(f"Max Drawdown: {ctx.max_drawdown:.2f}%")

        return "\n".join(lines)

    def _build_positions_context(self, ctx: ChatContext) -> str:
        """Build positions context for the system prompt."""
        if not ctx.top_positions:
            return "No open positions currently."

        lines = ["Top Positions:"]
        for pos in ctx.top_positions[:5]:
            ticker = pos.get("ticker", "???")
            shares = pos.get("shares", 0)
            pnl_pct = pos.get("unrealized_pnl_pct", 0)
            lines.append(f"- {ticker}: {shares} shares ({pnl_pct:+.1f}%)")

        return "\n".join(lines)

    def _build_activity_context(self, ctx: ChatContext) -> str:
        """Build recent activity context for the system prompt."""
        if not ctx.recent_activities:
            return "No recent trading activity."

        lines = ["Recent Activity:"]
        for act in ctx.recent_activities[:3]:
            activity_type = act.get("activity_type", "")
            ticker = act.get("ticker", "")
            if activity_type and ticker:
                lines.append(f"- {activity_type.upper()}: {ticker}")

        return "\n".join(lines)

    def _build_system_prompt(self, ctx: ChatContext) -> str:
        """Build the full system prompt for the chat."""
        persona = get_persona(ctx.persona)

        context_summary = self._build_context_summary(ctx)
        positions_context = self._build_positions_context(ctx)
        activity_context = self._build_activity_context(ctx)

        return f"""{persona.system_prompt}

You are {ctx.agent_name}, a {ctx.strategy_type.replace('_', ' ')} trading agent.

{persona.chat_style}

CURRENT STATE:
{context_summary}

{positions_context}

{activity_context}

Important guidelines:
- Stay in character as {ctx.agent_name}
- Reference your actual positions and performance when relevant
- Be helpful but maintain your persona's communication style
- If asked about specific trades, reference your actual data
- Don't make up information - if you don't know, say so
- Keep responses concise but informative (aim for 50-150 words)"""

    def _format_history(
        self, history: list[ChatMessage]
    ) -> list[dict[str, str]]:
        """Format chat history for the API."""
        # Take most recent messages
        recent = history[-self.MAX_HISTORY_MESSAGES:]

        return [
            {"role": msg.role, "content": msg.content}
            for msg in recent
        ]

    def generate_response(
        self,
        context: ChatContext,
        user_message: str,
        history: list[ChatMessage] | None = None,
    ) -> ChatResponse:
        """
        Generate a response to a user message.

        Args:
            context: Agent context with current state
            user_message: The user's message
            history: Previous conversation history

        Returns:
            ChatResponse with content and metadata
        """
        if not self.client.is_configured:
            return self._generate_placeholder_response(context, user_message)

        system_prompt = self._build_system_prompt(context)

        # Build messages list
        messages = []
        if history:
            messages.extend(self._format_history(history))
        messages.append({"role": "user", "content": user_message})

        try:
            content, usage = self.client.send_message(
                messages=messages,
                system=system_prompt,
                model=self.CHAT_MODEL,
                max_tokens=512,
                temperature=0.8,  # Slightly higher for more natural chat
                use_cache=True,  # Cache can help with repeated questions
            )

            logger.debug(
                f"Chat response for {context.agent_name}: "
                f"{usage.total_tokens} tokens"
            )

            return ChatResponse(
                content=content,
                usage=usage,
                context_used={
                    "agent_name": context.agent_name,
                    "persona": context.persona,
                    "strategy_type": context.strategy_type,
                    "total_value": context.total_value,
                    "daily_return_pct": context.daily_return_pct,
                    "positions_count": context.positions_count,
                },
            )

        except Exception as e:
            logger.error(f"Failed to generate chat response: {e}")
            return self._generate_placeholder_response(context, user_message)

    def _generate_placeholder_response(
        self,
        context: ChatContext,
        user_message: str,
    ) -> ChatResponse:
        """Generate a placeholder response when LLM is not available."""
        persona = get_persona(context.persona)

        # Simple keyword-based responses
        message_lower = user_message.lower()

        if any(word in message_lower for word in ["performance", "return", "doing"]):
            content = (
                f"My current total return is {context.total_return_pct:+.2f}%, "
                f"with today's return at {context.daily_return_pct:+.2f}%. "
                f"Portfolio value: ${context.total_value:,.2f}."
            )
        elif any(word in message_lower for word in ["position", "holding", "stock"]):
            content = (
                f"I currently have {context.positions_count} open positions. "
                f"My strategy is {context.strategy_type.replace('_', ' ')}."
            )
        elif any(word in message_lower for word in ["strategy", "approach", "method"]):
            content = (
                f"I follow a {context.strategy_type.replace('_', ' ')} strategy. "
                f"This means I focus on stocks that match specific criteria "
                f"for this approach."
            )
        elif any(word in message_lower for word in ["hello", "hi", "hey"]):
            content = (
                f"Hello! I'm {context.agent_name}, your "
                f"{context.strategy_type.replace('_', ' ')} trading agent. "
                f"How can I help you today?"
            )
        else:
            content = (
                f"I'm {context.agent_name}, running a "
                f"{context.strategy_type.replace('_', ' ')} strategy. "
                f"Currently managing ${context.total_value:,.2f} with "
                f"{context.positions_count} positions. "
                f"Full AI chat available with Anthropic API key configured."
            )

        return ChatResponse(
            content=content,
            usage=TokenUsage(),
            context_used={
                "agent_name": context.agent_name,
                "persona": context.persona,
                "placeholder": True,
            },
        )

    def generate_greeting(self, context: ChatContext) -> ChatResponse:
        """
        Generate an initial greeting from the agent.

        Args:
            context: Agent context

        Returns:
            ChatResponse with greeting
        """
        if not self.client.is_configured:
            return self._generate_placeholder_response(context, "hello")

        system_prompt = self._build_system_prompt(context)

        greeting_prompt = (
            f"Generate a brief, friendly greeting as {context.agent_name}. "
            f"Introduce yourself and mention your current status briefly. "
            f"Keep it under 50 words."
        )

        try:
            content, usage = self.client.send_message(
                messages=[{"role": "user", "content": greeting_prompt}],
                system=system_prompt,
                model=self.CHAT_MODEL,
                max_tokens=128,
                temperature=0.8,
            )

            return ChatResponse(
                content=content,
                usage=usage,
                context_used={"greeting": True},
            )

        except Exception as e:
            logger.error(f"Failed to generate greeting: {e}")
            return self._generate_placeholder_response(context, "hello")


# Singleton instance
_handler_instance: AgentChatHandler | None = None


def get_chat_handler() -> AgentChatHandler:
    """Get or create the singleton AgentChatHandler instance."""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = AgentChatHandler()
    return _handler_instance
