from __future__ import annotations

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


def test_node_timings_include_all_pipeline_nodes(sample_store) -> None:
    plan = run_plan_workflow(_request(), sample_store)
    nodes = {str(item["node"]) for item in plan.node_timings}
    assert {"intake", "role_retrieval", "planner", "verifier", "evidence"}.issubset(nodes)
    for item in plan.node_timings:
        assert int(item["timing_ms"]) >= 0
