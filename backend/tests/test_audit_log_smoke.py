from __future__ import annotations

import json
import logging

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


def test_audit_log_emitted(sample_store, caplog) -> None:
    caplog.set_level(logging.INFO)
    plan = run_plan_workflow(_request(), sample_store)
    lines = [record.getMessage() for record in caplog.records if "plan_audit" in record.getMessage()]
    assert lines
    payload = json.loads(lines[-1])
    assert payload["event"] == "plan_audit"
    assert payload["request_id"] == plan.request_id
    for field in (
        "selected_role_id",
        "retries",
        "retry_codes",
        "final_error_codes",
        "vector_status",
        "total_time_ms",
    ):
        assert field in payload
