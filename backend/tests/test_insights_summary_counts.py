from __future__ import annotations

from app.analytics.events import append_event
from app.analytics.insights import reset_insights_cache, summary
from app.analytics.role_requests import upsert_unknown_role_request


def test_insights_summary_counts(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SANJAYA_ANALYTICS_DIR", str(tmp_path))
    reset_insights_cache()
    append_event(
        event_type="plan_created",
        plan_id="plan-1",
        selected_role_id="ROLE_A",
        error_codes=["CREDIT_OVER_MAX", "SKILL_GAP"],
    )
    append_event(
        event_type="advisor_question",
        plan_id="plan-1",
        intent="alternatives_compare",
        notes={"question_hash": "abc"},
    )
    append_event(
        event_type="role_search",
        role_query="AI Product Lead",
    )
    unknown = append_event(
        event_type="unknown_role_request",
        role_query="AI Product Lead",
        candidate_roles=[{"role_id": "ROLE_A", "score": 0.2}],
        notes={"top1_score": 0.2},
    )
    upsert_unknown_role_request(unknown)

    payload = summary(window="30d")
    assert payload["events_total"] >= 4
    assert payload["top_roles_selected"][0]["key"] == "ROLE_A"
    assert any(item["key"] == "alternatives_compare" for item in payload["top_intents"])
    assert payload["top_unknown_role_requests"][0]["role_query_norm"] == "ai product lead"
