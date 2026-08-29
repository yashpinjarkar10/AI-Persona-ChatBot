from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import settings
from app.schema.admin import AdminEntryRequest, SyncResponse
from app.services.ingestion import sync_knowledge_base, upsert_entry_in_markdown
from app.services.supabase_client import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter()


async def verify_admin(request: Request) -> str:
    """Authenticate request using Supabase Auth JWT token or static admin key header."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        try:
            sb = get_supabase()
            user_resp = sb.auth.get_user(token)
            if user_resp and user_resp.user and user_resp.user.email:
                if settings.admin_email and user_resp.user.email.lower() == settings.admin_email.lower():
                    return user_resp.user.email
                raise HTTPException(status_code=403, detail="User is not authorized as admin")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("Supabase JWT verification failed: %s", e)
            raise HTTPException(status_code=401, detail="Invalid Supabase authentication token")

    admin_key = request.headers.get("X-Admin-Key")
    if admin_key and settings.admin_api_key and admin_key == settings.admin_api_key:
        return "admin_key_user"

    raise HTTPException(status_code=401, detail="Missing or invalid authentication credentials")


@router.post("/sync", response_model=SyncResponse, dependencies=[Depends(verify_admin)])
async def trigger_sync():
    """Trigger manual synchronization of personal_facts.md into Supabase documentation table."""
    try:
        stats = sync_knowledge_base()
        return SyncResponse(message="Knowledge base synchronized successfully.", result=stats)
    except Exception as e:
        logger.exception("Knowledge base sync failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/entry", response_model=SyncResponse, dependencies=[Depends(verify_admin)])
async def add_or_update_entry(entry: AdminEntryRequest):
    """Add or update an entry in personal_facts.md and synchronize it with Supabase."""
    try:
        upsert_entry_in_markdown(entry.model_dump(), settings.facts_file_path)
        stats = sync_knowledge_base()
        return SyncResponse(message=f"Entry '{entry.entity_name}::{entry.title}' saved and synchronized.", result=stats)
    except Exception as e:
        logger.exception("Failed to add/update entry")
        raise HTTPException(status_code=500, detail=str(e))
