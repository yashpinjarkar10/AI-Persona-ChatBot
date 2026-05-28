"""Singleton Supabase client for server-side operations."""

from __future__ import annotations

from supabase import create_client, Client

from app.config import settings

_client: Client | None = None


def get_supabase() -> Client:
    """Return a cached Supabase client (service-role key for server writes)."""
    global _client
    if _client is not None:
        return _client

    url = settings.supabase_url
    key = settings.supabase_service_key or settings.supabase_key
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY (or SUPABASE_KEY) must be set in environment"
        )

    _client = create_client(url, key)
    return _client
