from __future__ import annotations

from app.agents.gap_engine import build_gap_report
from app.schemas.plan import PlanResponse, SkillCoverage
from app.schemas.reality import ProjectTemplate


def test_gap_report_deterministic(monkeypatch, sample_store) -> None:
    monkeypatch.setenv("SANJAYA_PROJECTS_PER_SKILL", "2")
    sample_store.project_templates = [
        ProjectTemplate.model_validate(
            {
                "template_id": "PT_Z",
                "skill_id": "SK_TEST",
                "level": "advanced",
                "title": "Advanced Project",
                "time_hours": 20,
                "deliverables": ["A"],
                "rubric": ["R"],
                "links": [],
            }
        ),
        ProjectTemplate.model_validate(
            {
                "template_id": "PT_A",
                "skill_id": "SK_TEST",
                "level": "beginner",
                "title": "Beginner Project",
                "time_hours": 8,
                "deliverables": ["B"],
                "rubric": ["R"],
                "links": [],
            }
        ),
        ProjectTemplate.model_validate(
            {
                "template_id": "PT_B",
                "skill_id": "SK_TEST",
                "level": "intermediate",
                "title": "Intermediate Project",
                "time_hours": 10,
                "deliverables": ["C"],
                "rubric": ["R"],
                "links": [],
            }
        ),
    ]
    plan = PlanResponse(
        selected_role_id="ROLE_TEST",
        selected_role_title="Test Role",
        skill_coverage=[
            SkillCoverage(required_skill_id="SK_TEST", covered=False, matched_courses=[]),
        ],
    )
    report = build_gap_report(plan, sample_store)
    assert len(report.missing_skills) == 1
    picked = report.missing_skills[0].recommended_projects
    assert len(picked) == 2
    assert [item.template_id for item in picked] == ["PT_A", "PT_B"]
