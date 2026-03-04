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


def _diverse_store() -> CatalogStore:
    courses = [_course("CISC-101")]
    skills = [
        SkillMarket.model_validate(
            {
                "skill_id": "SK_TEST",
                "name": "Testing Skill",
                "aliases": [],
                "category": "Programming",
                "source_refs": ["SRC_A1", "SRC_B1"],
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
                "summary": "Role summary",
                "required_skills": [{"skill_id": "SK_TEST", "importance": 5}],
                "evidence_sources": ["SRC_A1", "SRC_B1"],
            }
        )
    ]
    sources = [
        SourceReference.model_validate(
            {
                "source_id": "SRC_A1",
                "provider": "Provider A",
                "type": "report",
                "title": "Source A1",
                "url": "https://example.com/a1",
                "retrieved_on": "2026-01-01",
            }
        ),
        SourceReference.model_validate(
            {
                "source_id": "SRC_A2",
                "provider": "Provider A",
                "type": "report",
                "title": "Source A2",
                "url": "https://example.com/a2",
                "retrieved_on": "2026-01-01",
            }
        ),
        SourceReference.model_validate(
            {
                "source_id": "SRC_A3",
                "provider": "Provider A",
                "type": "report",
                "title": "Source A3",
                "url": "https://example.com/a3",
                "retrieved_on": "2026-01-01",
            }
        ),
        SourceReference.model_validate(
            {
                "source_id": "SRC_A4",
                "provider": "Provider A",
                "type": "report",
                "title": "Source A4",
                "url": "https://example.com/a4",
                "retrieved_on": "2026-01-01",
            }
        ),
        SourceReference.model_validate(
            {
                "source_id": "SRC_B1",
                "provider": "Provider B",
                "type": "report",
                "title": "Source B1",
                "url": "https://example.com/b1",
                "retrieved_on": "2026-01-01",
            }
        ),
    ]
    evidence = [
        RoleSkillEvidence.model_validate(
            {
                "role_id": "ROLE_TEST",
                "skill_id": "SK_TEST",
                "confidence": 0.95,
                "evidence_sources": ["SRC_A1"],
                "evidence_note": "A one",
            }
        ),
        RoleSkillEvidence.model_validate(
            {
                "role_id": "ROLE_TEST",
                "skill_id": "SK_TEST",
                "confidence": 0.94,
                "evidence_sources": ["SRC_A2"],
                "evidence_note": "A two",
            }
        ),
        RoleSkillEvidence.model_validate(
            {
                "role_id": "ROLE_TEST",
                "skill_id": "SK_TEST",
                "confidence": 0.93,
                "evidence_sources": ["SRC_A3"],
                "evidence_note": "A three",
            }
        ),
        RoleSkillEvidence.model_validate(
            {
                "role_id": "ROLE_TEST",
                "skill_id": "SK_TEST",
                "confidence": 0.92,
                "evidence_sources": ["SRC_A4"],
                "evidence_note": "A four",
            }
        ),
        RoleSkillEvidence.model_validate(
            {
                "role_id": "ROLE_TEST",
                "skill_id": "SK_TEST",
                "confidence": 0.10,
                "evidence_sources": ["SRC_B1"],
                "evidence_note": "B one",
            }
        ),
    ]
    return CatalogStore(
        courses=courses,
        course_skills=[
            CourseSkillMapping.model_validate(
                {"course_id": "CISC-101", "skill_id": "SK_TEST", "strength": 3}
            )
        ],
        curated_role_skill_courses=[],
        fusion_role_profiles=[],
        roles=roles,
        roles_source_file="roles_market.json",
        skills=skills,
        evidence_links=evidence,
        sources=sources,
        warnings=[],
    )


def test_evidence_source_diversity(monkeypatch) -> None:
    monkeypatch.setattr(evidence_retriever, "CHROMA_AVAILABLE", False)
    store = _diverse_store()
    retriever = evidence_retriever.MarketEvidenceRetriever(store, persist_dir=None)
    panel = retriever.retrieve_role_evidence(store.roles[0], top_k=4)
    providers = {item.source_provider for item in panel}
    assert len(providers) >= 2
