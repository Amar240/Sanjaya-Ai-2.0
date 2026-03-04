from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Literal

from ..ops.db import connect, get_db_path, init_db, utc_now
from ..schemas.plan import PlanRequest
from ..schemas.plan import PlanResponse

EventType = Literal[
    "plan_created",
    "advisor_question",
    "validation_event",
    "role_search",
    "unknown_role_request",
]


def analytics_dir() -> Path:
    raw = os.getenv("SANJAYA_ANALYTICS_DIR", "").strip()
    if raw:
        return Path(raw).resolve()
    return get_db_path().parent


def events_path() -> Path:
    # Kept for backward compatibility in tests/tools.
    return get_db_path()


def append_event(
    *,
    event_type: EventType,
    plan_id: str | None = None,
    data_version: str | None = None,
    request_id: str | None = None,
    selected_role_id: str | None = None,
    candidate_roles: list[dict[str, float | str]] | None = None,
    intent: str | None = None,
    error_codes: list[str] | None = None,
    role_query: str | None = None,
    question_hash: str | None = None,
    keyword_tags: list[str] | None = None,
    notes: dict | None = None,
) -> dict:
    init_db()
    payload = {
        "ts": utc_now(),
        "event_type": event_type,
        "plan_id": plan_id,
        "data_version": data_version,
        "request_id": request_id,
        "selected_role_id": selected_role_id,
        "candidate_roles": candidate_roles or None,
        "intent": intent,
        "error_codes": error_codes or None,
        "role_query": role_query,
        "role_query_norm": normalize_role_query(role_query) if role_query else None,
        "question_hash": question_hash,
        "keyword_tags": keyword_tags or None,
        "notes": notes or {},
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO events(
                ts, event_type, plan_id, data_version, request_id, selected_role_id,
                candidate_roles_json, intent, question_hash, keyword_tags_json, error_codes_json,
                role_query, role_query_norm, notes_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["ts"],
                payload["event_type"],
                payload["plan_id"],
                payload["data_version"],
                payload["request_id"],
                payload["selected_role_id"],
                _json_dump(payload["candidate_roles"]),
                payload["intent"],
                payload["question_hash"],
                _json_dump(payload["keyword_tags"]),
                _json_dump(payload["error_codes"]),
                payload["role_query"],
                payload["role_query_norm"],
                _json_dump(payload["notes"]),
            ),
        )
        conn.commit()
    return payload


def log_plan_created(plan: PlanResponse, request: PlanRequest) -> dict:
    candidate_roles = [
        {"role_id": item.role_id, "score": float(item.score)}
        for item in (plan.candidate_roles or [])[:3]
    ]
    return append_event(
        event_type="plan_created",
        plan_id=plan.plan_id or None,
        data_version=plan.data_version or None,
        request_id=plan.request_id or None,
        selected_role_id=plan.selected_role_id,
        candidate_roles=candidate_roles,
        error_codes=[error.code for error in (plan.validation_errors or [])],
        notes={
            "goal_type": request.student_profile.goal_type,
            "confidence_level": request.student_profile.confidence_level,
            "hours_per_week": int(request.student_profile.hours_per_week),
        },
    )


def log_advisor_question(
    *,
    plan_id: str | None,
    data_version: str | None,
    request_id: str | None,
    intent: str | None,
    question: str,
) -> dict:
    keyword_tags = keyword_tags_for(question) if _keywords_logging_enabled() else None
    return append_event(
        event_type="advisor_question",
        plan_id=plan_id,
        data_version=data_version,
        request_id=request_id,
        intent=intent,
        question_hash=hashlib.sha256(question.encode("utf-8")).hexdigest()[:16],
        keyword_tags=keyword_tags,
        notes={},
    )


def log_role_search(
    *,
    request_id: str | None,
    data_version: str | None,
    role_query: str,
    candidate_roles: list[dict[str, float | str]] | None,
    plan_id: str | None = None,
) -> dict:
    return append_event(
        event_type="role_search",
        plan_id=plan_id,
        data_version=data_version,
        request_id=request_id,
        candidate_roles=candidate_roles,
        role_query=role_query.strip(),
    )


def log_unknown_role_request(
    *,
    request_id: str | None,
    data_version: str | None,
    role_query: str,
    candidate_roles: list[dict[str, float | str]] | None,
    top1_score: float,
    plan_id: str | None = None,
) -> dict:
    return append_event(
        event_type="unknown_role_request",
        plan_id=plan_id,
        data_version=data_version,
        request_id=request_id,
        candidate_roles=candidate_roles,
        role_query=role_query.strip(),
        notes={"top1_score": float(top1_score)},
    )


def iter_events(*, window_days: int | None = None) -> list[dict]:
    init_db()
    out: list[dict] = []
    sql = (
        "SELECT ts,event_type,plan_id,data_version,request_id,selected_role_id,"
        "candidate_roles_json,intent,question_hash,keyword_tags_json,error_codes_json,"
        "role_query,role_query_norm,notes_json FROM events"
    )
    params: tuple[object, ...] = ()
    if window_days and window_days > 0:
        sql += " WHERE datetime(replace(ts,'Z','')) >= datetime('now', ?)"
        params = (f"-{int(window_days)} days",)
    sql += " ORDER BY id ASC"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    for row in rows:
        out.append(
            {
                "ts": row["ts"],
                "event_type": row["event_type"],
                "plan_id": row["plan_id"],
                "data_version": row["data_version"],
                "request_id": row["request_id"],
                "selected_role_id": row["selected_role_id"],
                "candidate_roles": _json_load(row["candidate_roles_json"], default=None),
                "intent": row["intent"],
                "question_hash": row["question_hash"],
                "keyword_tags": _json_load(row["keyword_tags_json"], default=None),
                "error_codes": _json_load(row["error_codes_json"], default=None),
                "role_query": row["role_query"],
                "role_query_norm": row["role_query_norm"],
                "notes": _json_load(row["notes_json"], default={}),
            }
        )
    return out


def normalize_role_query(value: str | None) -> str:
    if not value:
        return ""
    lower = value.lower()
    lower = re.sub(r"[^a-z0-9\s]+", " ", lower)
    lower = re.sub(r"\s+", " ", lower).strip()
    return lower


def keyword_tags_for(question: str, limit: int = 5) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", question.lower())
    counts: dict[str, int] = {}
    for token in tokens:
        if len(token) < 3:
            continue
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [token for token, _ in ranked[:limit]]


def _keywords_logging_enabled() -> bool:
    return os.getenv("SANJAYA_LOG_KEYWORDS", "").strip() == "1"


def _json_dump(value: object) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _json_load(value: str | None, *, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default
