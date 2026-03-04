from __future__ import annotations

import json

import pytest

from app.data_loader import DataValidationError, load_catalog_store


def _write_json(path, payload) -> None:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _seed_base(processed_dir) -> None:
    _write_json(
        processed_dir / "courses.json",
        [
            {
                "course_id": "CISC-101",
                "title": "Intro CS",
                "department": "CISC",
                "level": "UG",
                "credits": 3,
                "description": "Intro",
                "topics": [],
                "prerequisites": [],
                "prerequisites_text": "",
                "corequisites": [],
                "corequisites_text": "",
                "antirequisites": [],
                "antirequisites_text": "",
                "offered_terms": ["Fall"],
                "source_url": "https://example.com/cisc101",
            }
        ],
    )
    _write_json(
        processed_dir / "course_skills.json",
        [{"course_id": "CISC-101", "skill_id": "SK_TEST", "strength": 3}],
    )
    _write_json(
        processed_dir / "roles_market.json",
        [
            {
                "role_id": "ROLE_TEST",
                "title": "Test Role",
                "market_grounding": "direct",
                "source_occupation_codes": [{"system": "TEST", "code": "1"}],
                "summary": "Role",
                "required_skills": [{"skill_id": "SK_TEST", "importance": 4}],
                "evidence_sources": ["SRC_TEST"],
            }
        ],
    )
    _write_json(
        processed_dir / "skills_market.json",
        [
            {
                "skill_id": "SK_TEST",
                "name": "Test",
                "aliases": [],
                "category": "Programming",
                "source_refs": ["SRC_TEST"],
            }
        ],
    )
    _write_json(
        processed_dir / "role_skill_evidence.json",
        [
            {
                "role_id": "ROLE_TEST",
                "skill_id": "SK_TEST",
                "confidence": 0.9,
                "evidence_sources": ["SRC_TEST"],
                "evidence_note": "Test evidence",
            }
        ],
    )
    _write_json(
        processed_dir / "market_sources.json",
        [
            {
                "source_id": "SRC_TEST",
                "provider": "Provider",
                "type": "report",
                "title": "Source",
                "url": "https://example.com/source",
                "retrieved_on": "2026-01-01",
            }
        ],
    )


def test_invalid_role_reality_references_fail_startup(tmp_path) -> None:
    _seed_base(tmp_path)
    _write_json(
        tmp_path / "role_reality_usa.json",
        [
            {
                "role_id": "ROLE_MISSING",
                "role_title": "Missing",
                "typical_tasks": ["x"],
                "salary_usd": {"p25": 1, "median": 2, "p75": 3},
                "sources": ["SRC_TEST"],
                "last_updated": "2026-01-01",
            }
        ],
    )
    _write_json(
        tmp_path / "project_templates.json",
        [
            {
                "template_id": "PT1",
                "skill_id": "SK_TEST",
                "level": "beginner",
                "title": "t",
                "time_hours": 2,
                "deliverables": ["d"],
                "rubric": ["r"],
                "links": [],
            }
        ],
    )
    with pytest.raises(DataValidationError):
        load_catalog_store(data_dir=tmp_path)


def test_invalid_project_template_skill_fails_startup(tmp_path) -> None:
    _seed_base(tmp_path)
    _write_json(
        tmp_path / "role_reality_usa.json",
        [
            {
                "role_id": "ROLE_TEST",
                "role_title": "Test Role",
                "typical_tasks": ["x"],
                "salary_usd": {"p25": 1, "median": 2, "p75": 3},
                "sources": ["SRC_TEST"],
                "last_updated": "2026-01-01",
            }
        ],
    )
    _write_json(
        tmp_path / "project_templates.json",
        [
            {
                "template_id": "PT_BAD",
                "skill_id": "SK_MISSING",
                "level": "beginner",
                "title": "bad",
                "time_hours": 2,
                "deliverables": ["d"],
                "rubric": ["r"],
                "links": [],
            }
        ],
    )
    with pytest.raises(DataValidationError):
        load_catalog_store(data_dir=tmp_path)


def test_invalid_role_reality_source_fails_startup(tmp_path) -> None:
    _seed_base(tmp_path)
    _write_json(
        tmp_path / "role_reality_usa.json",
        [
            {
                "role_id": "ROLE_TEST",
                "role_title": "Test Role",
                "typical_tasks": ["x"],
                "salary_usd": {"p25": 1, "median": 2, "p75": 3},
                "sources": ["SRC_MISSING"],
                "last_updated": "2026-01-01",
            }
        ],
    )
    _write_json(
        tmp_path / "project_templates.json",
        [
            {
                "template_id": "PT1",
                "skill_id": "SK_TEST",
                "level": "beginner",
                "title": "t",
                "time_hours": 2,
                "deliverables": ["d"],
                "rubric": ["r"],
                "links": [],
            }
        ],
    )
    with pytest.raises(DataValidationError):
        load_catalog_store(data_dir=tmp_path)
