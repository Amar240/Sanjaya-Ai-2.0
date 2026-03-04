from __future__ import annotations

from app.agents.reality_attach import attach_role_reality
from app.schemas.plan import PlanResponse


def test_role_reality_attaches_for_existing_role(sample_store) -> None:
    plan = PlanResponse(selected_role_id="ROLE_TEST", selected_role_title="Test Role")
    reality, warnings = attach_role_reality(plan, sample_store)
    assert reality is not None
    assert reality.role_id == "ROLE_TEST"
    assert warnings == []


def test_role_reality_missing_emits_warning(sample_store) -> None:
    plan = PlanResponse(selected_role_id="ROLE_UNKNOWN", selected_role_title="Unknown Role")
    reality, warnings = attach_role_reality(plan, sample_store)
    assert reality is None
    assert len(warnings) == 1
    warning = warnings[0]
    assert warning.code == "ROLE_REALITY_MISSING"
    assert warning.details.get("severity") == "warning"
