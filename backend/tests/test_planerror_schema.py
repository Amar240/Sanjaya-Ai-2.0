from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.plan import PlanError, PlanResponse


def test_planerror_serializes_and_planresponse_accepts_structured_errors() -> None:
    error = PlanError(
        code="CREDIT_OVER_MAX",
        message="Semester 1 exceeds max credits.",
        term="Fall",
        details={"semester_index": 1, "planned_credits": 19, "max_credits": 17},
    )
    response = PlanResponse(
        selected_role_id="ROLE_TEST",
        selected_role_title="Test Role",
        validation_errors=[error],
    )
    payload = response.model_dump()
    assert payload["validation_errors"][0]["code"] == "CREDIT_OVER_MAX"
    assert payload["validation_errors"][0]["details"]["planned_credits"] == 19


def test_planresponse_rejects_string_validation_errors() -> None:
    with pytest.raises(ValidationError):
        PlanResponse(
            selected_role_id="ROLE_TEST",
            selected_role_title="Test Role",
            validation_errors=["legacy string error"],  # type: ignore[list-item]
        )
