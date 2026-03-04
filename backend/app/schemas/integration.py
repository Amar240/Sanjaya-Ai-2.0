from __future__ import annotations

from pydantic import BaseModel, Field

from .plan import PlanMode, ProgramLevel, Term


class MyUDLaunchRequest(BaseModel):
    student_id_hash: str = Field(min_length=6)
    major: str
    class_year: int = Field(ge=1, le=6)
    current_term: Term
    completed_courses: list[str] = Field(default_factory=list)
    level: ProgramLevel = "UG"
    mode: PlanMode = "CORE"
    interests: list[str] = Field(default_factory=list)
    preferred_role_id: str | None = None


class MyUDLaunchResponse(BaseModel):
    plan_id: str
    selected_role: str
    selected_role_id: str
    coverage_pct: int
    missing_skills: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    deep_links: dict[str, str] = Field(default_factory=dict)


class MyUDPlanSummaryResponse(BaseModel):
    plan_id: str
    selected_role: str
    selected_role_id: str
    coverage_pct: int
    missing_skills: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
