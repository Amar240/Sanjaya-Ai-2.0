from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app import main as main_module
from app.agents.workflow import reset_plan_cache
from app.ops import connect
from app.plan_store import reset_plan_store


def _plan_payload() -> dict:
    return {
        "student_profile": {
            "level": "UG",
            "mode": "CORE",
            "current_semester": 1,
            "start_term": "Fall",
            "include_optional_terms": False,
            "completed_courses": [],
            "min_credits": 6,
            "target_credits": 6,
            "max_credits": 9,
            "interests": ["test"],
        },
        "preferred_role_id": "ROLE_TEST",
        "requested_role_text": "custom data analyst",
    }


def test_events_logged_on_plan_and_advisor(monkeypatch, sample_store, tmp_path) -> None:
    monkeypatch.setenv("SANJAYA_ANALYTICS_DIR", str(tmp_path))
    monkeypatch.delenv("SANJAYA_LOG_KEYWORDS", raising=False)
    sample_store.data_version = "analytics-events-v1"
    reset_plan_cache(max_size=256)
    reset_plan_store(max_size=256)
    monkeypatch.setattr(main_module, "load_catalog_store", lambda: sample_store)

    with TestClient(main_module.app) as client:
        plan_res = client.post("/plan", json=_plan_payload())
        assert plan_res.status_code == 200
        plan_payload = plan_res.json()

        advisor_res = client.post(
            "/advisor/ask",
            json={
                "question": "why not data scientist?",
                "tone": "concise",
                "plan_id": plan_payload["plan_id"],
            },
        )
        assert advisor_res.status_code == 200

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT event_type, question_hash, keyword_tags_json, notes_json
            FROM events
            ORDER BY id ASC
            """
        ).fetchall()
    event_types = [row["event_type"] for row in rows]
    assert "plan_created" in event_types
    assert "role_search" in event_types
    assert "advisor_question" in event_types

    advisor_event = next(row for row in rows if row["event_type"] == "advisor_question")
    assert advisor_event["question_hash"]
    assert advisor_event["keyword_tags_json"] in (None, "null")

    plan_event = next(row for row in rows if row["event_type"] == "plan_created")
    notes = json.loads(plan_event["notes_json"] or "{}")
    assert notes["goal_type"] == "select_role"
    assert notes["confidence_level"] == "medium"
    assert notes["hours_per_week"] == 6
