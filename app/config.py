from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    groq_api_key: str | None
    mistral_api_key: str | None
    admin_api_key: str | None
    chroma_persist_dir: Path
    knowledge_dir: Path
    cors_allow_origins: list[str]

    # Supabase
    supabase_url: str | None
    supabase_key: str | None          # anon/public key (used by client-side & JWT verification)
    supabase_service_key: str | None  # service-role key (server-side DB writes, bypasses RLS)

    # Admin auth – the email of the sole admin user in Supabase Auth
    admin_email: str | None


BASE_DIR = Path(__file__).resolve().parents[1]

settings = Settings(
    base_dir=BASE_DIR,
    groq_api_key=os.getenv("GROQ_API_KEY"),
    mistral_api_key=os.getenv("MistralAI"),
    admin_api_key=os.getenv("ADMIN_API_KEY"),
    chroma_persist_dir=Path(
        os.getenv("CHROMA_PERSIST_DIR", str(BASE_DIR / "app" / "db" / "chroma_db100"))
    ),
    knowledge_dir=Path(os.getenv("KNOWLEDGE_DIR", str(BASE_DIR / "app" / "knowledge"))),
    cors_allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),

    # Supabase
    supabase_url=os.getenv("SUPABASE_URL"),
    supabase_key=os.getenv("SUPABASE_KEY"),
    supabase_service_key=os.getenv("SUPABASE_SERVICE_KEY"),

    # Admin
    admin_email=os.getenv("ADMIN_EMAIL"),
)
