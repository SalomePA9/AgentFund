"""
Database connection and utilities using Supabase.
"""

from functools import lru_cache

from supabase import Client, create_client

from config import get_settings

_supabase_client: Client | None = None


@lru_cache
def get_supabase_client() -> Client:
    """Get cached Supabase client instance."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key)


def get_db() -> Client:
    """Dependency for FastAPI routes to get database client."""
    return get_supabase_client()


class _LazySupabaseClient:
    """Lazy proxy for Supabase client to avoid module-level initialization."""

    def __getattr__(self, name):
        return getattr(get_supabase_client(), name)


# Global client instance for direct import (used by jobs)
# Uses lazy loading to avoid initialization at import time
supabase = _LazySupabaseClient()
