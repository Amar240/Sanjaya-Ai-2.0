from __future__ import annotations

from app.agents.fingerprint import compute_plan_id
from app.schemas.plan import PlanRequest, StudentProfile


def _request(hours_per_week: int) -> PlanRequest:
    return PlanRequest(
        student_profile=StudentProfile(
            level="UG",
            mode="CORE",
            goal_type="select_role",
            confidence_level="medium",
            hours_per_week=hours_per_week,
            current_semester=1,
            start_term="Fall",
            include_optional_terms=False,
            completed_courses=[],
            min_credits=12,
            target_credits=15,
            max_credits=17,
            interests=["analytics"],
        ),
        preferred_role_id="ROLE_TEST",
    )


def test_plan_id_changes_with_hours_per_week() -> None:
    data_version = "dv-hours-test"
    first = compute_plan_id(_request(4), data_version)
    second = compute_plan_id(_request(10), data_version)
    assert first != second
