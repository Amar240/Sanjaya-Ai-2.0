from __future__ import annotations

import re

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


def _store_with_duplicate_snippets() -> CatalogStore:
    courses = [_course("CISC-101")]
    skills = [
        SkillMarket.model_validate(
            {
                "skill_id": "SK_TEST",
                "name": "Testing Skill",
                "aliases": [],
                "category": "Programming",
                "source_refs": ["SRC_A", "SRC_B"],
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
                "evidence_sources": ["SRC_A", "SRC_B"],
            }
        )
    ]
    sources = [
        SourceReference.model_validate(
            {
                "source_id": "SRC_A",
                "provider": "Provider A",
                "type": "report",
                "title": "Source A",
                "url": "https://example.com/a",
                "retrieved_on": "2026-01-01",
            }
        ),
        SourceReference.model_validate(
            {
                "source_id": "SRC_B",
                "provider": "Provider B",
                "type": "report",
                "title": "Source B",
                "url": "https://example.com/b",
                "retrieved_on": "2026-01-01",
            }
        ),
    ]
    evidence = [
        RoleSkillEvidence.model_validate(
            {
                "role_id": "ROLE_TEST",
                "skill_id": "SK_TEST",
                "confidence": 0.90,
                "evidence_sources": ["SRC_A"],
                "evidence_note": "Same snippet text",
            }
        ),
        RoleSkillEvidence.model_validate(
            {
                "role_id": "ROLE_TEST",
                "skill_id": "SK_TEST",
                "confidence": 0.70,
                "evidence_sources": ["SRC_B"],
                "evidence_note": "  same   snippet   text ",
            }
        ),
        RoleSkillEvidence.model_validate(
            {
                "role_id": "ROLE_TEST",
                "skill_id": "SK_TEST",
                "confidence": 0.80,
                "evidence_sources": ["SRC_B"],
                "evidence_note": "Different snippet text",
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


def test_evidence_ids_are_present_unique_and_snippet_dedup(monkeypatch) -> None:
    monkeypatch.setattr(evidence_retriever, "CHROMA_AVAILABLE", False)
    store = _store_with_duplicate_snippets()
    retriever = evidence_retriever.MarketEvidenceRetriever(store, persist_dir=None)
    panel = retriever.retrieve_role_evidence(store.roles[0], top_k=8)

    evidence_ids = [item.evidence_id for item in panel]
    assert all(item.evidence_id for item in panel)
    assert len(evidence_ids) == len(set(evidence_ids))

    normalized = [
        re.sub(r"\s+", " ", item.snippet.strip().lower())
        for item in panel
    ]
    assert len(normalized) == len(set(normalized))
