from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as main_module
from app.agents.workflow import reset_plan_cache
from app.plan_store import get_plan_store, reset_plan_store


def _plan_payload() -> dict:
    return {
        "student_profile": {
            "level": "UG",
            "mode": "CORE",
            "current_semester": 1,
            "start_term": "Fall",
            "include_optional_terms": False,
            "completed_courses": [],
            "min_credits": 6,
            "target_credits": 6,
            "max_credits": 9,
            "interests": ["test"],
        },
        "preferred_role_id": "ROLE_TEST",
    }


def test_plan_saved_for_advisor_on_cache_hit(monkeypatch, sample_store) -> None:
    sample_store.data_version = "store-hit-v1"
    reset_plan_cache(max_size=256)
    reset_plan_store(max_size=256)
    monkeypatch.setattr(main_module, "load_catalog_store", lambda: sample_store)

    with TestClient(main_module.app) as client:
        first = client.post("/plan", json=_plan_payload())
        second = client.post("/plan", json=_plan_payload())
        assert first.status_code == 200
        assert second.status_code == 200
        payload_1 = first.json()
        payload_2 = second.json()
        assert payload_1["cache_status"] == "miss"
        assert payload_2["cache_status"] == "hit"

        snapshot = get_plan_store().get(payload_2["plan_id"])
        assert snapshot is not None
        assert snapshot.request_id == ""
        assert snapshot.node_timings == []
        assert snapshot.cache_status == "miss"

        advisor = client.post(
            "/advisor/ask",
            json={"question": "Why this role?", "tone": "friendly", "plan_id": payload_2["plan_id"]},
        )

    assert advisor.status_code == 200
    assert advisor.json()["plan_id"] == payload_2["plan_id"]
