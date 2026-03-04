from __future__ import annotations

from app.agents.planner import build_plan
from app.data_loader import CatalogStore
from app.schemas.catalog import (
    Course,
    CourseSkillMapping,
    RoleMarket,
    RoleSkillEvidence,
    SkillMarket,
    SourceReference,
)
from app.schemas.plan import PlanRequest, StudentProfile


def _course(course_id: str, *, prerequisites: list[str] | None = None) -> Course:
    return Course.model_validate(
        {
            "course_id": course_id,
            "title": course_id,
            "department": "CISC",
            "level": "UG",
            "credits": 3,
            "description": "course",
            "topics": [],
            "prerequisites": prerequisites or [],
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
    courses = [
        _course("CISC-100"),
        _course("CISC-200", prerequisites=["CISC-100"]),
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
                "summary": "Role summary",
                "required_skills": [{"skill_id": "SK_TEST", "importance": 5}],
                "evidence_sources": ["SRC_TEST"],
            }
        )
    ]
    sources = [
        SourceReference.model_validate(
            {
                "source_id": "SRC_TEST",
                "provider": "Provider",
                "type": "report",
                "title": "Source",
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
                "confidence": 0.8,
                "evidence_sources": ["SRC_TEST"],
                "evidence_note": "Test evidence",
            }
        )
    ]
    course_skills = [
        CourseSkillMapping.model_validate(
            {"course_id": "CISC-200", "skill_id": "SK_TEST", "strength": 5}
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
        warnings=[],
    )


def test_topo_scheduler_keeps_prereq_order() -> None:
    store = _store()
    request = PlanRequest(
        student_profile=StudentProfile(
            level="UG",
            mode="CORE",
            current_semester=1,
            start_term="Fall",
            include_optional_terms=False,
            completed_courses=[],
            min_credits=3,
            target_credits=6,
            max_credits=9,
            interests=["test"],
        ),
        preferred_role_id="ROLE_TEST",
    )
    plan = build_plan(request, store)
    semester_by_course = {
        course_id: sem.semester_index
        for sem in plan.semesters
        for course_id in sem.courses
    }
    assert semester_by_course["CISC-100"] < semester_by_course["CISC-200"]
