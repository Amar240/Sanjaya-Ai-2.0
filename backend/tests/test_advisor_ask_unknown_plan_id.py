from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as main_module
from app.plan_store import reset_plan_store


def test_advisor_ask_unknown_plan_id_returns_404(monkeypatch, sample_store) -> None:
    reset_plan_store(max_size=256)
    monkeypatch.setattr(main_module, "load_catalog_store", lambda: sample_store)

    with TestClient(main_module.app) as client:
        response = client.post(
            "/advisor/ask",
            json={
                "question": "Why this role?",
                "tone": "friendly",
                "plan_id": "missing-plan-id",
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown plan_id"
