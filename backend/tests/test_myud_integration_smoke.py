from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as main_module
from app.agents.workflow import reset_plan_cache
from app.plan_store import reset_plan_store


def test_myud_launch_and_summary(monkeypatch, sample_store) -> None:
    sample_store.data_version = "myud-v1"
    reset_plan_cache(max_size=64)
    reset_plan_store(max_size=64)
    monkeypatch.setattr(main_module, "load_catalog_store", lambda: sample_store)

    payload = {
        "student_id_hash": "abc123hash",
        "major": "Computer and Information Sciences",
        "class_year": 1,
        "current_term": "Fall",
        "completed_courses": [],
        "level": "UG",
        "mode": "CORE",
        "interests": ["software"],
    }

    with TestClient(main_module.app) as client:
        launch = client.post("/integration/myud/launch", json=payload)
        assert launch.status_code == 200
        launch_body = launch.json()
        assert launch_body["plan_id"]
        assert launch_body["selected_role_id"]
        summary = client.get(f"/integration/myud/plan/{launch_body['plan_id']}/summary")
        assert summary.status_code == 200
        summary_body = summary.json()
        assert summary_body["plan_id"] == launch_body["plan_id"]
        assert "coverage_pct" in summary_body
