"""Admin routes — protected by Supabase JWT authentication.

Usage from anywhere:
  1. Sign in via Supabase Auth (email/password, magic link, etc.)
  2. Get your access_token (JWT) from the Supabase session
  3. Send requests with:  Authorization: Bearer <access_token>

Only the email configured in ADMIN_EMAIL is allowed.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from supabase import create_client

from app.config import settings
from app.scripts.build_vectorstore import sync_knowledge_base

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Supabase JWT verification dependency
# ---------------------------------------------------------------------------


async def verify_admin(request: Request) -> str:
    """Verify the static API key from the X-Admin-Key header.

    Returns the key on success.
    """
    admin_key = request.headers.get("X-Admin-Key")
    if not admin_key:
        raise HTTPException(status_code=401, detail="Missing X-Admin-Key header")

    if not settings.admin_api_key:
        raise HTTPException(status_code=500, detail="ADMIN_API_KEY not configured on the server")

    if admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid admin API key")

    logger.info("Admin authenticated via static API key")
    return admin_key



# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------


@router.post("/ingest", dependencies=[Depends(verify_admin)])
async def ingest_knowledge():
    """Re-sync the knowledge base vector store."""
    try:
        result = sync_knowledge_base()
        logger.info("Knowledge base sync completed: %s", result)
        return {"message": "Knowledge base synchronized successfully", "result": result}
    except Exception as e:
        logger.exception("Knowledge base sync failed")
        raise HTTPException(status_code=500, detail=str(e))
