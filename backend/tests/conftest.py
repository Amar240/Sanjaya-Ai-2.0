from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data_loader import CatalogStore
from app.ops import reset_db_state
from app.schemas.catalog import (
    Course,
    CourseSkillMapping,
    RoleMarket,
    RoleSkillEvidence,
    SkillMarket,
    SourceReference,
)
from app.schemas.reality import ProjectTemplate, RoleRealityUSA


def _course(
    course_id: str,
    *,
    title: str,
    level: str = "UG",
    prerequisites: list[str] | None = None,
    offered_terms: list[str] | None = None,
) -> Course:
    return Course.model_validate(
        {
            "course_id": course_id,
            "title": title,
            "department": "CISC",
            "level": level,
            "credits": 3,
            "description": f"{title} description",
            "topics": [],
            "prerequisites": prerequisites or [],
            "prerequisites_text": "",
            "corequisites": [],
            "corequisites_text": "",
            "antirequisites": [],
            "antirequisites_text": "",
            "offered_terms": offered_terms or ["Fall", "Spring"],
            "source_url": "https://example.com/course",
        }
    )


@pytest.fixture
def sample_store() -> CatalogStore:
    courses = [
        _course("CISC-101", title="Intro CS"),
        _course("CISC-201", title="Data Structures", prerequisites=["CISC-101"]),
    ]
    skills = [
        SkillMarket.model_validate(
            {
                "skill_id": "SK_TEST",
                "name": "Test Skill",
                "aliases": [],
                "category": "Programming",
                "source_refs": ["SRC_TEST"],
            }
        )
    ]
    roles = [
        RoleMarket.model_validate(
            {
                "role_id": "ROLE_TEST",
                "title": "Test Role",
                "market_grounding": "direct",
                "source_occupation_codes": [{"system": "TEST", "code": "T-1"}],
                "summary": "Testing role",
                "required_skills": [{"skill_id": "SK_TEST", "importance": 4}],
                "evidence_sources": ["SRC_TEST"],
            }
        )
    ]
    sources = [
        SourceReference.model_validate(
            {
                "source_id": "SRC_TEST",
                "provider": "Test Provider",
                "type": "report",
                "title": "Test Source",
                "url": "https://example.com/source",
                "retrieved_on": "2026-01-01",
            }
        )
    ]
    evidence = [
        RoleSkillEvidence.model_validate(
            {
                "role_id": "ROLE_TEST",
                "skill_id": "SK_TEST",
                "confidence": 0.9,
                "evidence_sources": ["SRC_TEST"],
                "evidence_note": "Test evidence snippet.",
            }
        )
    ]
    course_skills = [
        CourseSkillMapping.model_validate(
            {"course_id": "CISC-201", "skill_id": "SK_TEST", "strength": 4}
        )
    ]
    return CatalogStore(
        courses=courses,
        course_skills=course_skills,
        curated_role_skill_courses=[],
        fusion_role_profiles=[],
        roles=roles,
        roles_source_file="roles_market.json",
        skills=skills,
        evidence_links=evidence,
        sources=sources,
        role_reality_usa=[
            RoleRealityUSA.model_validate(
                {
                    "role_id": "ROLE_TEST",
                    "role_title": "Test Role",
                    "typical_tasks": ["Design small systems", "Review data pipelines"],
                    "salary_usd": {"p25": 70000, "median": 90000, "p75": 120000},
                    "sources": ["SRC_TEST"],
                    "last_updated": "2026-01-15",
                }
            )
        ],
        project_templates=[
            ProjectTemplate.model_validate(
                {
                    "template_id": "PT_SK_TEST_1",
                    "skill_id": "SK_TEST",
                    "level": "beginner",
                    "title": "Test Skill Project",
                    "time_hours": 10,
                    "deliverables": ["Repo with README"],
                    "rubric": ["Clear scope", "Working demo"],
                    "links": [],
                }
            )
        ],
        warnings=[],
    )


@pytest.fixture(autouse=True)
def _ops_db_isolation(monkeypatch, tmp_path):
    db_path = tmp_path / "ops" / "sanjaya_ops.db"
    monkeypatch.setenv("SANJAYA_OPS_DB_PATH", str(db_path))
    reset_db_state()
    yield
    reset_db_state()
