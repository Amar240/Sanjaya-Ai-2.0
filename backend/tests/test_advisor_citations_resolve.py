from __future__ import annotations

from app.agents.advisor_agent import answer_advisor_question
from app.agents.workflow import run_plan_workflow
from app.schemas.advisor import AdvisorRequest
from app.schemas.plan import PlanRequest, StudentProfile


def _request() -> PlanRequest:
    return PlanRequest(
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


def test_advisor_citations_are_plan_resolvable(sample_store) -> None:
    plan = run_plan_workflow(_request(), sample_store)
    response = answer_advisor_question(
        AdvisorRequest(question="Why this role for me?", plan=plan, tone="friendly"),
        sample_store,
    )

    evidence_ids = {item.evidence_id for item in plan.evidence_panel}
    course_ids = {course_id for sem in plan.semesters for course_id in sem.courses}
    skill_ids = {item.required_skill_id for item in plan.skill_coverage}
    for citation in response.citations:
        if citation.evidence_id:
            assert citation.evidence_id in evidence_ids
        if citation.course_id:
            assert citation.course_id in course_ids
        if citation.skill_id:
            assert citation.skill_id in skill_ids
