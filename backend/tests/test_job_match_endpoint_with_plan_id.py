from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as main_module
from app.agents.workflow import reset_plan_cache
from app.plan_store import get_plan_store, reset_plan_store
from app.schemas.catalog import SkillMarket
from app.schemas.plan import PlanResponse, SkillCoverage, StudentProfile
from app.schemas.reality import ProjectTemplate


def test_job_match_endpoint_with_plan_id(monkeypatch, sample_store) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    reset_plan_cache(max_size=256)
    reset_plan_store(max_size=256)

    sample_store.skills = [
        SkillMarket.model_validate(
            {
                "skill_id": "SK_PYTHON",
                "name": "Python",
                "aliases": ["py"],
                "category": "Programming",
                "source_refs": ["SRC_TEST"],
            }
        ),
        SkillMarket.model_validate(
            {
                "skill_id": "SK_SQL",
                "name": "SQL",
                "aliases": ["postgresql"],
                "category": "Data",
                "source_refs": ["SRC_TEST"],
            }
        ),
    ]
    sample_store.project_templates = [
        ProjectTemplate.model_validate(
            {
                "template_id": "PT_PY",
                "skill_id": "SK_PYTHON",
                "level": "beginner",
                "title": "Python Project",
                "time_hours": 8,
                "deliverables": ["Repo"],
                "rubric": ["Runs"],
                "links": [],
            }
        ),
        ProjectTemplate.model_validate(
            {
                "template_id": "PT_SQL",
                "skill_id": "SK_SQL",
                "level": "beginner",
                "title": "SQL Project",
                "time_hours": 10,
                "deliverables": ["Notebook"],
                "rubric": ["Queries"],
                "links": [],
            }
        ),
    ]
    monkeypatch.setattr(main_module, "load_catalog_store", lambda: sample_store)

    plan = PlanResponse(
        plan_id="plan-job-1",
        selected_role_id="ROLE_TEST",
        selected_role_title="Test",
        skill_coverage=[
            SkillCoverage(required_skill_id="SK_PYTHON", covered=True, matched_courses=["CISC-201"]),
            SkillCoverage(required_skill_id="SK_SQL", covered=False, matched_courses=[]),
        ],
        intake_snapshot=StudentProfile(
            level="UG",
            mode="CORE",
            goal_type="select_role",
            confidence_level="medium",
            hours_per_week=6,
            current_semester=1,
            start_term="Fall",
            include_optional_terms=False,
            completed_courses=[],
            min_credits=12,
            target_credits=15,
            max_credits=17,
            interests=["data"],
        ),
    )
    get_plan_store().put("plan-job-1", plan)

    with TestClient(main_module.app) as client:
        res = client.post(
            "/job/match",
            json={
                "plan_id": "plan-job-1",
                "text": "Data analyst role. Required skills: Python and SQL. Preferred: dashboards.",
            },
        )
    assert res.status_code == 200
    payload = res.json()
    assert "SK_PYTHON" in payload["covered_skill_ids"]
    assert "SK_SQL" in payload["missing_skill_ids"]
