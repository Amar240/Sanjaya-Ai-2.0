from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class StoryboardRequest(BaseModel):
    plan_id: str
    tone: Literal["friendly", "concise"] = "friendly"
    audience_level: Literal["beginner", "intermediate"] = "beginner"


class StoryboardCitation(BaseModel):
    kind: Literal["source_id", "evidence_id"]
    id: str


class StoryboardSection(BaseModel):
    title: str
    body: str
    citations: list[StoryboardCitation] = Field(default_factory=list)


class StoryboardResponse(BaseModel):
    plan_id: str
    sections: list[StoryboardSection] = Field(default_factory=list)
    llm_status: Literal["used", "fallback", "disabled"] = "disabled"
    llm_error: str | None = None
