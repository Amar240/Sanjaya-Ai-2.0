from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthCounts(BaseModel):
    courses: int = 0
    roles: int = 0
    skills: int = 0
    sources: int = 0
    role_skill_evidence_links: int = 0


class ChromaHealth(BaseModel):
    enabled: bool = False
    persist_dir: str | None = None
    roles_count: int | None = None
    evidence_count: int | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    data_version: str | None = None
    counts: HealthCounts = Field(default_factory=HealthCounts)
    chroma: ChromaHealth = Field(default_factory=ChromaHealth)
    startup_validation_errors: int = 0
    startup_validation_samples: list[str] = Field(default_factory=list)
