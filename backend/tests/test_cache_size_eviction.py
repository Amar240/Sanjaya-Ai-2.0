from __future__ import annotations

from app.agents.workflow import reset_plan_cache, run_plan_workflow
from app.schemas.plan import PlanRequest, StudentProfile


def _request(current_semester: int) -> PlanRequest:
    return PlanRequest(
        student_profile=StudentProfile(
            level="UG",
            mode="CORE",
            current_semester=current_semester,
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


def test_cache_size_one_evicts_old_entry(monkeypatch, sample_store) -> None:
    sample_store.data_version = "cache-eviction-version"
    monkeypatch.setenv("SANJAYA_PLAN_CACHE_SIZE", "1")
    reset_plan_cache()

    first = run_plan_workflow(_request(1), sample_store)
    second = run_plan_workflow(_request(2), sample_store)
    first_again = run_plan_workflow(_request(1), sample_store)

    assert first.cache_status == "miss"
    assert second.cache_status == "miss"
    assert first_again.cache_status == "miss"
    reset_plan_cache(max_size=256)
