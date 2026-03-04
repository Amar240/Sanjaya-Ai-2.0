from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as main_module
from app.agents.workflow import reset_plan_cache
from app.plan_store import reset_plan_store


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


def test_plan_returns_candidate_roles(monkeypatch, sample_store) -> None:
    sample_store.data_version = "candidate-roles-present-v1"
    reset_plan_cache(max_size=256)
    reset_plan_store(max_size=256)
    monkeypatch.setattr(main_module, "load_catalog_store", lambda: sample_store)

    with TestClient(main_module.app) as client:
        response = client.post("/plan", json=_plan_payload())

    assert response.status_code == 200
    payload = response.json()
    candidate_roles = payload.get("candidate_roles", [])
    assert len(candidate_roles) >= 1
    scores = [float(item["score"]) for item in candidate_roles]
    assert scores == sorted(scores, reverse=True)
