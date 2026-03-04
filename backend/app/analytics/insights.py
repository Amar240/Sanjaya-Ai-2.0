from __future__ import annotations

from collections import Counter
import json
import time
from threading import Lock

from ..ops.db import connect, init_db
from .role_requests import list_role_requests

_CACHE_LOCK = Lock()
_CACHE: dict[str, tuple[float, dict]] = {}

_WARNING_CODES = {
    "SKILL_GAP",
    "PREREQ_EXTERNAL_REF",
    "PREREQ_COMPLEX_UNSUPPORTED",
    "CREDITS_BELOW_MIN",
    "ANTIREQ_CONFLICT",
    "COREQ_NOT_SATISFIED",
    "EVIDENCE_INTEGRITY_VIOLATION",
    "ROLE_REQUEST_UNRESOLVED",
}


def summary(window: str = "30d") -> dict:
    days = _parse_window_days(window)
    cache_key = f"window:{days}"
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if cached and (now - cached[0]) < 60:
            return cached[1]

    init_db()
    where = "WHERE datetime(replace(ts,'Z','')) >= datetime('now', ?)"
    params = (f"-{days} days",)

    with connect() as conn:
        events_total = int(
            conn.execute(f"SELECT COUNT(*) FROM events {where}", params).fetchone()[0]
        )
        top_roles = conn.execute(
            f"""
            SELECT selected_role_id AS key, COUNT(*) AS count
            FROM events
            {where} AND event_type = 'plan_created' AND selected_role_id IS NOT NULL
            GROUP BY selected_role_id
            ORDER BY count DESC, key ASC
            LIMIT 10
            """,
            params,
        ).fetchall()
        top_searches = conn.execute(
            f"""
            SELECT role_query_norm AS key, COUNT(*) AS count
            FROM events
            {where} AND event_type = 'role_search' AND role_query_norm IS NOT NULL
            GROUP BY role_query_norm
            ORDER BY count DESC, key ASC
            LIMIT 10
            """,
            params,
        ).fetchall()
        top_intents = conn.execute(
            f"""
            SELECT intent AS key, COUNT(*) AS count
            FROM events
            {where} AND event_type = 'advisor_question' AND intent IS NOT NULL
            GROUP BY intent
            ORDER BY count DESC, key ASC
            LIMIT 10
            """,
            params,
        ).fetchall()
        plan_rows = conn.execute(
            f"""
            SELECT error_codes_json FROM events
            {where} AND event_type = 'plan_created' AND error_codes_json IS NOT NULL
            """,
            params,
        ).fetchall()

    error_counter: Counter[str] = Counter()
    warning_count = 0
    error_count = 0
    for row in plan_rows:
        try:
            codes = json.loads(row["error_codes_json"])
        except json.JSONDecodeError:
            continue
        if not isinstance(codes, list):
            continue
        for code in codes:
            if not isinstance(code, str):
                continue
            error_counter[code] += 1
            if code in _WARNING_CODES:
                warning_count += 1
            else:
                error_count += 1

    unknown_requests = list_role_requests(show_all=True, status=None)
    payload = {
        "window": f"{days}d",
        "events_total": events_total,
        "top_roles_selected": _rows_to_list(top_roles),
        "top_role_searches": _rows_to_list(top_searches),
        "top_unknown_role_requests": [
            {
                "role_request_id": item.get("role_request_id"),
                "role_query_norm": item.get("role_query_norm"),
                "count": int(item.get("count", 0)),
                "status": item.get("status"),
            }
            for item in sorted(
                unknown_requests,
                key=lambda row: (-int(row.get("count", 0)), str(row.get("role_query_norm", ""))),
            )[:10]
        ],
        "top_error_codes": [
            {"key": key, "count": count}
            for key, count in error_counter.most_common(10)
        ],
        "top_intents": _rows_to_list(top_intents),
        "severity_breakdown": {"warnings": warning_count, "errors": error_count},
    }
    with _CACHE_LOCK:
        _CACHE[cache_key] = (now, payload)
    return payload


def reset_insights_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()


def _parse_window_days(window: str) -> int:
    raw = (window or "30d").strip().lower()
    if raw in {"7", "7d", "last_7d"}:
        return 7
    return 30


def _rows_to_list(rows) -> list[dict]:
    return [{"key": row["key"], "count": int(row["count"])} for row in rows]
