from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app import main as main_module
from app.curation import roles_drafts


def _seed_processed(root, *, include_reality: bool) -> None:
    processed = root / "data" / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    (processed / "course_skills_curated.json").write_text("[]\n", encoding="utf-8")
    (processed / "market_sources.json").write_text(
        json.dumps(
            [
                {
                    "source_id": "SRC_TEST",
                    "provider": "Test Provider",
                    "type": "report",
                    "title": "Test Source",
                    "url": "https://example.com/source",
                    "retrieved_on": "2026-01-01",
                    "enabled": 1,
                    "trust_weight": 0.85,
                }
            ]
        ),
        encoding="utf-8",
    )
    (processed / "project_templates.json").write_text(
        json.dumps(
            [
                {
                    "template_id": "PT_SK_TEST_1",
                    "skill_id": "SK_TEST",
                    "level": "beginner",
                    "title": "Test Project",
                    "time_hours": 4,
                    "prerequisites": [],
                    "deliverables": ["demo"],
                    "rubric": ["clear"],
                    "links": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    (processed / "roles_market.json").write_text(
        json.dumps(
            [
                {
                    "role_id": "ROLE_TEST",
                    "title": "Test Role",
                    "market_grounding": "direct",
                    "source_occupation_codes": [],
                    "summary": "Test summary",
                    "required_skills": [{"skill_id": "SK_TEST", "importance": 4}],
                    "evidence_sources": ["SRC_TEST"],
                    "department_owner": "CIS",
                    "country_scope": "USA",
                    "demo_tier": "core",
                    "reality_complete": False,
                    "project_coverage_complete": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    reality_rows = [
        {
            "role_id": "ROLE_TEST",
            "role_title": "Test Role",
            "typical_tasks": ["Task"],
            "salary_usd": {"p25": 1, "median": 2, "p75": 3},
            "sources": ["SRC_TEST"],
            "last_updated": "2026-01-01",
        }
    ] if include_reality else []
    (processed / "role_reality_usa.json").write_text(
        json.dumps(reality_rows),
        encoding="utf-8",
    )


def test_publish_requires_central_reviewer(monkeypatch, sample_store, tmp_path) -> None:
    data_root = tmp_path / "data_root"
    _seed_processed(data_root, include_reality=True)
    monkeypatch.setattr(roles_drafts, "project_root", lambda: data_root)
    monkeypatch.setenv("SANJAYA_ADMIN_TOKEN", "secret-token")
    monkeypatch.setenv("SANJAYA_CENTRAL_REVIEWERS", "reviewer_1")
    monkeypatch.setattr(main_module, "load_catalog_store", lambda: sample_store)

    with TestClient(main_module.app) as client:
        draft_res = client.post("/admin/drafts", headers={"x-admin-token": "secret-token", "x-admin-user": "advisor_1"})
        assert draft_res.status_code == 200
        draft_id = draft_res.json()["draft_id"]
        publish_res = client.post(
            f"/admin/drafts/{draft_id}/publish",
            headers={"x-admin-token": "secret-token", "x-admin-user": "advisor_1"},
        )
        assert publish_res.status_code == 403


def test_publish_gate_blocks_when_reality_missing(monkeypatch, sample_store, tmp_path) -> None:
    data_root = tmp_path / "data_root"
    _seed_processed(data_root, include_reality=False)
    monkeypatch.setattr(roles_drafts, "project_root", lambda: data_root)
    monkeypatch.setenv("SANJAYA_ADMIN_TOKEN", "secret-token")
    monkeypatch.setenv("SANJAYA_CENTRAL_REVIEWERS", "reviewer_1")
    monkeypatch.setattr(main_module, "load_catalog_store", lambda: sample_store)

    with TestClient(main_module.app) as client:
        draft_res = client.post("/admin/drafts", headers={"x-admin-token": "secret-token", "x-admin-user": "advisor_1"})
        assert draft_res.status_code == 200
        draft_id = draft_res.json()["draft_id"]
        publish_res = client.post(
            f"/admin/drafts/{draft_id}/publish",
            headers={"x-admin-token": "secret-token", "x-admin-user": "reviewer_1"},
        )
        assert publish_res.status_code == 422
        assert "readiness gates" in str(publish_res.json()).lower()
