from __future__ import annotations

from app.schemas.plan import CoursePurposeCard, EvidencePanelItem, PlanResponse, SkillCoverage
from app.validators.plan_verifier import check_evidence_integrity


def _evidence(*, evidence_id: str, role_id: str, skill_id: str) -> EvidencePanelItem:
    return EvidencePanelItem(
        evidence_id=evidence_id,
        role_id=role_id,
        skill_id=skill_id,
        skill_name=skill_id,
        source_id="SRC_TEST",
        source_provider="Test Provider",
        source_title="Test Source",
        source_url="https://example.com/source",
        snippet="test snippet",
        retrieval_method="lexical",
        rank_score=0.5,
        confidence=0.8,
    )


def test_evidence_integrity_card_evidence_not_in_panel_warning() -> None:
    plan = PlanResponse(
        selected_role_id="ROLE_A",
        selected_role_title="Role A",
        skill_coverage=[
            SkillCoverage(required_skill_id="SK_X", covered=True, matched_courses=[])
        ],
        evidence_panel=[_evidence(evidence_id="abc", role_id="ROLE_A", skill_id="SK_X")],
        course_purpose_cards=[
            CoursePurposeCard(
                course_id="CISC-101",
                course_title="Intro",
                why_this_course="reason",
                satisfied_skills=["SK_X"],
                evidence=[_evidence(evidence_id="def", role_id="ROLE_A", skill_id="SK_X")],
            )
        ],
    )

    warnings = check_evidence_integrity(plan)
    assert len(warnings) == 1
    warning = warnings[0]
    assert warning.code == "EVIDENCE_INTEGRITY_VIOLATION"
    assert warning.details.get("severity") == "warning"
    assert warning.details.get("kind") == "card_evidence_not_in_panel"
