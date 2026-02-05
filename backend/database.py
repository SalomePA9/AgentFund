"""
Database connection and utilities using Supabase.
"""

from functools import lru_cache

from supabase import Client, create_client

from config import get_settings


@lru_cache
def get_supabase_client() -> Client:
    """Get cached Supabase client instance."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key)


def get_db() -> Client:
    """Dependency for FastAPI routes to get database client."""
    return get_supabase_client()
