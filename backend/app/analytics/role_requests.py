from __future__ import annotations

import hashlib
import json
import os

from ..ops.db import connect, init_db, utc_now
from .events import normalize_role_query


def min_count_threshold(default: int = 3) -> int:
    raw = os.getenv("SANJAYA_ROLE_REQUEST_MIN_COUNT", "").strip()
    if not raw:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return max(1, parsed)


def load_role_requests() -> dict:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT role_request_id, role_query_norm, examples_json, count, first_seen, last_seen,
                   top_candidates_json, status, resolution_json
            FROM role_requests
            ORDER BY count DESC, role_query_norm ASC
            """
        ).fetchall()
    return {"items": [_row_to_item(row) for row in rows]}


def save_role_requests(payload: dict) -> None:
    init_db()
    items = payload.get("items", []) if isinstance(payload, dict) else []
    with connect() as conn:
        conn.execute("DELETE FROM role_requests")
        for item in items:
            if not isinstance(item, dict):
                continue
            conn.execute(
                """
                INSERT INTO role_requests(
                    role_request_id, role_query_norm, examples_json, count, first_seen, last_seen,
                    top_candidates_json, status, resolution_json
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.get("role_request_id"),
                    item.get("role_query_norm"),
                    _json_dump(item.get("examples", [])),
                    int(item.get("count", 0)),
                    item.get("first_seen") or utc_now(),
                    item.get("last_seen") or utc_now(),
                    _json_dump(item.get("top_candidates", [])),
                    item.get("status") or "open",
                    _json_dump(item.get("resolution", {})),
                ),
            )
        conn.commit()


