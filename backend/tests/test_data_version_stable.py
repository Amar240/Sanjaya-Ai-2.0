from __future__ import annotations

import json

from app.data_loader import load_catalog_store


def _write_json(path, payload) -> None:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _seed_processed_dir(processed_dir) -> None:
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
    _write_json(
        processed_dir / "role_reality_usa.json",
        [
            {
                "role_id": "ROLE_TEST",
                "role_title": "Test Role",
                "typical_tasks": ["Task A"],
                "salary_usd": {"p25": 50000, "median": 70000, "p75": 90000},
                "sources": ["SRC_TEST"],
                "last_updated": "2026-01-01",
            }
        ],
    )
    _write_json(
        processed_dir / "project_templates.json",
        [
            {
                "template_id": "PT_TEST_1",
                "skill_id": "SK_TEST",
                "level": "beginner",
                "title": "Template",
                "time_hours": 4,
                "prerequisites": [],
                "deliverables": ["demo"],
                "rubric": ["clear"],
                "links": [],
                "notes": None,
            }
        ],
    )


def test_data_version_stable_and_changes_on_file_update(tmp_path) -> None:
    _seed_processed_dir(tmp_path)

    first = load_catalog_store(data_dir=tmp_path)
    second = load_catalog_store(data_dir=tmp_path)
    assert first.data_version == second.data_version

    courses_path = tmp_path / "courses.json"
    payload = json.loads(courses_path.read_text(encoding="utf-8"))
    payload[0]["title"] = "Intro CS Updated"
    _write_json(courses_path, payload)

    third = load_catalog_store(data_dir=tmp_path)
    assert third.data_version != first.data_version
