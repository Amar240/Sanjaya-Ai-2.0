from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .reality import ProjectTemplateRef


class JobExtractRequest(BaseModel):
    text: str = Field(min_length=50, max_length=8000)


class JobExtractResult(BaseModel):
    job_title: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)


class JobMatchRequest(JobExtractRequest):
    plan_id: str | None = None


class MappedSkillItem(BaseModel):
    skill_id: str
    skill_name: str
    source: Literal["required", "preferred", "tool"]
    match_confidence: float = Field(ge=0.0, le=1.0)
    matched_by: Literal["name_overlap", "synonym", "substring"] | None = None
    matched_on: str | None = None


class UnmappedTerm(BaseModel):
    term: str
    source: Literal["required", "preferred", "tool"]


class MappingSummary(BaseModel):
    mapped_count: int = 0
    unmapped_count: int = 0
    threshold_used: float = 0.35


class JobSkillProjects(BaseModel):
    skill_id: str
    skill_name: str
    projects: list[ProjectTemplateRef] = Field(default_factory=list)


class JobMatchResponse(BaseModel):
    job_title: str | None = None
    extracted: JobExtractResult
    mapped_skills: list[MappedSkillItem] = Field(default_factory=list)
    unmapped_terms: list[UnmappedTerm] = Field(default_factory=list)
    mapping_summary: MappingSummary = Field(default_factory=MappingSummary)
    covered_skill_ids: list[str] = Field(default_factory=list)
    missing_skill_ids: list[str] = Field(default_factory=list)
    out_of_scope_skill_ids: list[str] = Field(default_factory=list)
    recommended_projects: list[JobSkillProjects] = Field(default_factory=list)
    disclaimer: str = (
        "We extract skills from pasted text and map to our verified skill catalog. "
        "This is guidance, not a job guarantee."
    )
    llm_status: Literal["used", "fallback", "disabled"] = "disabled"
    llm_error: str | None = None
