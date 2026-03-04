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


def test_storyboard_fallback_deterministic(monkeypatch, sample_store) -> None:
    monkeypatch.setenv("SANJAYA_ENABLE_LLM_STORYBOARD", "0")
    sample_store.data_version = "storyboard-fallback-v1"
    reset_plan_cache(max_size=256)
    reset_plan_store(max_size=256)
    monkeypatch.setattr(main_module, "load_catalog_store", lambda: sample_store)

    with TestClient(main_module.app) as client:
        plan_res = client.post("/plan", json=_plan_payload())
        assert plan_res.status_code == 200
        plan_id = plan_res.json()["plan_id"]
        storyboard_res = client.post(
            "/plan/storyboard",
            json={"plan_id": plan_id, "tone": "concise", "audience_level": "beginner"},
        )

    assert storyboard_res.status_code == 200
    payload = storyboard_res.json()
    assert payload["plan_id"] == plan_id
    assert payload["llm_status"] == "disabled"
    assert payload["sections"]
    assert any(
        citation["kind"] == "source_id"
        for section in payload["sections"]
        for citation in section.get("citations", [])
    )
