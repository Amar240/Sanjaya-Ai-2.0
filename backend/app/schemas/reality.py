from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SalaryUSD(BaseModel):
    p25: int | None = None
    median: int | None = None
    p75: int | None = None
    notes: str | None = None


class RoleRealityUSA(BaseModel):
    role_id: str
    role_title: str
    typical_tasks: list[str] = Field(default_factory=list)
    salary_usd: SalaryUSD
    sources: list[str] = Field(default_factory=list)
    last_updated: str


class ProjectLink(BaseModel):
    label: str
    url: str


class ProjectTemplate(BaseModel):
    template_id: str
    skill_id: str
    level: Literal["beginner", "intermediate", "advanced"]
    title: str
    time_hours: int
    prerequisites: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    rubric: list[str] = Field(default_factory=list)
    links: list[ProjectLink] = Field(default_factory=list)
    notes: str | None = None


class ProjectTemplateRef(BaseModel):
    template_id: str
    title: str
    level: Literal["beginner", "intermediate", "advanced"]
    time_hours: int
    effort_fit: Literal["fits", "stretch", "heavy"] = "stretch"
    deliverables: list[str] = Field(default_factory=list)


class MissingSkillItem(BaseModel):
    skill_id: str
    skill_name: str
    reason: str
    recommended_projects: list[ProjectTemplateRef] = Field(default_factory=list)


class CoveredSkillItem(BaseModel):
    skill_id: str
    skill_name: str
    matched_courses: list[str] = Field(default_factory=list)


class GapReport(BaseModel):
    missing_skills: list[MissingSkillItem] = Field(default_factory=list)
    covered_skills: list[CoveredSkillItem] = Field(default_factory=list)
