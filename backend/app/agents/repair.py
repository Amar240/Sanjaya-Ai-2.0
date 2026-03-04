from __future__ import annotations

from ..data_loader import CatalogStore
from ..schemas.plan import PlanError, PlanRequest, PlanResponse

RETRYABLE_ERROR_CODES = {"CREDIT_OVER_MAX", "PREREQ_ORDER", "OFFERING_MISMATCH"}


def retryable_errors(errors: list[PlanError]) -> list[PlanError]:
    return [error for error in errors if error.code in RETRYABLE_ERROR_CODES]


def repair_once(
    request: PlanRequest,
    draft_plan: PlanResponse,
    errors: list[PlanError],
    store: CatalogStore,
) -> tuple[PlanRequest, dict]:
    del draft_plan
    del store

    patched = request.model_copy(deep=True)
    codes = {error.code for error in errors}
    trace_event = ""

    if "CREDIT_OVER_MAX" in codes:
        profile = patched.student_profile
        profile.target_credits = max(profile.min_credits, profile.target_credits - 3)
        profile.max_credits = min(profile.max_credits, profile.target_credits)
        trace_event = "repair: reduced target credits due to CREDIT_OVER_MAX"
    elif "PREREQ_ORDER" in codes:
        patched.student_profile.include_optional_terms = True
        trace_event = "repair: enabled optional terms due to PREREQ_ORDER"
    elif "OFFERING_MISMATCH" in codes:
        patched.student_profile.include_optional_terms = True
        trace_event = "repair: enabled optional terms due to OFFERING_MISMATCH"
    else:
        patched.student_profile.include_optional_terms = True
        trace_event = "repair: enabled optional terms (default)"

    return patched, {"trace_events": [trace_event]}
