from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as main_module


def test_draft_readiness_endpoint_auth(monkeypatch, sample_store) -> None:
    monkeypatch.setenv("SANJAYA_ADMIN_TOKEN", "secret-token")
    monkeypatch.setattr(main_module, "load_catalog_store", lambda: sample_store)

    with TestClient(main_module.app) as client:
        create = client.post("/admin/drafts", headers={"x-admin-token": "secret-token"})
        assert create.status_code == 200
        draft_id = create.json()["draft_id"]

        unauthorized = client.get(f"/admin/drafts/{draft_id}/roles/readiness")
        assert unauthorized.status_code == 401

        authorized = client.get(
            f"/admin/drafts/{draft_id}/roles/readiness",
            headers={"x-admin-token": "secret-token"},
        )
        assert authorized.status_code == 200
        payload = authorized.json()
        assert "items" in payload
