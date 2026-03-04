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


def test_advisor_ask_uses_plan_id(monkeypatch, sample_store) -> None:
    sample_store.data_version = "plan-id-test-v1"
    reset_plan_cache(max_size=256)
    reset_plan_store(max_size=256)
    monkeypatch.setattr(main_module, "load_catalog_store", lambda: sample_store)

    with TestClient(main_module.app) as client:
        plan_res = client.post("/plan", json=_plan_payload())
        assert plan_res.status_code == 200
        plan_payload = plan_res.json()

        advisor_res = client.post(
            "/advisor/ask",
            json={
                "question": "Why this role for me?",
                "tone": "friendly",
                "plan_id": plan_payload["plan_id"],
            },
        )

    assert advisor_res.status_code == 200
    advisor_payload = advisor_res.json()
    assert advisor_payload["plan_id"] == plan_payload["plan_id"]
    evidence_ids = {item["evidence_id"] for item in plan_payload["evidence_panel"]}
    course_ids = {cid for sem in plan_payload["semesters"] for cid in sem["courses"]}
    skill_ids = {item["required_skill_id"] for item in plan_payload["skill_coverage"]}
    for citation in advisor_payload["citations"]:
        if citation.get("evidence_id"):
            assert citation["evidence_id"] in evidence_ids
        if citation.get("course_id"):
            assert citation["course_id"] in course_ids
        if citation.get("skill_id"):
            assert citation["skill_id"] in skill_ids
