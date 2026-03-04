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
    role = RoleMarket.model_validate(
        {
            "role_id": "ROLE_TEST",
            "title": "Test Role",
            "market_grounding": "direct",
            "source_occupation_codes": [{"system": "TEST", "code": "1"}],
            "summary": "Role summary",
            "required_skills": [{"skill_id": "SK_TEST", "importance": 5}],
            "evidence_sources": ["SRC_BLS", "SRC_UNK"],
        }
    )
    skill = SkillMarket.model_validate(
        {
            "skill_id": "SK_TEST",
            "name": "Test Skill",
            "aliases": [],
            "category": "Programming",
            "source_refs": ["SRC_BLS", "SRC_UNK"],
        }
    )
    sources = [
        SourceReference.model_validate(
            {
                "source_id": "SRC_BLS",
                "provider": "BLS",
                "type": "report",
                "title": "BLS Report",
                "url": "https://example.com/bls",
                "retrieved_on": "2026-01-01",
            }
        ),
        SourceReference.model_validate(
            {
                "source_id": "SRC_UNK",
                "provider": "Unknown Provider",
                "type": "report",
                "title": "Unknown Report",
                "url": "https://example.com/unknown",
                "retrieved_on": "2026-01-01",
            }
        ),
    ]
    evidence = [
        RoleSkillEvidence.model_validate(
            {
                "role_id": "ROLE_TEST",
                "skill_id": "SK_TEST",
                "confidence": 0.9,
                "evidence_sources": ["SRC_BLS"],
                "evidence_note": "Python analytics demand is strong.",
            }
        ),
        RoleSkillEvidence.model_validate(
            {
                "role_id": "ROLE_TEST",
                "skill_id": "SK_TEST",
                "confidence": 0.9,
                "evidence_sources": ["SRC_UNK"],
                "evidence_note": "Python analytics demand is strong!",
            }
        ),
    ]
    return CatalogStore(
        courses=[_course("CISC-101")],
        course_skills=[
            CourseSkillMapping.model_validate(
                {"course_id": "CISC-101", "skill_id": "SK_TEST", "strength": 3}
            )
        ],
        curated_role_skill_courses=[],
        fusion_role_profiles=[],
        roles=[role],
        roles_source_file="roles_market.json",
        skills=[skill],
        evidence_links=evidence,
        sources=sources,
        warnings=[],
        data_version="test-v1",
    )


def test_evidence_trust_weight_prioritizes_bls(monkeypatch) -> None:
    monkeypatch.setattr(evidence_retriever, "CHROMA_AVAILABLE", False)
    retriever = evidence_retriever.MarketEvidenceRetriever(_store(), persist_dir=None)
    panel = retriever.retrieve_role_evidence(retriever.store.roles[0], top_k=2)
    assert panel
    assert panel[0].source_provider == "BLS"
