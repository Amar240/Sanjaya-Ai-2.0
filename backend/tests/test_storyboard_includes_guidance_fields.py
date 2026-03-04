from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as main_module
from app.agents.workflow import reset_plan_cache
from app.plan_store import get_plan_store, reset_plan_store
from app.schemas.plan import PlanResponse


def _plan_payload() -> dict:
    return {
        "student_profile": {
            "level": "UG",
            "mode": "CORE",
            "goal_type": "explore",
            "confidence_level": "low",
            "hours_per_week": 5,
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


def test_storyboard_includes_guidance_fields(monkeypatch, sample_store) -> None:
    monkeypatch.setenv("SANJAYA_ENABLE_LLM_STORYBOARD", "0")
    sample_store.data_version = "storyboard-guidance-v1"
    reset_plan_cache(max_size=256)
    reset_plan_store(max_size=256)
    monkeypatch.setattr(main_module, "load_catalog_store", lambda: sample_store)

    with TestClient(main_module.app) as client:
        plan_res = client.post("/plan", json=_plan_payload())
        assert plan_res.status_code == 200
        plan_id = plan_res.json()["plan_id"]
        storyboard_res = client.post(
            "/plan/storyboard",
            json={"plan_id": plan_id, "tone": "friendly", "audience_level": "beginner"},
        )
    assert storyboard_res.status_code == 200
    payload = storyboard_res.json()
    bodies = " ".join(section["body"] for section in payload["sections"])
    assert "Plan assumes ~5 hours/week for projects." in bodies
    assert "beginner-friendly steps" in bodies
    assert "You're exploring - here are 3 strong paths" in bodies


def test_storyboard_intake_snapshot_backward_compat(monkeypatch, sample_store) -> None:
    monkeypatch.setenv("SANJAYA_ENABLE_LLM_STORYBOARD", "0")
    reset_plan_store(max_size=256)
    reset_plan_cache(max_size=256)
    monkeypatch.setattr(main_module, "load_catalog_store", lambda: sample_store)

    legacy_plan = PlanResponse(
        plan_id="legacy-plan-1",
        selected_role_id="ROLE_TEST",
        selected_role_title="Test Role",
        skill_coverage=[],
        semesters=[],
        intake_snapshot=None,
    )
    get_plan_store().put("legacy-plan-1", legacy_plan)

    with TestClient(main_module.app) as client:
        storyboard_res = client.post(
            "/plan/storyboard",
            json={"plan_id": "legacy-plan-1", "tone": "concise", "audience_level": "intermediate"},
        )
    assert storyboard_res.status_code == 200
    payload = storyboard_res.json()
    bodies = " ".join(section["body"] for section in payload["sections"])
    assert "Plan assumes ~6 hours/week for projects." in bodies
