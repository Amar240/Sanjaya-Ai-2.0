from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .plan import PlanResponse


class AdvisorRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    tone: Literal["friendly", "concise"] = "friendly"
    plan_id: str | None = None
    plan: PlanResponse | None = None
    course_id: str | None = None

    @model_validator(mode="after")
    def _validate_plan_reference(self) -> "AdvisorRequest":
        if self.plan_id:
            return self
        if self.plan is not None:
            return self
        raise ValueError("At least one of 'plan_id' or 'plan' must be provided.")


class AdvisorCitation(BaseModel):
    citation_type: Literal[
        "evidence_source",
        "course",
        "policy_note",
        "skill_coverage",
        "semester",
    ]
    label: str
    detail: str
    source_url: str | None = None
    evidence_id: str | None = None
    course_id: str | None = None
    skill_id: str | None = None


class AdvisorResponse(BaseModel):
    request_id: str = ""
    plan_id: str
    intent: str
    answer: str
    reasoning_points: list[str] = Field(default_factory=list)
    citations: list[AdvisorCitation] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    used_llm: bool = False
    llm_status: Literal["used", "fallback", "disabled"] = "disabled"
    llm_error: str | None = None
