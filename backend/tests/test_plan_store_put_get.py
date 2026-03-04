from __future__ import annotations

from app.plan_store import PlanStore
from app.schemas.plan import PlanResponse


def _plan(plan_id: str) -> PlanResponse:
    return PlanResponse(
        request_id="req-123",
        plan_id=plan_id,
        cache_status="hit",
        data_version="v1",
        selected_role_id="ROLE_TEST",
        selected_role_title="Test Role",
        node_timings=[{"node": "planner", "timing_ms": 5}],
        agent_trace=["request_id:req-123", "planner: done"],
    )


def test_plan_store_lru_put_get_eviction() -> None:
    store = PlanStore(max_size=1)
    store.put("plan-a", _plan("plan-a"))
    assert store.get("plan-a") is not None

    store.put("plan-b", _plan("plan-b"))
    assert store.get("plan-a") is None
    saved = store.get("plan-b")
    assert saved is not None
    assert saved.request_id == ""
    assert saved.node_timings == []
    assert saved.cache_status == "miss"
    assert saved.agent_trace == ["planner: done"]
    stats = store.stats()
    assert stats["count"] == 1
    assert stats["max_size"] == 1
    assert stats["evictions"] == 1
