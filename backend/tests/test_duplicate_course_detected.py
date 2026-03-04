from __future__ import annotations

from app.agents.repair import retryable_errors
from app.schemas.plan import PlanRequest, PlanSemester, SkillCoverage, StudentProfile
from app.validators.plan_verifier import verify_plan


def test_duplicate_course_detected(sample_store) -> None:
    request = PlanRequest(
        student_profile=StudentProfile(
            level="UG",
            mode="CORE",
            current_semester=1,
            start_term="Fall",
            include_optional_terms=False,
            completed_courses=[],
            min_credits=0,
            target_credits=6,
            max_credits=9,
            interests=["test"],
        ),
        preferred_role_id="ROLE_TEST",
    )
    semesters = [
        PlanSemester(semester_index=1, term="Fall", courses=["CISC-101"], total_credits=3.0),
        PlanSemester(semester_index=2, term="Spring", courses=["CISC-101"], total_credits=3.0),
    ]
    errors, _, _ = verify_plan(
        request=request,
        role=sample_store.roles[0],
        semesters=semesters,
        courses_by_id=sample_store.courses_by_id,
        skill_coverage=[SkillCoverage(required_skill_id="SK_TEST", covered=True, matched_courses=[])],
        all_courses_by_id=sample_store.courses_by_id,
        course_skills=sample_store.course_skills,
        curated_role_skill_courses=sample_store.curated_role_skill_courses,
    )
    dupes = [err for err in errors if err.code == "DUPLICATE_COURSE"]
    assert dupes
    assert dupes[0].details.get("severity") == "error"
    assert retryable_errors(dupes) == []
