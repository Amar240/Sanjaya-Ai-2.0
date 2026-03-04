from __future__ import annotations

from app.agents.workflow import reset_plan_cache, run_plan_workflow
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


def test_candidate_roles_are_deterministic(sample_store) -> None:
    sample_store.data_version = "candidate-roles-deterministic-v1"
    reset_plan_cache(max_size=256)
    first = run_plan_workflow(_request(), sample_store)

    sample_store.data_version = "candidate-roles-deterministic-v1"
    reset_plan_cache(max_size=256)
    second = run_plan_workflow(_request(), sample_store)

    first_snapshot = [(row.role_id, row.score, tuple(row.reasons)) for row in first.candidate_roles]
    second_snapshot = [(row.role_id, row.score, tuple(row.reasons)) for row in second.candidate_roles]
    assert first_snapshot == second_snapshot
