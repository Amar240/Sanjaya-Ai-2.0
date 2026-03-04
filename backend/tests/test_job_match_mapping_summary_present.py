from __future__ import annotations

from app.agents.job_matcher import match_extracted_to_skills
from app.schemas.catalog import SkillMarket
from app.schemas.job_match import JobExtractResult


def test_job_match_mapping_summary_present(sample_store) -> None:
    sample_store.skills = [
        SkillMarket.model_validate(
            {
                "skill_id": "SK_PYTHON",
                "name": "Python",
                "aliases": [],
                "category": "Programming",
                "source_refs": ["SRC_TEST"],
            }
        )
    ]
    extracted = JobExtractResult(
        job_title="Role",
        required_skills=["python", "unknownthing"],
        preferred_skills=[],
        tools=[],
    )
    mapped, unmapped, summary = match_extracted_to_skills(extracted, sample_store)
    assert mapped
    assert unmapped
    assert summary.mapped_count == len(mapped)
    assert summary.unmapped_count == len(unmapped)
    assert summary.threshold_used == 0.35
