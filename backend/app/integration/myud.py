from __future__ import annotations

import hashlib
import hmac
import os

from ..schemas.integration import (
    MyUDLaunchRequest,
    MyUDLaunchResponse,
    MyUDPlanSummaryResponse,
)
from ..schemas.plan import PlanRequest, StudentProfile


def validate_myud_signature(*, payload: MyUDLaunchRequest, signature: str | None) -> bool:
    secret = os.getenv("SANJAYA_MYUD_SHARED_SECRET", "").strip()
    if not secret:
        return True
    if not signature:
        return False
    raw = (
        f"{payload.student_id_hash}|{payload.major}|{payload.class_year}|{payload.current_term}"
    ).encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


def build_plan_request_from_myud(payload: MyUDLaunchRequest) -> PlanRequest:
    interests = list(payload.interests) if payload.interests else _default_interests_from_major(payload.major)
    profile = StudentProfile(
        level=payload.level,
        mode=payload.mode,
        current_semester=max(1, payload.class_year * 2 - 1),
        start_term=payload.current_term,
        include_optional_terms=False,
        completed_courses=list(payload.completed_courses),
        min_credits=12 if payload.level == "UG" else 9,
        target_credits=15 if payload.level == "UG" else 9,
        max_credits=17 if payload.level == "UG" else 12,
        degree_total_credits=128 if payload.level == "UG" else 33,
        interests=interests,
    )
    return PlanRequest(
        student_profile=profile,
        preferred_role_id=payload.preferred_role_id,
        requested_role_text=None,
    )


def build_myud_launch_response(plan) -> MyUDLaunchResponse:
    coverage_pct = _coverage_pct(plan)
    missing_skills = [
        item.required_skill_id
        for item in plan.skill_coverage
        if not item.covered
    ]
    next_actions = build_next_actions(plan)
    return MyUDLaunchResponse(
        plan_id=plan.plan_id,
        selected_role=plan.selected_role_title,
        selected_role_id=plan.selected_role_id,
        coverage_pct=coverage_pct,
        missing_skills=missing_skills[:8],
        next_actions=next_actions,
        deep_links={
            "course_registration": "/myud/webreg",
            "degree_planning": "/myud/stellic",
            "learning_platform": "/myud/canvas",
        },
    )


def build_myud_summary_response(plan) -> MyUDPlanSummaryResponse:
    return MyUDPlanSummaryResponse(
        plan_id=plan.plan_id,
        selected_role=plan.selected_role_title,
        selected_role_id=plan.selected_role_id,
        coverage_pct=_coverage_pct(plan),
        missing_skills=[item.required_skill_id for item in plan.skill_coverage if not item.covered][:8],
        next_actions=build_next_actions(plan),
    )


def build_next_actions(plan) -> list[str]:
    actions: list[str] = []
    if plan.gap_report and plan.gap_report.missing_skills:
        first_gap = plan.gap_report.missing_skills[0]
        actions.append(
            f"Start a project for {first_gap.skill_name} using template "
            f"{first_gap.recommended_projects[0].template_id if first_gap.recommended_projects else 'to be assigned'}."
        )
    if plan.semesters:
        first = plan.semesters[0]
        if first.courses:
            actions.append(f"Register the first roadmap semester courses: {', '.join(first.courses[:3])}.")
    if plan.validation_errors:
        actions.append("Review plan warnings with advisor and resolve the top issue before registration.")
    if not actions:
        actions.append("Proceed with the next semester courses and keep evidence-backed project progress.")
    return actions[:4]


def _coverage_pct(plan) -> int:
    total = len(plan.skill_coverage)
    if total == 0:
        return 0
    covered = sum(1 for item in plan.skill_coverage if item.covered)
    return int(round((covered / total) * 100))


def _default_interests_from_major(major: str) -> list[str]:
    lower = major.lower()
    if "computer" in lower or "cis" in lower:
        return ["software engineering", "data systems"]
    if "finance" in lower or "account" in lower:
        return ["finance analytics", "risk modeling"]
    if "biology" in lower or "bio" in lower:
        return ["bioinformatics", "data analysis"]
    return ["career exploration", "applied analytics"]
