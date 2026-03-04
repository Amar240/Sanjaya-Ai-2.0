from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .plan import ConfidenceLevel, GoalType, PlanRequest, ProgramLevel, Term


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp_utc: str


class ChatProfileDraft(BaseModel):
    level: ProgramLevel = "UG"
    mode: Literal["CORE", "FUSION"] = "CORE"
    goal_type: GoalType = "select_role"
    confidence_level: ConfidenceLevel = "medium"
    hours_per_week: int = Field(default=6, ge=0, le=40)
    fusion_domain: str | None = None
    current_semester: int = Field(default=1, ge=1, le=12)
    start_term: Term = "Fall"
    include_optional_terms: bool = False
    completed_courses: list[str] = Field(default_factory=list)
    min_credits: int = Field(default=12, ge=0, le=30)
    target_credits: int = Field(default=15, ge=0, le=30)
    max_credits: int = Field(default=17, ge=0, le=30)
    degree_total_credits: int | None = Field(default=None, ge=1, le=200)
    interests: list[str] = Field(default_factory=list)
    preferred_role_id: str | None = None


class ChatRoleSuggestion(BaseModel):
    role_id: str
    title: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None
    reset_session: bool = False


class ChatResponse(BaseModel):
    session_id: str
    assistant_message: str
    profile_draft: ChatProfileDraft
    missing_fields: list[str] = Field(default_factory=list)
    suggested_roles: list[ChatRoleSuggestion] = Field(default_factory=list)
    ready_for_plan: bool = False
    plan_request_draft: PlanRequest | None = None
    conversation: list[ChatTurn] = Field(default_factory=list)
    llm_used: bool = False
