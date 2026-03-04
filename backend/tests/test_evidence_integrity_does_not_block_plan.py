from __future__ import annotations

from app.agents.repair import retryable_errors
from app.schemas.plan import EvidencePanelItem, PlanRequest, PlanResponse, SkillCoverage, StudentProfile
from app.validators.plan_verifier import verify_plan


def _evidence(*, evidence_id: str, role_id: str, skill_id: str) -> EvidencePanelItem:
    return EvidencePanelItem(
        evidence_id=evidence_id,
        role_id=role_id,
        skill_id=skill_id,
        skill_name=skill_id,
        source_id="SRC_TEST",
        source_provider="Test Provider",
        source_title="Test Source",
        source_url="https://example.com/source",
        snippet="test snippet",
        retrieval_method="lexical",
        rank_score=0.5,
        confidence=0.8,
    )


def test_evidence_integrity_warning_is_non_retryable(sample_store) -> None:
    request = PlanRequest(
        student_profile=StudentProfile(
            level="UG",
            mode="CORE",
            current_semester=1,
            start_term="Fall",
            include_optional_terms=False,
            completed_courses=[],
            min_credits=6,
            target_credits=6,
            max_credits=9,
            interests=["test"],
        ),
        preferred_role_id="ROLE_TEST",
    )
    plan = PlanResponse(
        selected_role_id="ROLE_TEST",
        selected_role_title="Test Role",
        skill_coverage=[
            SkillCoverage(required_skill_id="SK_TEST", covered=True, matched_courses=["CISC-101"])
        ],
        evidence_panel=[_evidence(evidence_id="ev-1", role_id="ROLE_OTHER", skill_id="SK_TEST")],
    )

    errors, _, _ = verify_plan(
        request=request,
        role=sample_store.roles[0],
        semesters=[],
        courses_by_id=sample_store.courses_by_id,
        skill_coverage=plan.skill_coverage,
        all_courses_by_id=sample_store.courses_by_id,
        course_skills=sample_store.course_skills,
        curated_role_skill_courses=sample_store.curated_role_skill_courses,
        plan=plan,
    )

    evidence_warnings = [err for err in errors if err.code == "EVIDENCE_INTEGRITY_VIOLATION"]
    assert evidence_warnings
    assert all(err.details.get("severity") == "warning" for err in evidence_warnings)
    assert retryable_errors(evidence_warnings) == []
