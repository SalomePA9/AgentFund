"""
Application configuration using Pydantic Settings.
Loads environment variables from .env file.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "AgentFund API"
    debug: bool = False
    api_version: str = "v1"

    # Database (Supabase)
    supabase_url: str
    supabase_anon_key: str  # Public key for client operations
    supabase_service_key: str | None = None  # Service role key for backend
    database_url: str | None = None

    @property
    def supabase_key(self) -> str:
        """Return service key if available, otherwise anon key."""
        return self.supabase_service_key or self.supabase_anon_key

    # Authentication
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Encryption (for storing user API keys)
    encryption_key: str

    # Alpaca (default/fallback for testing)
    alpaca_api_key: str | None = None
    alpaca_api_secret: str | None = None
    alpaca_paper_mode: bool = True

    # Uppercase aliases for convenience
    @property
    def ALPACA_API_KEY(self) -> str | None:
        return self.alpaca_api_key

    @property
    def ALPACA_API_SECRET(self) -> str | None:
        return self.alpaca_api_secret

    # Claude API (optional for Phase 1, required for Phase 2 reports/chat)
    anthropic_api_key: str | None = None

    # Reddit (for sentiment)
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None

    # Email (Resend)
    resend_api_key: str | None = None

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance for direct import
settings = get_settings()
