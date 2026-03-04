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


def test_advisor_out_of_context_question_is_safely_limited(sample_store) -> None:
    plan = run_plan_workflow(_request(), sample_store)
    response = answer_advisor_question(
        AdvisorRequest(
            question="Can you guarantee me a job if I follow this plan?",
            plan=plan,
            tone="friendly",
        ),
        sample_store,
    )
    assert response.intent == "safety_limit"
    assert "cannot guarantee" in response.answer.lower()
    assert response.citations == []
