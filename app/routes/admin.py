from __future__ import annotations

import logging
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import settings
from app.schema.admin import AdminEntryRequest, SyncResponse
from app.services.ingestion import sync_knowledge_base, upsert_entry_in_markdown

logger = logging.getLogger(__name__)
router = APIRouter()


async def verify_admin(request: Request) -> str:
    """Authenticate admin using constant-time comparison against static API key."""
    admin_key = request.headers.get("X-Admin-Key")
    if not admin_key:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            admin_key = auth_header[7:].strip()

    if admin_key and settings.admin_api_key and secrets.compare_digest(admin_key, settings.admin_api_key):
        return "admin"

    raise HTTPException(status_code=401, detail="Missing or invalid admin API key")


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
