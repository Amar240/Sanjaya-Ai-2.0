from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .reality import GapReport, RoleRealityUSA

ProgramLevel = Literal["UG", "GR"]
PlanMode = Literal["CORE", "FUSION"]
GoalType = Literal["select_role", "type_role", "explore"]
ConfidenceLevel = Literal["low", "medium", "high"]
Term = Literal["Fall", "Spring", "Summer", "Winter"]
PlanErrorCode = Literal[
    "COURSE_NOT_FOUND",
    "PREREQ_ORDER",
    "CREDIT_OVER_MAX",
    "CREDITS_BELOW_MIN",
    "LEVEL_MISMATCH",
    "OFFERING_MISMATCH",
    "DUPLICATE_COURSE",
    "ANTIREQ_CONFLICT",
    "COREQ_NOT_SATISFIED",
    "SKILL_GAP",
    "PREREQ_EXTERNAL_REF",
    "PREREQ_COMPLEX_UNSUPPORTED",
    "EVIDENCE_INTEGRITY_VIOLATION",
    "ROLE_REQUEST_UNRESOLVED",
    "ROLE_REALITY_MISSING",
    "TOTAL_CREDITS_OVER_DEGREE",
    "TOTAL_CREDITS_UNDER_DEGREE",
]


class StudentProfile(BaseModel):
    level: ProgramLevel
    mode: PlanMode = "CORE"
    goal_type: GoalType = "select_role"
    confidence_level: ConfidenceLevel = "medium"
    hours_per_week: int = Field(default=6, ge=0, le=40)
    fusion_domain: str | None = None
    current_semester: int = Field(ge=1, le=12)
    start_term: Term = "Fall"
    include_optional_terms: bool = False
    completed_courses: list[str] = Field(default_factory=list)
    min_credits: int = Field(default=12, ge=0, le=30)
    target_credits: int = Field(default=15, ge=0, le=30)
    max_credits: int = Field(default=17, ge=0, le=30)
    degree_total_credits: int | None = Field(default=None, ge=1, le=200)
    interests: list[str] = Field(default_factory=list)


class PlanRequest(BaseModel):
    student_profile: StudentProfile
    preferred_role_id: str | None = None
    requested_role_text: str | None = None


class SkillCoverage(BaseModel):
    required_skill_id: str
    covered: bool
    matched_courses: list[str] = Field(default_factory=list)


class PlanSemester(BaseModel):
    semester_index: int
    term: Term = "Fall"
    courses: list[str] = Field(default_factory=list)
    total_credits: float = 0
    warnings: list[str] = Field(default_factory=list)


class EvidencePanelItem(BaseModel):
    evidence_id: str
    role_id: str
    skill_id: str
    skill_name: str
    source_id: str
    source_provider: str
    source_title: str
    source_url: str
    snippet: str
    retrieval_method: Literal["vector", "lexical", "hybrid"]
    rank_score: float | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class CoursePurposeCard(BaseModel):
    course_id: str
    course_title: str
    why_this_course: str
    satisfied_skills: list[str] = Field(default_factory=list)
    evidence: list[EvidencePanelItem] = Field(default_factory=list)


class CandidateRole(BaseModel):
    role_id: str
    role_title: str
    score: float
    reasons: list[str] = Field(default_factory=list)


class ReadinessFactor(BaseModel):
    name: str
    value: float
    description: str


class ReadinessSummary(BaseModel):
    readiness_band: Literal["Early", "Developing", "Market-Ready Track"]
    score: float = Field(ge=0.0, le=1.0)
    factors: list[ReadinessFactor] = Field(default_factory=list)
    unresolved_warning_count: int = 0
    missing_skill_count: int = 0


class DepartmentContext(BaseModel):
    primary_department: str = ""
    supporting_departments: list[str] = Field(default_factory=list)


class FusionPackSummary(BaseModel):
    fusion_pack_id: str
    title: str
    domain_a: str
    domain_b: str
    target_roles: list[str] = Field(default_factory=list)
    unlock_skills: list[str] = Field(default_factory=list)
    starter_projects: list[str] = Field(default_factory=list)
    evidence_sources: list[str] = Field(default_factory=list)


class FusionReadiness(BaseModel):
    domain_ready_pct: float = Field(ge=0.0, le=1.0)
    tech_ready_pct: float = Field(ge=0.0, le=1.0)
    overall_fit_pct: float = Field(ge=0.0, le=1.0)


class FusionUnlockSkillStatus(BaseModel):
    skill_id: str
    reason: str
    covered: bool
    matched_courses: list[str] = Field(default_factory=list)


class FusionSummary(BaseModel):
    domain: str
    domain_weight: float = Field(ge=0.0, le=1.0)
    tech_weight: float = Field(ge=0.0, le=1.0)
    domain_skill_coverage: list[SkillCoverage] = Field(default_factory=list)
    tech_skill_coverage: list[SkillCoverage] = Field(default_factory=list)
    unlock_skills: list[FusionUnlockSkillStatus] = Field(default_factory=list)
    readiness: FusionReadiness


class PlanError(BaseModel):
    code: PlanErrorCode
    message: str
    course_id: str | None = None
    prereq_id: str | None = None
    term: Term | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class PlanResponse(BaseModel):
    request_id: str = ""
    plan_id: str = ""
    cache_status: Literal["hit", "miss"] = "miss"
    data_version: str = ""
    selected_role_id: str
    selected_role_title: str
    skill_coverage: list[SkillCoverage] = Field(default_factory=list)
    semesters: list[PlanSemester] = Field(default_factory=list)
    validation_errors: list[PlanError] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    candidate_roles: list[CandidateRole] = Field(default_factory=list)
    evidence_panel: list[EvidencePanelItem] = Field(default_factory=list)
    course_purpose_cards: list[CoursePurposeCard] = Field(default_factory=list)
    readiness_summary: ReadinessSummary | None = None
    department_context: DepartmentContext | None = None
    fusion_pack_summary: FusionPackSummary | None = None
    role_reality: RoleRealityUSA | None = None
    gap_report: GapReport | None = None
    fusion_summary: FusionSummary | None = None
    intake_snapshot: StudentProfile | None = None
    agent_trace: list[str] = Field(default_factory=list)
    node_timings: list[dict[str, int | str]] = Field(default_factory=list)
