from __future__ import annotations

from app.agents.gap_engine import build_gap_report
from app.schemas.plan import PlanResponse, SkillCoverage
from app.schemas.reality import ProjectTemplate


def _plan() -> PlanResponse:
    return PlanResponse(
        selected_role_id="ROLE_TEST",
        selected_role_title="Test Role",
        skill_coverage=[SkillCoverage(required_skill_id="SK_TEST", covered=False, matched_courses=[])],
    )


def test_gap_projects_respect_confidence_and_hours(monkeypatch, sample_store) -> None:
    monkeypatch.setenv("SANJAYA_PROJECTS_PER_SKILL", "3")
    sample_store.project_templates = [
        ProjectTemplate.model_validate(
            {
                "template_id": "PT_BEGINNER_6",
                "skill_id": "SK_TEST",
                "level": "beginner",
                "title": "Beginner 6h",
                "time_hours": 6,
                "deliverables": ["D"],
                "rubric": ["R"],
                "links": [],
            }
        ),
        ProjectTemplate.model_validate(
            {
                "template_id": "PT_BEGINNER_14",
                "skill_id": "SK_TEST",
                "level": "beginner",
                "title": "Beginner 14h",
                "time_hours": 14,
                "deliverables": ["D"],
                "rubric": ["R"],
                "links": [],
            }
        ),
        ProjectTemplate.model_validate(
            {
                "template_id": "PT_INTERMEDIATE_10",
                "skill_id": "SK_TEST",
                "level": "intermediate",
                "title": "Intermediate 10h",
                "time_hours": 10,
                "deliverables": ["D"],
                "rubric": ["R"],
                "links": [],
            }
        ),
    ]

    low_report = build_gap_report(_plan(), sample_store, confidence_level="low", hours_per_week=3)
    low_projects = low_report.missing_skills[0].recommended_projects
    assert [item.template_id for item in low_projects][:2] == ["PT_BEGINNER_6", "PT_BEGINNER_14"]
    assert low_projects[0].effort_fit == "fits"

    high_report = build_gap_report(_plan(), sample_store, confidence_level="high", hours_per_week=10)
    high_projects = high_report.missing_skills[0].recommended_projects
    assert "PT_INTERMEDIATE_10" in [item.template_id for item in high_projects]


def test_gap_projects_fallback_expands_levels_when_beginner_missing(monkeypatch, sample_store) -> None:
    monkeypatch.setenv("SANJAYA_PROJECTS_PER_SKILL", "2")
    sample_store.project_templates = [
        ProjectTemplate.model_validate(
            {
                "template_id": "PT_INTERMEDIATE_ONLY",
                "skill_id": "SK_TEST",
                "level": "intermediate",
                "title": "Intermediate Only",
                "time_hours": 10,
                "deliverables": ["D"],
                "rubric": ["R"],
                "links": [],
            }
        )
    ]

    report = build_gap_report(_plan(), sample_store, confidence_level="low", hours_per_week=3)
    projects = report.missing_skills[0].recommended_projects
    assert projects
    assert projects[0].template_id == "PT_INTERMEDIATE_ONLY"
