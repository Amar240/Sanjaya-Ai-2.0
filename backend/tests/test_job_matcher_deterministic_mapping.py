from __future__ import annotations

from app.agents.job_matcher import match_extracted_to_skills
from app.schemas.catalog import SkillMarket
from app.schemas.job_match import JobExtractResult


def test_job_matcher_deterministic_mapping(sample_store) -> None:
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
    extracted = JobExtractResult(
        job_title="Data role",
        required_skills=["python", "sql"],
        preferred_skills=[],
        tools=[],
    )

    first, unmapped_first, _ = match_extracted_to_skills(extracted, sample_store)
    second, unmapped_second, _ = match_extracted_to_skills(extracted, sample_store)

    assert [item.skill_id for item in first] == ["SK_PYTHON", "SK_SQL"]
    assert [item.skill_id for item in second] == ["SK_PYTHON", "SK_SQL"]
    assert unmapped_first == unmapped_second == []
