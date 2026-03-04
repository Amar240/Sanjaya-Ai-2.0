from __future__ import annotations

from app.agents.planner import build_plan
from app.schemas.plan import PlanRequest, StudentProfile


def test_topo_scheduler_is_deterministic(sample_store) -> None:
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
    plan_one = build_plan(request, sample_store)
    plan_two = build_plan(request, sample_store)

    assert [sem.model_dump() for sem in plan_one.semesters] == [
        sem.model_dump() for sem in plan_two.semesters
    ]
