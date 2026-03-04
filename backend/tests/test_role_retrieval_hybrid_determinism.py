from __future__ import annotations

from app.data_loader import CatalogStore
from app.rag import evidence_retriever
from app.schemas.catalog import (
    Course,
    CourseSkillMapping,
    RoleMarket,
    RoleSkillEvidence,
    SkillMarket,
    SourceReference,
)


def _course(course_id: str) -> Course:
    return Course.model_validate(
        {
            "course_id": course_id,
            "title": course_id,
            "department": "CISC",
            "level": "UG",
            "credits": 3,
            "description": "course",
            "topics": [],
            "prerequisites": [],
            "prerequisites_text": "",
            "corequisites": [],
            "corequisites_text": "",
            "antirequisites": [],
            "antirequisites_text": "",
            "offered_terms": ["Fall", "Spring"],
            "source_url": "https://example.com/course",
        }
    )


def _store() -> CatalogStore:
    roles = [
        RoleMarket.model_validate(
            {
                "role_id": "ROLE_DATA_ENGINEER",
                "title": "Data Engineer",
                "market_grounding": "direct",
                "source_occupation_codes": [{"system": "TEST", "code": "1"}],
                "summary": "Builds analytics and pipeline systems",
                "required_skills": [{"skill_id": "SK_PYTHON", "importance": 5}],
                "evidence_sources": ["SRC_BLS"],
            }
        ),
        RoleMarket.model_validate(
            {
                "role_id": "ROLE_BUSINESS_ANALYST",
                "title": "Business Analyst",
                "market_grounding": "direct",
                "source_occupation_codes": [{"system": "TEST", "code": "2"}],
                "summary": "Focuses on business requirements and reporting",
                "required_skills": [{"skill_id": "SK_ANALYSIS", "importance": 4}],
                "evidence_sources": ["SRC_BLS"],
            }
        ),
        RoleMarket.model_validate(
            {
                "role_id": "ROLE_STATISTICIAN",
                "title": "Statistician",
                "market_grounding": "direct",
                "source_occupation_codes": [{"system": "TEST", "code": "3"}],
                "summary": "Statistical modeling and experiments",
                "required_skills": [{"skill_id": "SK_STATS", "importance": 4}],
                "evidence_sources": ["SRC_BLS"],
            }
        ),
    ]
    skills = [
        SkillMarket.model_validate(
            {
                "skill_id": "SK_PYTHON",
                "name": "Python",
                "aliases": [],
                "category": "Programming",
                "source_refs": ["SRC_BLS"],
            }
        ),
        SkillMarket.model_validate(
            {
                "skill_id": "SK_ANALYSIS",
                "name": "Analysis",
                "aliases": [],
                "category": "Analytics",
                "source_refs": ["SRC_BLS"],
            }
        ),
        SkillMarket.model_validate(
            {
                "skill_id": "SK_STATS",
                "name": "Statistics",
                "aliases": [],
                "category": "Math",
                "source_refs": ["SRC_BLS"],
            }
        ),
    ]
    source = SourceReference.model_validate(
        {
            "source_id": "SRC_BLS",
            "provider": "BLS",
            "type": "report",
            "title": "BLS Source",
            "url": "https://example.com/source",
            "retrieved_on": "2026-01-01",
        }
    )
    evidence = [
        RoleSkillEvidence.model_validate(
            {
                "role_id": "ROLE_DATA_ENGINEER",
                "skill_id": "SK_PYTHON",
                "confidence": 0.9,
                "evidence_sources": ["SRC_BLS"],
                "evidence_note": "Data engineer roles require python pipeline skills.",
            }
        )
    ]
    courses = [_course("CISC-101")]
    mappings = [
        CourseSkillMapping.model_validate(
            {"course_id": "CISC-101", "skill_id": "SK_PYTHON", "strength": 4}
        )
    ]
    return CatalogStore(
        courses=courses,
        course_skills=mappings,
        curated_role_skill_courses=[],
        fusion_role_profiles=[],
        roles=roles,
        roles_source_file="roles_market.json",
        skills=skills,
        evidence_links=evidence,
        sources=[source],
        warnings=[],
        data_version="test-v1",
    )


def test_role_retrieval_hybrid_deterministic(monkeypatch) -> None:
    monkeypatch.setattr(evidence_retriever, "CHROMA_AVAILABLE", False)
    retriever = evidence_retriever.MarketEvidenceRetriever(_store(), persist_dir=None)
    first = retriever.retrieve_roles_by_interest(["python", "pipeline", "analytics"], top_k=3)
    second = retriever.retrieve_roles_by_interest(["python", "pipeline", "analytics"], top_k=3)
    assert first == second
    diagnostics = retriever.get_last_role_diagnostics()
    assert diagnostics.get("top")
