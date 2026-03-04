from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as main_module
from app.agents import workflow


def _request_payload() -> dict:
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


def _core_signature(plan_payload: dict) -> dict:
    return {
        "selected_role_id": plan_payload["selected_role_id"],
        "semesters": plan_payload["semesters"],
        "skill_coverage": plan_payload["skill_coverage"],
        "evidence_ids": [item["evidence_id"] for item in plan_payload["evidence_panel"]],
    }


def test_plan_cache_miss_then_hit(monkeypatch, sample_store) -> None:
    sample_store.data_version = "cache-version"
    workflow.reset_plan_cache(max_size=256)
    monkeypatch.setattr(main_module, "load_catalog_store", lambda: sample_store)

    with TestClient(main_module.app) as client:
        first = client.post("/plan", json=_request_payload())
        second = client.post("/plan", json=_request_payload())

    assert first.status_code == 200
    assert second.status_code == 200
    payload_a = first.json()
    payload_b = second.json()

    assert payload_a["cache_status"] == "miss"
    assert payload_b["cache_status"] == "hit"
    assert payload_a["plan_id"] == payload_b["plan_id"]
    assert payload_a["request_id"] != payload_b["request_id"]
    assert payload_a["node_timings"]
    assert payload_b["node_timings"]
    assert _core_signature(payload_a) == _core_signature(payload_b)
    workflow.reset_plan_cache(max_size=256)
