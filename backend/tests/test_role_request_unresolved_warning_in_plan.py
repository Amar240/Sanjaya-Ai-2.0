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
            "interests": [],
        },
        "preferred_role_id": "ROLE_TEST",
        "requested_role_text": "very niche unknown role phrase",
    }


def test_role_request_unresolved_warning_in_plan(monkeypatch, sample_store, tmp_path) -> None:
    monkeypatch.setenv("SANJAYA_ANALYTICS_DIR", str(tmp_path))
    monkeypatch.setenv("SANJAYA_ROLE_MATCH_MIN_SCORE", "1.0")
    sample_store.data_version = "role-request-warning-v1"
    reset_plan_cache(max_size=256)
    reset_plan_store(max_size=256)
    monkeypatch.setattr(main_module, "load_catalog_store", lambda: sample_store)

    with TestClient(main_module.app) as client:
        res = client.post("/plan", json=_plan_payload())

    assert res.status_code == 200
    payload = res.json()
    warning = next(
        (item for item in payload["validation_errors"] if item["code"] == "ROLE_REQUEST_UNRESOLVED"),
        None,
    )
    assert warning is not None
    assert warning["details"]["severity"] == "warning"
