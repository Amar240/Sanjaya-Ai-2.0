from __future__ import annotations

from uuid import UUID

from app.agents.workflow import run_plan_workflow
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


def test_request_id_is_present_and_uuid(sample_store) -> None:
    plan = run_plan_workflow(_request(), sample_store)
    assert plan.request_id
    parsed = UUID(plan.request_id)
    assert str(parsed) == plan.request_id
