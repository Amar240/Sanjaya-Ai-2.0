from __future__ import annotations

from app.agents.fingerprint import compute_plan_id
from app.schemas.plan import PlanRequest, StudentProfile


def _request(completed: list[str], interests: list[str]) -> PlanRequest:
    return PlanRequest(
        student_profile=StudentProfile(
            level="UG",
            mode="CORE",
            current_semester=1,
            start_term="Fall",
            include_optional_terms=False,
            completed_courses=completed,
            min_credits=12,
            target_credits=15,
            max_credits=17,
            interests=interests,
        ),
        preferred_role_id="ROLE_TEST",
    )


def test_plan_id_is_deterministic_for_same_content() -> None:
    req_a = _request(["CISC-201", "CISC-101"], ["python", "data"])
    req_b = _request(["CISC-101", "CISC-201"], ["data", "python"])

    plan_id_a = compute_plan_id(req_a, "v1")
    plan_id_b = compute_plan_id(req_b, "v1")

    assert plan_id_a == plan_id_b


def test_plan_id_changes_when_data_version_changes() -> None:
    req = _request(["CISC-101"], ["python"])
    assert compute_plan_id(req, "v1") != compute_plan_id(req, "v2")
