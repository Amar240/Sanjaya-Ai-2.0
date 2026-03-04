from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from threading import Lock
from typing import Iterator

_DB_LOCK = Lock()
_INITIALIZED = False


def get_db_path() -> Path:
    raw = os.getenv("SANJAYA_OPS_DB_PATH", "").strip()
    if raw:
        return Path(raw).resolve()
    if Path("/app").exists():
        return Path("/app/data/ops/sanjaya_ops.db")
    return (_project_root() / "data" / "ops" / "sanjaya_ops.db").resolve()


def init_db() -> None:
    global _INITIALIZED
    with _DB_LOCK:
        if _INITIALIZED:
            return
        path = get_db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path, timeout=30) as conn:
            _configure_connection(conn)
            _run_migrations(conn)
            conn.commit()
        _INITIALIZED = True


def reset_db_state() -> None:
    global _INITIALIZED
    with _DB_LOCK:
        _INITIALIZED = False


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    init_db()
    conn = sqlite3.connect(get_db_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    _configure_connection(conn)
    try:
        yield conn
    finally:
        conn.close()


def insert_audit_log(
    *,
    user: str,
    action: str,
    entity: str,
    draft_id: str | None = None,
    before_hash: str | None = None,
    after_hash: str | None = None,
    meta: dict | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO audit_log(
                ts, user, action, entity, draft_id, before_hash, after_hash, meta_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                utc_now(),
                user,
                action,
                entity,
                draft_id,
                before_hash,
                after_hash,
                _json_dump(meta or {}),
            ),
        )
        conn.commit()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _configure_connection(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")


def _run_migrations(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts TEXT NOT NULL,
          event_type TEXT NOT NULL,
          plan_id TEXT,
          data_version TEXT,
          request_id TEXT,
          selected_role_id TEXT,
          candidate_roles_json TEXT,
          intent TEXT,
          question_hash TEXT,
          keyword_tags_json TEXT,
          error_codes_json TEXT,
          role_query TEXT,
          role_query_norm TEXT,
          notes_json TEXT
        );
        CREATE TABLE IF NOT EXISTS role_requests(
          role_request_id TEXT PRIMARY KEY,
          role_query_norm TEXT NOT NULL,
          examples_json TEXT NOT NULL,
          count INTEGER NOT NULL,
          first_seen TEXT NOT NULL,
          last_seen TEXT NOT NULL,
          top_candidates_json TEXT NOT NULL,
          status TEXT NOT NULL,
          resolution_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS drafts(
          draft_id TEXT PRIMARY KEY,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS draft_curated_mappings(
          row_id TEXT PRIMARY KEY,
          draft_id TEXT NOT NULL,
          role_id TEXT NOT NULL,
          skill_id TEXT NOT NULL,
          course_id TEXT NOT NULL,
          note TEXT,
          updated_at TEXT NOT NULL,
          FOREIGN KEY(draft_id) REFERENCES drafts(draft_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS draft_sources(
          draft_id TEXT NOT NULL,
          source_id TEXT NOT NULL,
          enabled INTEGER NOT NULL,
          trust_weight REAL NOT NULL,
          provider TEXT,
          title TEXT,
          url TEXT,
          PRIMARY KEY (draft_id, source_id),
          FOREIGN KEY(draft_id) REFERENCES drafts(draft_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS draft_roles_calibrated(
          draft_id TEXT NOT NULL,
          role_id TEXT NOT NULL,
          title TEXT NOT NULL,
          market TEXT,
          required_skills_json TEXT NOT NULL,
          evidence_sources_json TEXT NOT NULL,
          role_origin TEXT,
          created_by TEXT,
          created_at TEXT,
          summary TEXT,
          source_occupation_codes_json TEXT,
          department_owner TEXT,
          country_scope TEXT,
          demo_tier TEXT,
          reality_complete INTEGER,
          project_coverage_complete INTEGER,
          PRIMARY KEY (draft_id, role_id),
          FOREIGN KEY(draft_id) REFERENCES drafts(draft_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS audit_log(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts TEXT NOT NULL,
          user TEXT NOT NULL,
          action TEXT NOT NULL,
          entity TEXT NOT NULL,
          draft_id TEXT,
          before_hash TEXT,
          after_hash TEXT,
          meta_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
        CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);
        CREATE INDEX IF NOT EXISTS idx_events_role_query_norm ON events(role_query_norm);
        CREATE INDEX IF NOT EXISTS idx_role_requests_status ON role_requests(status);
        CREATE INDEX IF NOT EXISTS idx_role_requests_count ON role_requests(count);
        """
    )
    _ensure_column(conn, "draft_roles_calibrated", "department_owner", "TEXT")
    _ensure_column(conn, "draft_roles_calibrated", "country_scope", "TEXT")
    _ensure_column(conn, "draft_roles_calibrated", "demo_tier", "TEXT")
    _ensure_column(conn, "draft_roles_calibrated", "reality_complete", "INTEGER")
    _ensure_column(conn, "draft_roles_calibrated", "project_coverage_complete", "INTEGER")


def _ensure_column(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_type: str,
) -> None:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing = {str(row[1]) for row in rows}
    if column_name in existing:
        return
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def _json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]
