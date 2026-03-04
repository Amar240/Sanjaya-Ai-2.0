from __future__ import annotations

from app.analytics.events import log_unknown_role_request
from app.analytics.role_requests import stable_role_request_id, upsert_unknown_role_request
from app.ops import connect


def test_role_request_aggregation(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SANJAYA_ANALYTICS_DIR", str(tmp_path))
    role_query = "AI Policy Architect"
    role_norm = "ai policy architect"
    expected_id = stable_role_request_id(role_norm)
    candidates = [{"role_id": "ROLE_TEST", "score": 0.11}]

    for _ in range(3):
        event = log_unknown_role_request(
            request_id="req-1",
            data_version="v1",
            role_query=role_query,
            candidate_roles=candidates,
            top1_score=0.11,
            plan_id="plan-1",
        )
        upsert_unknown_role_request(event)

    with connect() as conn:
        row = conn.execute(
            """
            SELECT role_request_id, role_query_norm, count
            FROM role_requests
            WHERE role_request_id = ?
            """,
            (expected_id,),
        ).fetchone()
    assert row is not None
    assert row["role_request_id"] == expected_id
    assert row["role_query_norm"] == role_norm
    assert int(row["count"]) == 3
