from __future__ import annotations

from app.schemas.plan import PlanRequest, PlanSemester, SkillCoverage, StudentProfile
from app.validators.plan_verifier import verify_plan


def test_verifier_emits_required_structured_codes(sample_store) -> None:
    request = PlanRequest(
        student_profile=StudentProfile(
            level="UG",
            mode="CORE",
            current_semester=1,
            start_term="Fall",
            include_optional_terms=False,
            completed_courses=[],
            min_credits=12,
            target_credits=15,
            max_credits=17,
            interests=["testing"],
        ),
        preferred_role_id="ROLE_TEST",
    )
    semesters = [
        PlanSemester(
            semester_index=1,
            term="Fall",
            courses=["CISC-201", "MISSING-999"],
            total_credits=20.0,
            warnings=[],
        )
    ]

    errors, _, _ = verify_plan(
        request=request,
        role=sample_store.roles[0],
        semesters=semesters,
        courses_by_id=sample_store.courses_by_id,
        skill_coverage=[
            SkillCoverage(
                required_skill_id="SK_TEST",
                covered=True,
                matched_courses=["CISC-201"],
            )
        ],
        all_courses_by_id=sample_store.courses_by_id,
        course_skills=sample_store.course_skills,
        curated_role_skill_courses=sample_store.curated_role_skill_courses,
    )
    codes = {error.code for error in errors}
    assert "COURSE_NOT_FOUND" in codes
    assert "PREREQ_ORDER" in codes
    assert "CREDIT_OVER_MAX" in codes
