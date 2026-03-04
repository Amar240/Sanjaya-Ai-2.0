from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as main_module
from app.analytics.events import log_unknown_role_request
from app.analytics.role_requests import upsert_unknown_role_request
from app.curation import roles_drafts
from app.ops import connect


def test_create_role_from_role_request_creates_draft(monkeypatch, sample_store, tmp_path) -> None:
    data_root = tmp_path / "data_root"
    (data_root / "data" / "processed").mkdir(parents=True, exist_ok=True)
    (data_root / "data" / "processed" / "roles_market.json").write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(roles_drafts, "project_root", lambda: data_root)
    monkeypatch.setenv("SANJAYA_ANALYTICS_DIR", str(tmp_path / "analytics"))
    monkeypatch.setenv("SANJAYA_ADMIN_TOKEN", "secret-token")
    monkeypatch.setattr(main_module, "load_catalog_store", lambda: sample_store)

    event = log_unknown_role_request(
        request_id="req-1",
        data_version="v1",
        role_query="AI Policy Architect",
        candidate_roles=[{"role_id": "ROLE_TEST", "score": 0.12}],
        top1_score=0.12,
        plan_id="plan-1",
    )
    request_item = upsert_unknown_role_request(event)
    assert request_item is not None
    request_id = request_item["role_request_id"]

    with TestClient(main_module.app) as client:
        create_res = client.post(
            f"/admin/role-requests/{request_id}/create-role",
            json={},
            headers={"x-admin-token": "secret-token", "x-admin-user": "advisor_1"},
        )
        assert create_res.status_code == 200
        payload = create_res.json()
        draft_id = payload["draft_id"]
        new_role_id = payload["new_role_id"]

        with connect() as conn:
            row = conn.execute(
                """
                SELECT role_origin, created_by, created_at
                FROM draft_roles_calibrated
                WHERE draft_id = ? AND role_id = ?
                """,
                (draft_id, new_role_id),
            ).fetchone()
        assert row is not None
        assert row["role_origin"] == "advisor_added"
        assert row["created_by"] == "advisor_1"
        assert row["created_at"]

        invalid_role = {
            "role_id": "ROLE_BAD",
            "title": "Bad Role",
            "market_grounding": "direct",
            "summary": "bad",
            "required_skills": [{"skill_id": "SK_MISSING", "weight": 3}],
            "evidence_sources": ["SRC_TEST"],
        }
        invalid_res = client.post(
            f"/admin/drafts/{draft_id}/roles",
            json=invalid_role,
            headers={"x-admin-token": "secret-token", "x-admin-user": "advisor_1"},
        )
        assert invalid_res.status_code == 422
