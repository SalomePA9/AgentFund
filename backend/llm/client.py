"""
Claude API client wrapper for AgentFund.

Provides a robust interface to the Anthropic Claude API with:
- Automatic retry with exponential backoff
- Response caching for cost optimization
- Token usage tracking
- Error handling
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any

from anthropic import Anthropic, APIError, RateLimitError

from config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Track token usage for cost monitoring."""

    input_tokens: int = 0
    output_tokens: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost(self) -> float:
        """Estimate cost based on Claude 3 Haiku pricing."""
        # Haiku: $0.25/1M input, $1.25/1M output
        input_cost = (self.input_tokens / 1_000_000) * 0.25
        output_cost = (self.output_tokens / 1_000_000) * 1.25
        return input_cost + output_cost


@dataclass
class CachedResponse:
    """Cached LLM response with expiration."""

    content: str
    usage: TokenUsage
    created_at: datetime = field(default_factory=datetime.utcnow)
    ttl_minutes: int = 30

    @property
    def is_expired(self) -> bool:
        expiry = self.created_at + timedelta(minutes=self.ttl_minutes)
        return datetime.utcnow() > expiry


class ClaudeClient:
    """
    Wrapper around Anthropic's Claude API.

    Features:
    - Automatic retry with exponential backoff
    - Response caching (optional)
    - Token usage tracking
    - Support for different Claude models
    """

    # Default model - using Haiku for cost efficiency
    DEFAULT_MODEL = "claude-3-haiku-20240307"

    # Model options for different use cases
    MODELS = {
        "haiku": "claude-3-haiku-20240307",  # Fast, cheap - good for chat
        "sonnet": "claude-3-5-sonnet-20241022",  # Balanced - good for reports
        "opus": "claude-3-opus-20240229",  # Most capable - complex analysis
    }

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str | None = None,
        enable_cache: bool = True,
        cache_ttl_minutes: int = 30,
        max_retries: int = 3,
    ):
        """
        Initialize Claude client.

        Args:
            api_key: Anthropic API key (defaults to settings)
            default_model: Default model to use
            enable_cache: Whether to cache responses
            cache_ttl_minutes: Cache TTL in minutes
            max_retries: Max retry attempts for failed requests
        """
        settings = get_settings()
        self.api_key = api_key or settings.anthropic_api_key

        if not self.api_key:
            logger.warning("No Anthropic API key configured - LLM features disabled")
            self._client = None
        else:
            self._client = Anthropic(api_key=self.api_key)

        self.default_model = default_model or self.DEFAULT_MODEL
        self.enable_cache = enable_cache
        self.cache_ttl_minutes = cache_ttl_minutes
        self.max_retries = max_retries

        # Response cache
        self._cache: dict[str, CachedResponse] = {}

        # Usage tracking
        self._usage_history: list[TokenUsage] = []

    @property
    def is_configured(self) -> bool:
        """Check if the client is properly configured."""
        return self._client is not None

    def _get_cache_key(self, messages: list[dict], system: str, model: str) -> str:
        """Generate cache key from request parameters."""
        content = f"{model}:{system}:{str(messages)}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_cached_response(self, cache_key: str) -> CachedResponse | None:
        """Get cached response if valid."""
        if not self.enable_cache:
            return None

        cached = self._cache.get(cache_key)
        if cached and not cached.is_expired:
            logger.debug(f"Cache hit for key {cache_key[:8]}...")
            return cached

        # Clean up expired entry
        if cached:
            del self._cache[cache_key]

        return None

    def _cache_response(
        self, cache_key: str, content: str, usage: TokenUsage
    ) -> None:
        """Cache a response."""
        if not self.enable_cache:
            return

        self._cache[cache_key] = CachedResponse(
            content=content,
            usage=usage,
            ttl_minutes=self.cache_ttl_minutes,
        )

        # Limit cache size (simple LRU-like behavior)
        if len(self._cache) > 1000:
            # Remove oldest entries
            sorted_items = sorted(
                self._cache.items(),
                key=lambda x: x[1].created_at,
            )
            for key, _ in sorted_items[:100]:
                del self._cache[key]

    def send_message(
        self,
        messages: list[dict[str, str]],
        system: str = "",
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        use_cache: bool = True,
    ) -> tuple[str, TokenUsage]:
        """
        Send a message to Claude and get a response.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system: System prompt
            model: Model to use (defaults to instance default)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0-1)
            use_cache: Whether to use caching for this request

        Returns:
            Tuple of (response_content, token_usage)

        Raises:
            RuntimeError: If client is not configured
            APIError: If API request fails after retries
        """
        if not self.is_configured:
            raise RuntimeError(
                "Claude client not configured. Set ANTHROPIC_API_KEY environment variable."
            )

        model = model or self.default_model

        # Check cache
        if use_cache:
            cache_key = self._get_cache_key(messages, system, model)
            cached = self._get_cached_response(cache_key)
            if cached:
                return cached.content, cached.usage

        # Make API request with retry
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self._client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system if system else None,
                    messages=messages,
                )

                # Extract content
                content = response.content[0].text

                # Track usage
                usage = TokenUsage(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                )
                self._usage_history.append(usage)

                # Cache response
                if use_cache:
                    self._cache_response(cache_key, content, usage)

                logger.debug(
                    f"Claude response: {usage.total_tokens} tokens, "
                    f"${usage.estimated_cost:.4f} estimated cost"
                )

                return content, usage

            except RateLimitError as e:
                last_error = e
                wait_time = 2 ** (attempt + 1)  # Exponential backoff
                logger.warning(
                    f"Rate limited, waiting {wait_time}s (attempt {attempt + 1})"
                )
                time.sleep(wait_time)

            except APIError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        f"API error: {e}, retrying in {wait_time}s "
                        f"(attempt {attempt + 1})"
                    )
                    time.sleep(wait_time)
                else:
                    raise

        raise last_error or RuntimeError("Unknown error in Claude API call")

    def get_usage_summary(
        self, since: datetime | None = None
    ) -> dict[str, Any]:
        """
        Get usage summary for cost tracking.

        Args:
            since: Only include usage since this time

        Returns:
            Dictionary with usage statistics
        """
        relevant_usage = self._usage_history
        if since:
            relevant_usage = [u for u in self._usage_history if u.timestamp >= since]

        if not relevant_usage:
            return {
                "total_requests": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "estimated_cost": 0.0,
            }

        total_input = sum(u.input_tokens for u in relevant_usage)
        total_output = sum(u.output_tokens for u in relevant_usage)
        total_cost = sum(u.estimated_cost for u in relevant_usage)

        return {
            "total_requests": len(relevant_usage),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "estimated_cost": round(total_cost, 4),
        }

    def clear_cache(self) -> int:
        """Clear the response cache. Returns number of entries cleared."""
        count = len(self._cache)
        self._cache.clear()
        return count


# Singleton instance for shared use
_client_instance: ClaudeClient | None = None


def get_claude_client() -> ClaudeClient:
    """Get or create the singleton Claude client instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = ClaudeClient()
    return _client_instance
