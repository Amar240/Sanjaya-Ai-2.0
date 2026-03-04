from __future__ import annotations

from app.agents.workflow import run_plan_workflow
from app.schemas.catalog import (
    FusionPack,
    FusionRoleProfile,
)
from app.schemas.plan import PlanRequest, StudentProfile


def test_fusion_pack_summary_attached(sample_store) -> None:
    sample_store.fusion_role_profiles = [
        FusionRoleProfile.model_validate(
            {
                "role_id": "ROLE_TEST",
                "title": "Test Role",
                "domain": "Finance",
                "skill_bands": {"domain_weight": 0.6, "tech_weight": 0.4},
                "domain_skills": [{"skill_id": "SK_TEST", "importance": 4}],
                "tech_skills": [{"skill_id": "SK_TEST", "importance": 4}],
                "unlock_skills": [{"skill_id": "SK_TEST", "reason": "Bridge skill"}],
                "evidence_sources": ["SRC_TEST"],
            }
        )
    ]
    sample_store.fusion_packs_usa = [
        FusionPack.model_validate(
            {
                "fusion_pack_id": "PACK_TEST",
                "title": "Finance + Data Catalyst",
                "domain_a": "Finance",
                "domain_b": "Data",
                "target_roles": ["ROLE_TEST"],
                "unlock_skills": ["SK_TEST"],
                "starter_projects": ["PT_SK_TEST_1"],
                "evidence_sources": ["SRC_TEST"],
            }
        )
    ]
    request = PlanRequest(
        student_profile=StudentProfile(
            level="UG",
            mode="FUSION",
            fusion_domain="Finance",
            current_semester=1,
            start_term="Fall",
            include_optional_terms=False,
            completed_courses=[],
            min_credits=6,
            target_credits=6,
            max_credits=9,
            interests=["testing"],
        ),
        preferred_role_id="ROLE_TEST",
    )
    plan = run_plan_workflow(request, sample_store)
    assert plan.fusion_pack_summary is not None
    assert plan.fusion_pack_summary.fusion_pack_id == "PACK_TEST"
