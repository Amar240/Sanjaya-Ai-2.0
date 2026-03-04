from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as main_module
from app.agents.workflow import reset_plan_cache
from app.plan_store import reset_plan_store


def _payload() -> dict:
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
            "interests": ["testing"],
        },
        "preferred_role_id": "ROLE_TEST",
    }


def test_readiness_summary_deterministic(monkeypatch, sample_store) -> None:
    sample_store.data_version = "readiness-v1"
    reset_plan_cache(max_size=64)
    reset_plan_store(max_size=64)
    monkeypatch.setattr(main_module, "load_catalog_store", lambda: sample_store)

    with TestClient(main_module.app) as client:
        first = client.post("/plan", json=_payload())
        second = client.post("/plan", json=_payload())

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert first_body["readiness_summary"] is not None
    assert second_body["readiness_summary"] is not None
    assert first_body["readiness_summary"] == second_body["readiness_summary"]
    assert first_body["department_context"] == second_body["department_context"]
