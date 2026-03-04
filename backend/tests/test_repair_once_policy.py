from __future__ import annotations

from app.agents.repair import repair_once
from app.schemas.plan import PlanError, PlanRequest, PlanResponse, StudentProfile


def _base_request() -> PlanRequest:
    return PlanRequest(
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
            interests=["test"],
        ),
        preferred_role_id="ROLE_TEST",
    )


def test_repair_once_credit_over_max(sample_store) -> None:
    request = _base_request()
    draft_plan = PlanResponse(
        selected_role_id="ROLE_TEST",
        selected_role_title="Test Role",
    )
    errors = [PlanError(code="CREDIT_OVER_MAX", message="over max")]
    patched, meta = repair_once(request, draft_plan, errors, sample_store)

    assert patched.student_profile.target_credits == 12
    assert patched.student_profile.max_credits == 12
    assert meta["trace_events"] == [
        "repair: reduced target credits due to CREDIT_OVER_MAX"
    ]


def test_repair_once_prereq_order_enables_optional_terms(sample_store) -> None:
    request = _base_request()
    draft_plan = PlanResponse(
        selected_role_id="ROLE_TEST",
        selected_role_title="Test Role",
    )
    errors = [PlanError(code="PREREQ_ORDER", message="prereq order issue")]
    patched, meta = repair_once(request, draft_plan, errors, sample_store)

    assert patched.student_profile.include_optional_terms is True
    assert meta["trace_events"] == [
        "repair: enabled optional terms due to PREREQ_ORDER"
    ]
