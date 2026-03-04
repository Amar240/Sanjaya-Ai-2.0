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


def test_debug_flag_controls_retrieval_trace(monkeypatch, sample_store) -> None:
    sample_store.data_version = "trace-debug-v1"
    monkeypatch.delenv("SANJAYA_RETRIEVAL_DEBUG", raising=False)
    reset_plan_cache(max_size=256)
    normal = run_plan_workflow(_request(), sample_store)
    assert not any("retrieval_debug:" in line for line in normal.agent_trace)

    monkeypatch.setenv("SANJAYA_RETRIEVAL_DEBUG", "1")
    sample_store.data_version = "trace-debug-v2"
    reset_plan_cache(max_size=256)
    debug = run_plan_workflow(_request(), sample_store)
    assert any("retrieval_debug:" in line for line in debug.agent_trace)
