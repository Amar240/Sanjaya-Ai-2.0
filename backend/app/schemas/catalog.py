from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class Course(BaseModel):
    course_id: str
    title: str
    department: str
    level: Literal["UG", "GR"]
    credits: float
    description: str
    topics: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    prerequisites_text: str = ""
    corequisites: list[str] = Field(default_factory=list)
    corequisites_text: str = ""
    antirequisites: list[str] = Field(default_factory=list)
    antirequisites_text: str = ""
    offered_terms: list[str] = Field(default_factory=list)
    source_url: HttpUrl


class SkillMarket(BaseModel):
    skill_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    category: str
    source_refs: list[str] = Field(default_factory=list)


class CourseSkillMapping(BaseModel):
    course_id: str
    skill_id: str
    strength: int = Field(ge=1, le=5)


class CuratedRoleSkillCourse(BaseModel):
    role_id: str
    skill_id: str
    course_id: str
    strength: int = Field(ge=1, le=5)
    rationale: str = ""


class FusionSkillRequirement(BaseModel):
    skill_id: str
    importance: int = Field(ge=1, le=5)


class FusionUnlockSkill(BaseModel):
    skill_id: str
    reason: str


class FusionSkillBands(BaseModel):
    domain_weight: float = Field(ge=0.0, le=1.0)
    tech_weight: float = Field(ge=0.0, le=1.0)


class FusionRoleProfile(BaseModel):
    role_id: str
    title: str
    domain: str
    skill_bands: FusionSkillBands
    domain_skills: list[FusionSkillRequirement] = Field(default_factory=list)
    tech_skills: list[FusionSkillRequirement] = Field(default_factory=list)
    unlock_skills: list[FusionUnlockSkill] = Field(default_factory=list)
    evidence_sources: list[str] = Field(default_factory=list)


class FusionPack(BaseModel):
    fusion_pack_id: str
    title: str
    domain_a: str
    domain_b: str
    target_roles: list[str] = Field(default_factory=list)
    unlock_skills: list[str] = Field(default_factory=list)
    starter_projects: list[str] = Field(default_factory=list)
    evidence_sources: list[str] = Field(default_factory=list)


class SourceReference(BaseModel):
    source_id: str
    provider: str
    type: str
    title: str
    url: HttpUrl
    retrieved_on: str


class RoleSkillRequirement(BaseModel):
    skill_id: str
    importance: int = Field(ge=1, le=5)


class RoleMarket(BaseModel):
    role_id: str
    title: str
    market_grounding: Literal["direct", "composite"]
    source_occupation_codes: list[dict]
    summary: str
    required_skills: list[RoleSkillRequirement]
    evidence_sources: list[str] = Field(default_factory=list)
    department_owner: str = ""
    country_scope: str = "USA"
    demo_tier: Literal["core", "fusion", "extended"] = "extended"
    reality_complete: bool = False
    project_coverage_complete: bool = False


class RoleSkillEvidence(BaseModel):
    role_id: str
    skill_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_sources: list[str] = Field(default_factory=list)
    evidence_note: str
