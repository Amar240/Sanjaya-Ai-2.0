from __future__ import annotations

from app.agents.job_matcher import build_job_match_response, match_extracted_to_skills
from app.schemas.catalog import SkillMarket
from app.schemas.job_match import JobExtractResult
from app.schemas.plan import PlanResponse, SkillCoverage


def test_job_match_out_of_scope_semantics(sample_store) -> None:
    sample_store.skills = [
        SkillMarket.model_validate(
            {
                "skill_id": "SK_PYTHON",
                "name": "Python",
                "aliases": [],
                "category": "Programming",
                "source_refs": ["SRC_TEST"],
            }
        ),
        SkillMarket.model_validate(
            {
                "skill_id": "SK_SQL",
                "name": "SQL",
                "aliases": [],
                "category": "Data",
                "source_refs": ["SRC_TEST"],
            }
        ),
    ]
    extracted = JobExtractResult(
        job_title="Role",
        required_skills=["python", "sql"],
        preferred_skills=[],
        tools=[],
    )
    mapped, unmapped, summary = match_extracted_to_skills(extracted, sample_store)
    plan = PlanResponse(
        selected_role_id="ROLE_TEST",
        selected_role_title="Test",
        skill_coverage=[SkillCoverage(required_skill_id="SK_PYTHON", covered=True, matched_courses=[])],
    )
    response = build_job_match_response(
        extracted=extracted,
        mapped_skills=mapped,
        unmapped_terms=unmapped,
        mapping_summary=summary,
        store=sample_store,
        plan=plan,
        llm_status="disabled",
        llm_error=None,
    )
    assert response.covered_skill_ids == ["SK_PYTHON"]
    assert response.missing_skill_ids == []
    assert response.out_of_scope_skill_ids == ["SK_SQL"]
