from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from langchain_mistralai import MistralAIEmbeddings

from app.config import settings
from app.services.supabase_client import get_supabase

ALLOWED_CATEGORIES = {
    "personal",
    "summary",
    "education",
    "experience",
    "project",
    "skill",
    "certification",
    "achievement",
    "language",
    "hobby",
    "goal",
}


@dataclass
class ParsedEntry:
    entity_name: str
    title: str
    category: str
    content: str
    content_hash: str
    subcategory: str | None = None
    tags: list[str] | None = None
    date_range: str | None = None
    status: str | None = None
    priority: int | None = None
    links: dict[str, str] | None = None
    metrics: list[str] | None = None
    active: bool = True
    source: str = "manual_entry"
    created_date: str | None = None
    last_updated: str | None = None


def parse_markdown_file(file_path: Path | str) -> list[ParsedEntry]:
    """Parse knowledge markdown file into a validated list of ParsedEntry objects."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Knowledge file not found at: {path}")

    text = path.read_text(encoding="utf-8")
    blocks = re.findall(r"<!-- ENTRY START -->(.*?)<!-- ENTRY END -->", text, re.DOTALL)

    entries: list[ParsedEntry] = []
    seen_keys: set[tuple[str, str]] = set()

    for index, block in enumerate(blocks, start=1):
        block = block.strip()
        if not block:
            continue

        parts = block.split("---")
        if len(parts) < 3:
            raise ValueError(f"Entry #{index} is missing valid YAML frontmatter delimiters (---)")

        raw_yaml = parts[1].strip()
        content = "---".join(parts[2:]).strip()

        data: dict[str, Any] = yaml.safe_load(raw_yaml) or {}
        entity_name = str(data.get("entity_name") or "").strip()
        title = str(data.get("title") or "").strip()
        category = str(data.get("category") or "").strip()

        if not entity_name or not title:
            raise ValueError(f"Entry #{index} must have both 'entity_name' and 'title'")

        if category not in ALLOWED_CATEGORIES:
            raise ValueError(f"Entry '{entity_name}::{title}' has invalid category: '{category}'")

        if not content:
            raise ValueError(f"Entry '{entity_name}::{title}' has empty content")

        key = (entity_name, title)
        if key in seen_keys:
            raise ValueError(f"Duplicate entry key detected: {key}")
        seen_keys.add(key)

        content_hash = hashlib.sha256(content.strip().encode("utf-8")).hexdigest()

        entries.append(
            ParsedEntry(
                entity_name=entity_name,
                title=title,
                category=category,
                content=content,
                content_hash=content_hash,
                subcategory=data.get("subcategory"),
                tags=data.get("tags") or [],
                date_range=data.get("date_range"),
                status=data.get("status"),
                priority=data.get("priority"),
                links=data.get("links") or {},
                metrics=data.get("metrics") or [],
                active=bool(data.get("active", True)),
                source=str(data.get("source") or "manual_entry"),
                created_date=data.get("created_date"),
                last_updated=data.get("last_updated"),
            )
        )

    return entries


def format_entry_block(entry: dict[str, Any]) -> str:
    """Format an entry dictionary into a markdown ENTRY block."""
    frontmatter = {
        "entity_name": entry["entity_name"],
        "title": entry["title"],
        "category": entry["category"],
        "subcategory": entry.get("subcategory"),
        "tags": entry.get("tags", []),
        "date_range": entry.get("date_range"),
        "status": entry.get("status"),
        "priority": entry.get("priority"),
        "links": entry.get("links", {}),
        "metrics": entry.get("metrics", []),
        "active": entry.get("active", True),
        "source": entry.get("source", "manual_entry"),
        "created_date": entry.get("created_date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    yaml_str = yaml.dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
    return f"<!-- ENTRY START -->\n---\n{yaml_str}\n---\n{entry['content'].strip()}\n<!-- ENTRY END -->"


def upsert_entry_in_markdown(entry_data: dict[str, Any], file_path: Path | str) -> bool:
    """Insert or update a single entry block inside the markdown knowledge file."""
    path = Path(file_path)
    content = path.read_text(encoding="utf-8") if path.exists() else ""

    entity_name = entry_data["entity_name"].strip()
    title = entry_data["title"].strip()
    new_block = format_entry_block(entry_data)

    pattern = re.compile(
        rf"<!-- ENTRY START -->\s*---\s*entity_name:\s*{re.escape(entity_name)}\s*\ntitle:\s*{re.escape(title)}\s*\n.*?<!-- ENTRY END -->",
        re.DOTALL | re.IGNORECASE,
    )

    if pattern.search(content):
        updated_content = pattern.sub(new_block, content, count=1)
    else:
        updated_content = content.rstrip() + "\n\n" + new_block + "\n"

    path.write_text(updated_content, encoding="utf-8")
    return True


def sync_knowledge_base(dry_run: bool = False, verbose: bool = False) -> dict[str, int]:
    """Synchronize markdown facts to Supabase documentation table using hash-based diffing."""
    entries = parse_markdown_file(settings.facts_file_path)
    sb = get_supabase()

    db_res = sb.table("documentation").select("id, entity_name, title, content_hash, active, version").execute()
    db_map = {(row["entity_name"], row["title"]): row for row in (db_res.data or [])}

    new_entries: list[ParsedEntry] = []
    updated_entries: list[tuple[ParsedEntry, dict[str, Any]]] = []
    unchanged_count = 0

    seen_keys = set()
    for entry in entries:
        key = (entry.entity_name, entry.title)
        seen_keys.add(key)
        db_row = db_map.get(key)

        if not db_row:
            if entry.active:
                new_entries.append(entry)
        else:
            if db_row["content_hash"] != entry.content_hash or db_row["active"] != entry.active:
                updated_entries.append((entry, db_row))
            else:
                unchanged_count += 1

    archived_rows = [
        row for key, row in db_map.items()
        if key not in seen_keys and row.get("active", True)
    ]

    stats = {
        "inserted": len(new_entries),
        "updated": len(updated_entries),
        "archived": len(archived_rows),
        "unchanged": unchanged_count,
    }

    if verbose:
        print(f"[Sync] Planned actions: {stats}")

    if dry_run:
        return stats

    # Batch embed new and updated contents only
    items_to_embed = new_entries + [item[0] for item in updated_entries]
    embeddings_map: dict[tuple[str, str], list[float]] = {}

    if items_to_embed:
        if not settings.mistral_api_key:
            raise RuntimeError("MistralAI API key missing for embeddings generation")
        embedder = MistralAIEmbeddings(model="mistral-embed", api_key=settings.mistral_api_key)
        vectors = embedder.embed_documents([item.content for item in items_to_embed])
        for item, vector in zip(items_to_embed, vectors):
            embeddings_map[(item.entity_name, item.title)] = vector

    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Insert new entries
    for entry in new_entries:
        payload = {
            "entity_name": entry.entity_name,
            "title": entry.title,
            "category": entry.category,
            "subcategory": entry.subcategory,
            "content": entry.content,
            "content_hash": entry.content_hash,
            "embedding": embeddings_map.get((entry.entity_name, entry.title)),
            "tags": entry.tags,
            "date_range": entry.date_range,
            "status": entry.status,
            "priority": entry.priority,
            "links": entry.links,
            "metrics": entry.metrics,
            "active": entry.active,
            "source": entry.source,
            "version": 1,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        sb.table("documentation").insert(payload).execute()

    # 2. Update modified entries
    for entry, db_row in updated_entries:
        payload = {
            "category": entry.category,
            "subcategory": entry.subcategory,
            "content": entry.content,
            "content_hash": entry.content_hash,
            "embedding": embeddings_map.get((entry.entity_name, entry.title)),
            "tags": entry.tags,
            "date_range": entry.date_range,
            "status": entry.status,
            "priority": entry.priority,
            "links": entry.links,
            "metrics": entry.metrics,
            "active": entry.active,
            "source": entry.source,
            "version": (db_row.get("version") or 1) + 1,
            "updated_at": now_iso,
        }
        sb.table("documentation").update(payload).eq("id", db_row["id"]).execute()

    # 3. Soft-delete archived rows
    for row in archived_rows:
        sb.table("documentation").update({"active": False, "updated_at": now_iso}).eq("id", row["id"]).execute()

    return stats
