from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as main_module


def test_admin_role_requests_endpoints_require_auth(monkeypatch, sample_store) -> None:
    monkeypatch.setenv("SANJAYA_ADMIN_TOKEN", "secret-token")
    monkeypatch.setattr(main_module, "load_catalog_store", lambda: sample_store)

    with TestClient(main_module.app) as client:
        res = client.get("/admin/role-requests")
        assert res.status_code == 401

        authorized = client.get(
            "/admin/role-requests",
            headers={"x-admin-token": "secret-token"},
        )
        assert authorized.status_code == 200
