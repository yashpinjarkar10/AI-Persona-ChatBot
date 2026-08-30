from __future__ import annotations

import base64
import gzip
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
FACTS_PATH = BASE_DIR / "personal_facts.md"
if not FACTS_PATH.exists() and os.getenv("PERSONAL_FACTS_BASE64"):
    try:
        FACTS_PATH.write_bytes(gzip.decompress(base64.b64decode(os.getenv("PERSONAL_FACTS_BASE64", "").strip())))
    except Exception:
        FACTS_PATH.write_bytes(base64.b64decode(os.getenv("PERSONAL_FACTS_BASE64", "").strip()))


@dataclass(frozen=True)
class Settings:
    groq_api_key: str | None
    mistral_api_key: str | None
    supabase_url: str | None
    supabase_key: str | None
    supabase_service_key: str | None
    cors_allow_origins: list[str]
    admin_api_key: str | None
    facts_file_path: Path


settings = Settings(
    groq_api_key=os.getenv("GROQ_API_KEY"),
    mistral_api_key=os.getenv("MistralAI"),
    supabase_url=os.getenv("SUPABASE_URL"),
    supabase_key=os.getenv("SUPABASE_KEY"),
    supabase_service_key=os.getenv("SUPABASE_SERVICE_KEY"),
    cors_allow_origins=[origin.strip() for origin in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if origin.strip()],
    admin_api_key=os.getenv("ADMIN_API_KEY"),
    facts_file_path=FACTS_PATH,
)