def upsert_unknown_role_request(event: dict) -> dict | None:
    init_db()
    role_query = str(event.get("role_query") or "").strip()
    role_query_norm = normalize_role_query(event.get("role_query_norm") or role_query)
    if not role_query_norm:
        return None

    role_request_id = stable_role_request_id(role_query_norm)
    ts = str(event.get("ts") or utc_now())
    candidate_roles = _normalize_candidates(event.get("candidate_roles"))

    with connect() as conn:
        existing = conn.execute(
            """
            SELECT role_request_id, role_query_norm, examples_json, count, first_seen, last_seen,
                   top_candidates_json, status, resolution_json
            FROM role_requests WHERE role_request_id = ?
            """,
            (role_request_id,),
        ).fetchone()
        if existing is None:
            item = {
                "role_request_id": role_request_id,
                "role_query_norm": role_query_norm,
                "examples": [role_query] if role_query else [role_query_norm],
                "count": 1,
                "first_seen": ts,
                "last_seen": ts,
                "top_candidates": candidate_roles,
                "status": "open",
                "resolution": {
                    "mapped_role_id": None,
                    "new_role_id": None,
                    "note": None,
                },
            }
            conn.execute(
                """
                INSERT INTO role_requests(
                    role_request_id, role_query_norm, examples_json, count, first_seen, last_seen,
                    top_candidates_json, status, resolution_json
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    role_request_id,
                    role_query_norm,
                    _json_dump(item["examples"]),
                    item["count"],
                    item["first_seen"],
                    item["last_seen"],
                    _json_dump(item["top_candidates"]),
                    item["status"],
                    _json_dump(item["resolution"]),
                ),
            )
            conn.commit()
            return item

        current = _row_to_item(existing)
        current["count"] = int(current.get("count", 0)) + 1
        current["last_seen"] = ts
        examples = list(current.get("examples", []))
        if role_query and role_query not in examples:
            examples.append(role_query)
        current["examples"] = examples[:3]
        current["top_candidates"] = _choose_best_candidates(
            current.get("top_candidates", []),
            candidate_roles,
        )
        conn.execute(
            """
            UPDATE role_requests
            SET examples_json = ?, count = ?, last_seen = ?, top_candidates_json = ?
            WHERE role_request_id = ?
            """,
            (
                _json_dump(current["examples"]),
                int(current["count"]),
                current["last_seen"],
                _json_dump(current["top_candidates"]),
                role_request_id,
            ),
        )
        conn.commit()
        return current


def list_role_requests(
    *,
    status: str | None = "open",
    min_count: int | None = None,
    show_all: bool = False,
) -> list[dict]:
    threshold = min_count if min_count is not None else min_count_threshold()
    init_db()
    where = []
    params: list[object] = []
    if status:
        where.append("status = ?")
        params.append(status)
    if not show_all:
        where.append("count >= ?")
        params.append(int(threshold))
    sql = (
        "SELECT role_request_id, role_query_norm, examples_json, count, first_seen, last_seen, "
        "top_candidates_json, status, resolution_json FROM role_requests"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY status != 'open', count DESC, role_query_norm ASC"
    with connect() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [_row_to_item(row) for row in rows]


def get_role_request(role_request_id: str) -> dict | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT role_request_id, role_query_norm, examples_json, count, first_seen, last_seen,
                   top_candidates_json, status, resolution_json
            FROM role_requests WHERE role_request_id = ?
            """,
            (role_request_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_item(row)


def set_role_request_status(
    role_request_id: str,
    *,
    status: str,
    mapped_role_id: str | None = None,
    new_role_id: str | None = None,
    note: str | None = None,
) -> dict | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT role_request_id, role_query_norm, examples_json, count, first_seen, last_seen,
                   top_candidates_json, status, resolution_json
            FROM role_requests WHERE role_request_id = ?
            """,
            (role_request_id,),
        ).fetchone()
        if row is None:
            return None
        item = _row_to_item(row)
        resolution = dict(item.get("resolution", {}))
        if mapped_role_id is not None:
            resolution["mapped_role_id"] = mapped_role_id
        if new_role_id is not None:
            resolution["new_role_id"] = new_role_id
        if note is not None:
            resolution["note"] = note
        item["status"] = status
        item["resolution"] = resolution
        conn.execute(
            "UPDATE role_requests SET status = ?, resolution_json = ? WHERE role_request_id = ?",
            (
                status,
                _json_dump(resolution),
                role_request_id,
            ),
        )
        conn.commit()
        return item


def stable_role_request_id(role_query_norm: str) -> str:
    return hashlib.sha1(role_query_norm.encode("utf-8")).hexdigest()[:12]


def _normalize_candidates(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    out: list[dict] = []
    for item in value[:3]:
        if not isinstance(item, dict):
            continue
        role_id = str(item.get("role_id") or "").strip()
        if not role_id:
            continue
        try:
            score = float(item.get("score", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        out.append({"role_id": role_id, "score": score})
    out.sort(key=lambda row: (-float(row["score"]), row["role_id"]))
    return out[:3]


def _choose_best_candidates(existing, incoming) -> list[dict]:
    current = _normalize_candidates(existing)
    latest = _normalize_candidates(incoming)
    if not latest:
        return current
    current_top = float(current[0]["score"]) if current else float("-inf")
    latest_top = float(latest[0]["score"]) if latest else float("-inf")
    if latest_top > current_top:
        return latest
    if latest_top == current_top and latest:
        latest_key = "|".join(item["role_id"] for item in latest)
        current_key = "|".join(item["role_id"] for item in current)
        if latest_key < current_key:
            return latest
    return current


def _row_to_item(row) -> dict:
    return {
        "role_request_id": row["role_request_id"],
        "role_query_norm": row["role_query_norm"],
        "examples": _json_load(row["examples_json"], default=[]),
        "count": int(row["count"]),
        "first_seen": row["first_seen"],
        "last_seen": row["last_seen"],
        "top_candidates": _json_load(row["top_candidates_json"], default=[]),
        "status": row["status"],
        "resolution": _json_load(
            row["resolution_json"],
            default={"mapped_role_id": None, "new_role_id": None, "note": None},
        ),
    }


def _json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _json_load(value: str | None, *, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default
