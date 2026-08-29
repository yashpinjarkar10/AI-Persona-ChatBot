from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

CategoryType = Literal[
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
]


class AdminEntryRequest(BaseModel):
    entity_name: str = Field(..., min_length=1, description="Top-level anchor (project, company, or section name)")
    title: str = Field(..., min_length=1, description="Facet label (lowercase-hyphenated recommended)")
    category: CategoryType = Field(..., description="Allowed knowledge category")
    subcategory: str | None = Field(default=None, description="Finer classification")
    tags: list[str] = Field(default_factory=list, description="Keywords for filtering")
    date_range: str | None = Field(default=None, description="Date range, e.g., '2025-2026'")
    status: str | None = Field(default=None, description="ongoing | completed | archived")
    priority: int | None = Field(default=None, ge=1, le=5, description="1 (highest) to 5 (lowest)")
    links: dict[str, str] = Field(default_factory=dict, description="URLs such as github, demo, etc.")
    metrics: list[str] = Field(default_factory=list, description="Quantifiable metrics")
    content: str = Field(..., min_length=1, description="Self-contained chunk text")
    active: bool = Field(default=True, description="Soft active flag")
    source: str = Field(default="manual_entry", description="Source of the fact")


class SyncResponse(BaseModel):
    message: str
    result: dict[str, int]
