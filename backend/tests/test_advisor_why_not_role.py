from __future__ import annotations

from app.agents.advisor_agent import answer_advisor_question
from app.schemas.advisor import AdvisorRequest
from app.schemas.plan import CandidateRole, PlanResponse, SkillCoverage


def test_advisor_handles_why_not_role_from_candidate_roles(sample_store) -> None:
    plan = PlanResponse(
        selected_role_id="ROLE_DATA_ENGINEER",
        selected_role_title="Data Engineer",
        plan_id="plan-xyz",
        skill_coverage=[
            SkillCoverage(required_skill_id="SK_TEST", covered=True, matched_courses=["CISC-201"])
        ],
        candidate_roles=[
            CandidateRole(
                role_id="ROLE_DATA_ENGINEER",
                role_title="Data Engineer",
                score=0.91,
                reasons=["Interest overlap tokens: 3; phrase hits: 1."],
            ),
            CandidateRole(
                role_id="ROLE_DATA_SCIENTIST",
                role_title="Data Scientist",
                score=0.86,
                reasons=["Interest overlap tokens: 2; phrase hits: 1."],
            ),
        ],
    )
    response = answer_advisor_question(
        AdvisorRequest(
            question="Why not Data Scientist?",
            tone="friendly",
            plan=plan,
        ),
        sample_store,
    )

    assert response.intent == "alternatives_compare"
    assert response.plan_id == "plan-xyz"
    assert any("Candidate role ROLE_DATA_SCIENTIST" in citation.label for citation in response.citations)
