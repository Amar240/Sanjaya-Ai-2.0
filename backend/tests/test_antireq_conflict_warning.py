from __future__ import annotations

from app.schemas.plan import PlanRequest, PlanSemester, SkillCoverage, StudentProfile
from app.validators.plan_verifier import verify_plan


def test_antireq_conflict_warning(sample_store) -> None:
    sample_store.courses_by_id["CISC-101"].antirequisites = ["CISC-201"]
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
        PlanSemester(semester_index=2, term="Spring", courses=["CISC-201"], total_credits=3.0),
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
    warnings = [err for err in errors if err.code == "ANTIREQ_CONFLICT"]
    assert warnings
    assert warnings[0].details.get("severity") == "warning"
