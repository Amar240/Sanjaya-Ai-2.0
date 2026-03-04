from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import uuid

from ..analytics.events import normalize_role_query
from ..data_loader import CatalogStore, load_catalog_store
from ..ops.db import connect, init_db, insert_audit_log, utc_now


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def processed_dir() -> Path:
    return project_root() / "data" / "processed"


def drafts_root() -> Path:
    # Kept for backward compatibility with existing tests / tooling.
    return project_root() / "data" / "curation_drafts"


def history_root() -> Path:
    return processed_dir() / "history"


def roles_calibrated_processed_path() -> Path:
    return processed_dir() / "roles_market_calibrated.json"


def roles_baseline_processed_path() -> Path:
    return processed_dir() / "roles_market.json"


def draft_roles_path(draft_id: str) -> Path:
    # Legacy path helper; no longer primary store.
    return drafts_root() / draft_id / "roles_market_calibrated.json"


def create_draft(*, draft_id: str | None = None, created_by: str = "advisor") -> str:
    init_db()
    draft_id = draft_id or _new_draft_id()
    created_at = utc_now()

    curated_rows = _load_processed_json("course_skills_curated.json", default=[])
    sources_rows = _load_processed_json("market_sources.json", default=[])
    roles_rows = _load_processed_roles_rows()

    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO drafts(draft_id, created_by, created_at, status) VALUES(?, ?, ?, ?)",
            (draft_id, created_by, created_at, "open"),
        )
        conn.execute("DELETE FROM draft_curated_mappings WHERE draft_id = ?", (draft_id,))
        conn.execute("DELETE FROM draft_sources WHERE draft_id = ?", (draft_id,))
        conn.execute("DELETE FROM draft_roles_calibrated WHERE draft_id = ?", (draft_id,))

        for row in curated_rows:
            if not isinstance(row, dict):
                continue
            role_id = str(row.get("role_id", "")).strip()
            skill_id = str(row.get("skill_id", "")).strip()
            course_id = str(row.get("course_id", "")).strip()
            if not (role_id and skill_id and course_id):
                continue
            row_id = _mapping_row_id(role_id=role_id, skill_id=skill_id, course_id=course_id)
            conn.execute(
                """
                INSERT INTO draft_curated_mappings(
                    row_id, draft_id, role_id, skill_id, course_id, note, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    draft_id,
                    role_id,
                    skill_id,
                    course_id,
                    str(row.get("rationale") or row.get("note") or ""),
                    created_at,
                ),
            )

        for row in sources_rows:
            if not isinstance(row, dict):
                continue
            source_id = str(row.get("source_id", "")).strip()
            if not source_id:
                continue
            conn.execute(
                """
                INSERT INTO draft_sources(
                    draft_id, source_id, enabled, trust_weight, provider, title, url
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    source_id,
                    int(row.get("enabled", 1) in (1, True, "1", "true", "True")),
                    float(row.get("trust_weight", 0.85)),
                    str(row.get("provider") or ""),
                    str(row.get("title") or ""),
                    str(row.get("url") or ""),
                ),
            )

        for row in roles_rows:
            if not isinstance(row, dict):
                continue
            role_id = str(row.get("role_id", "")).strip()
            title = str(row.get("title", "")).strip()
            if not (role_id and title):
                continue
            conn.execute(
                """
                INSERT INTO draft_roles_calibrated(
                    draft_id, role_id, title, market, required_skills_json, evidence_sources_json,
                    role_origin, created_by, created_at, summary, source_occupation_codes_json,
                    department_owner, country_scope, demo_tier, reality_complete, project_coverage_complete
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    role_id,
                    title,
                    str(row.get("market_grounding") or row.get("market") or "direct"),
                    _json_dump(row.get("required_skills") or []),
                    _json_dump(row.get("evidence_sources") or []),
                    str(row.get("role_origin") or ""),
                    str(row.get("created_by") or ""),
                    str(row.get("created_at") or ""),
                    str(row.get("summary") or ""),
                    _json_dump(row.get("source_occupation_codes") or []),
                    str(row.get("department_owner") or ""),
                    str(row.get("country_scope") or "USA"),
                    str(row.get("demo_tier") or "extended"),
                    int(bool(row.get("reality_complete", False))),
                    int(bool(row.get("project_coverage_complete", False))),
                ),
            )

        conn.commit()

    insert_audit_log(
        user=created_by,
        action="draft_create",
        entity="draft",
        draft_id=draft_id,
        meta={"seed_counts": {"curated": len(curated_rows), "sources": len(sources_rows), "roles": len(roles_rows)}},
    )
    _mirror_roles_to_legacy_file(draft_id)
    return draft_id


def load_draft_roles(draft_id: str) -> list[dict]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT role_id, title, market, required_skills_json, evidence_sources_json,
                   role_origin, created_by, created_at, summary, source_occupation_codes_json,
                   department_owner, country_scope, demo_tier, reality_complete, project_coverage_complete
            FROM draft_roles_calibrated
            WHERE draft_id = ?
            ORDER BY role_id ASC
            """,
            (draft_id,),
        ).fetchall()
        exists = conn.execute("SELECT 1 FROM drafts WHERE draft_id = ?", (draft_id,)).fetchone()
    if exists is None:
        raise FileNotFoundError(f"Draft not found: {draft_id}")
    return [_row_to_role(row) for row in rows]


def save_draft_roles(draft_id: str, roles: list[dict]) -> None:
    init_db()
    with connect() as conn:
        exists = conn.execute("SELECT 1 FROM drafts WHERE draft_id = ?", (draft_id,)).fetchone()
        if exists is None:
            raise FileNotFoundError(f"Draft not found: {draft_id}")
        conn.execute("DELETE FROM draft_roles_calibrated WHERE draft_id = ?", (draft_id,))
        for role in roles:
            conn.execute(
                """
                INSERT INTO draft_roles_calibrated(
                    draft_id, role_id, title, market, required_skills_json, evidence_sources_json,
                    role_origin, created_by, created_at, summary, source_occupation_codes_json,
                    department_owner, country_scope, demo_tier, reality_complete, project_coverage_complete
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    role.get("role_id"),
                    role.get("title"),
                    role.get("market_grounding") or role.get("market") or "direct",
                    _json_dump(role.get("required_skills") or []),
                    _json_dump(role.get("evidence_sources") or []),
                    role.get("role_origin") or "",
                    role.get("created_by") or "",
                    role.get("created_at") or "",
                    role.get("summary") or "",
                    _json_dump(role.get("source_occupation_codes") or []),
                    role.get("department_owner") or "",
                    role.get("country_scope") or "USA",
                    role.get("demo_tier") or "extended",
                    int(bool(role.get("reality_complete", False))),
                    int(bool(role.get("project_coverage_complete", False))),
                ),
            )
        conn.commit()
    _mirror_roles_to_legacy_file(draft_id)


def list_draft_roles(
    draft_id: str,
    *,
    query: str | None = None,
    department_owner: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    roles = load_draft_roles(draft_id)
    q = (query or "").strip().lower()
    if q:
        roles = [
            role
            for role in roles
            if q in str(role.get("role_id", "")).lower() or q in str(role.get("title", "")).lower()
        ]
    dept = (department_owner or "").strip().upper()
    if dept:
        roles = [role for role in roles if str(role.get("department_owner") or "").upper() == dept]
    roles.sort(key=lambda item: str(item.get("role_id", "")))
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": roles[start:end],
        "page": page,
        "page_size": page_size,
        "total": len(roles),
    }


def create_role_in_draft(
    draft_id: str,
    payload: dict,
    *,
    username: str,
    store: CatalogStore,
) -> dict:
    roles = load_draft_roles(draft_id)
    role = normalize_role_payload(payload, username=username, store=store, existing_role=None)
    if not can_edit_department(username=username, department_owner=str(role.get("department_owner") or "")):
        raise ValueError(
            f"User '{username}' is not allowed to edit department '{role.get('department_owner')}'."
        )
    if any(str(item.get("role_id")) == role["role_id"] for item in roles):
        raise ValueError(f"role_id already exists in draft: {role['role_id']}")
    roles.append(role)
    roles.sort(key=lambda item: str(item.get("role_id", "")))
    save_draft_roles(draft_id, roles)
    insert_audit_log(
        user=username,
        action="draft_role_create",
        entity="draft_roles_calibrated",
        draft_id=draft_id,
        after_hash=_hash_json(role),
        meta={"role_id": role["role_id"]},
    )
    return role


def update_role_in_draft(
    draft_id: str,
    role_id: str,
    payload: dict,
    *,
    username: str,
    store: CatalogStore,
) -> dict:
    roles = load_draft_roles(draft_id)
    target = next((item for item in roles if str(item.get("role_id")) == role_id), None)
    if target is None:
        raise KeyError(role_id)
    if not can_edit_department(
        username=username,
        department_owner=str(target.get("department_owner") or ""),
    ):
        raise ValueError(
            f"User '{username}' is not allowed to edit department '{target.get('department_owner')}'."
        )
    updated_payload = dict(target)
    updated_payload.update(payload)
    updated = normalize_role_payload(
        updated_payload,
        username=username,
        store=store,
        existing_role=target,
    )
    if updated["role_id"] != role_id and any(
        str(item.get("role_id")) == updated["role_id"] for item in roles
    ):
        raise ValueError(f"role_id already exists in draft: {updated['role_id']}")
    idx = roles.index(target)
    roles[idx] = updated
    roles.sort(key=lambda item: str(item.get("role_id", "")))
    save_draft_roles(draft_id, roles)
    insert_audit_log(
        user=username,
        action="draft_role_update",
        entity="draft_roles_calibrated",
        draft_id=draft_id,
        before_hash=_hash_json(target),
        after_hash=_hash_json(updated),
        meta={"role_id": role_id},
    )
    return updated


def delete_role_in_draft(draft_id: str, role_id: str, *, username: str = "advisor") -> None:
    roles = load_draft_roles(draft_id)
    target = next((item for item in roles if str(item.get("role_id")) == role_id), None)
    if target and not can_edit_department(
        username=username,
        department_owner=str(target.get("department_owner") or ""),
    ):
        raise ValueError(
            f"User '{username}' is not allowed to edit department '{target.get('department_owner')}'."
        )
    filtered = [item for item in roles if str(item.get("role_id")) != role_id]
    if len(filtered) == len(roles):
        raise KeyError(role_id)
    save_draft_roles(draft_id, filtered)
    insert_audit_log(
        user=username,
        action="draft_role_delete",
        entity="draft_roles_calibrated",
        draft_id=draft_id,
        before_hash=_hash_json(target or {"role_id": role_id}),
        meta={"role_id": role_id},
    )


def publish_draft_roles(draft_id: str, *, reviewer: str | None = None) -> dict:
    init_db()
    with connect() as conn:
        draft = conn.execute(
            "SELECT draft_id, created_by, created_at, status FROM drafts WHERE draft_id = ?",
            (draft_id,),
        ).fetchone()
        if draft is None:
            raise FileNotFoundError(f"Draft not found: {draft_id}")

        curated_rows = conn.execute(
            """
            SELECT role_id, skill_id, course_id, note FROM draft_curated_mappings
            WHERE draft_id = ?
            ORDER BY role_id, skill_id, course_id
            """,
            (draft_id,),
        ).fetchall()
        source_rows = conn.execute(
            """
            SELECT source_id, provider, title, url, enabled, trust_weight
            FROM draft_sources
            WHERE draft_id = ?
            ORDER BY source_id
            """,
            (draft_id,),
        ).fetchall()
        role_rows = conn.execute(
            """
            SELECT role_id, title, market, required_skills_json, evidence_sources_json, role_origin,
                   created_by, created_at, summary, source_occupation_codes_json,
                   department_owner, country_scope, demo_tier, reality_complete, project_coverage_complete
            FROM draft_roles_calibrated
            WHERE draft_id = ?
            ORDER BY role_id
            """,
            (draft_id,),
        ).fetchall()

    curated_json = [
        {
            "role_id": row["role_id"],
            "skill_id": row["skill_id"],
            "course_id": row["course_id"],
            "strength": 5,
            "rationale": row["note"] or "",
        }
        for row in curated_rows
    ]
    sources_json = []
    for row in source_rows:
        item = {
            "source_id": row["source_id"],
            "provider": row["provider"] or "",
            "type": "report",
            "title": row["title"] or "",
            "url": row["url"] or "",
            "retrieved_on": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "enabled": int(row["enabled"]),
            "trust_weight": float(row["trust_weight"]),
        }
        sources_json.append(item)

    roles_json = [_row_to_role(row) for row in role_rows]
    readiness_rows = compute_role_readiness_status(
        roles_rows=roles_json,
        sources_rows=sources_json,
        role_reality_rows=_load_processed_json("role_reality_usa.json", default=[]),
        project_template_rows=_load_processed_json("project_templates.json", default=[]),
    )
    readiness_by_role = {row["role_id"]: row for row in readiness_rows}
    blocking = [
        row
        for row in readiness_rows
        if row.get("demo_tier") in {"core", "fusion"} and (
            not row.get("gate1_required_skills_evidence_ok", False)
            or not row.get("gate2_role_reality_ok", False)
            or not row.get("gate3_project_coverage_ok", False)
        )
    ]
    if blocking:
        details = "; ".join(
            f"{row['role_id']}: gates="
            f"{int(row['gate1_required_skills_evidence_ok'])}/"
            f"{int(row['gate2_role_reality_ok'])}/"
            f"{int(row['gate3_project_coverage_ok'])}"
            for row in blocking[:10]
        )
        raise ValueError(
            "Draft publish blocked by readiness gates for demo-tier roles. " + details
        )
    for role in roles_json:
        ready = readiness_by_role.get(role["role_id"])
        if ready:
            role["reality_complete"] = bool(ready["gate2_role_reality_ok"])
            role["project_coverage_complete"] = bool(ready["gate3_project_coverage_ok"])
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_dir = history_root() / f"{timestamp}_{draft_id}"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    _snapshot_if_exists(processed_dir() / "course_skills_curated.json", snapshot_dir)
    _snapshot_if_exists(processed_dir() / "market_sources.json", snapshot_dir)
    _snapshot_if_exists(roles_calibrated_processed_path(), snapshot_dir)
    _snapshot_if_exists(roles_baseline_processed_path(), snapshot_dir)

    _write_json(processed_dir() / "course_skills_curated.json", curated_json)
    _write_json(processed_dir() / "market_sources.json", sources_json)
    _write_json(roles_calibrated_processed_path(), roles_json)

    with connect() as conn:
        conn.execute(
            "UPDATE drafts SET status = ? WHERE draft_id = ?",
            ("published", draft_id),
        )
        conn.commit()

    insert_audit_log(
        user=reviewer or str(draft["created_by"]),
        action="draft_publish",
        entity="draft",
        draft_id=draft_id,
        after_hash=_hash_json({"roles": len(roles_json), "sources": len(sources_json), "curated": len(curated_json)}),
        meta={"history_snapshot_dir": str(snapshot_dir)},
    )
    return {
        "published_file": str(roles_calibrated_processed_path()),
        "history_snapshot_dir": str(snapshot_dir),
        "reload_required": True,
        "readiness_roles_checked": len(readiness_rows),
    }


def create_role_stub_from_request(
    *,
    role_query: str,
    username: str,
    store: CatalogStore,
    draft_id: str | None = None,
) -> tuple[str, str]:
    draft_id = draft_id or create_draft(created_by=username)
    role_id = generate_role_id(role_query)
    title = _title_from_query(role_query)
    payload = {
        "role_id": role_id,
        "title": title,
        "market_grounding": "direct",
        "source_occupation_codes": [],
        "summary": f"Advisor-added role draft for '{title}'.",
        "required_skills": [],
        "evidence_sources": default_evidence_sources(store),
    }
    create_role_in_draft(
        draft_id=draft_id,
        payload=payload,
        username=username,
        store=store,
    )
    return draft_id, role_id


def reload_store() -> CatalogStore:
    return load_catalog_store()


def generate_role_id(role_query: str) -> str:
    norm = normalize_role_query(role_query)
    if not norm:
        norm = "custom_role"
    slug = re.sub(r"[^a-z0-9]+", "_", norm).strip("_")
    slug = slug.upper()[:24] or "CUSTOM_ROLE"
    suffix = hashlib.sha1(norm.encode("utf-8")).hexdigest()[:6].upper()
    return f"ROLE_{slug}_{suffix}"


def normalize_role_payload(
    payload: dict,
    *,
    username: str,
    store: CatalogStore,
    existing_role: dict | None,
) -> dict:
    role_id = str(payload.get("role_id") or "").strip().upper()
    title = str(payload.get("title") or "").strip()
    if not role_id:
        raise ValueError("role_id is required.")
    if not title:
        raise ValueError("title is required.")

    market_grounding = str(payload.get("market_grounding") or payload.get("market") or "direct").strip().lower()
    if market_grounding not in {"direct", "composite"}:
        raise ValueError("market_grounding must be 'direct' or 'composite'.")

    required_skills = []
    valid_skill_ids = {item.skill_id for item in store.skills}
    for row in payload.get("required_skills") or []:
        if not isinstance(row, dict):
            raise ValueError("required_skills must contain objects.")
        skill_id = str(row.get("skill_id") or "").strip()
        if skill_id not in valid_skill_ids:
            raise ValueError(f"Unknown skill_id: {skill_id}")
        weight_raw = row.get("weight", row.get("importance", 3))
        try:
            weight = int(weight_raw)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid skill weight for {skill_id}") from None
        weight = max(1, min(5, weight))
        required_skills.append({"skill_id": skill_id, "importance": weight})

    valid_source_ids = {item.source_id for item in store.sources}
    evidence_sources = []
    for source_id in payload.get("evidence_sources") or []:
        source_id = str(source_id).strip()
        if source_id not in valid_source_ids:
            raise ValueError(f"Unknown source_id: {source_id}")
        evidence_sources.append(source_id)

    created_at = str(payload.get("created_at") or "")
    created_by = str(payload.get("created_by") or "")
    role_origin = str(payload.get("role_origin") or "")
    department_owner = str(payload.get("department_owner") or "").strip().upper()
    country_scope = str(payload.get("country_scope") or "USA").strip().upper() or "USA"
    demo_tier = str(payload.get("demo_tier") or "extended").strip().lower() or "extended"
    if demo_tier not in {"core", "fusion", "extended"}:
        raise ValueError("demo_tier must be one of: core, fusion, extended.")
    reality_complete = bool(payload.get("reality_complete", False))
    project_coverage_complete = bool(payload.get("project_coverage_complete", False))
    if existing_role is None:
        created_at = utc_now()
        created_by = username
        role_origin = "advisor_added"
        if not department_owner:
            department_owner = "EXTENDED"
    else:
        created_at = created_at or str(existing_role.get("created_at") or "")
        created_by = created_by or str(existing_role.get("created_by") or username)
        role_origin = role_origin or str(existing_role.get("role_origin") or "advisor_added")
        department_owner = department_owner or str(existing_role.get("department_owner") or "EXTENDED")
        country_scope = country_scope or str(existing_role.get("country_scope") or "USA")
        demo_tier = demo_tier or str(existing_role.get("demo_tier") or "extended")
        reality_complete = bool(payload.get("reality_complete", existing_role.get("reality_complete", False)))
        project_coverage_complete = bool(
            payload.get("project_coverage_complete", existing_role.get("project_coverage_complete", False))
        )

    return {
        "role_id": role_id,
        "title": title,
        "market_grounding": market_grounding,
        "source_occupation_codes": payload.get("source_occupation_codes") or [],
        "summary": str(payload.get("summary") or ""),
        "required_skills": required_skills,
        "evidence_sources": evidence_sources,
        "role_origin": role_origin,
        "created_by": created_by,
        "created_at": created_at,
        "department_owner": department_owner,
        "country_scope": country_scope,
        "demo_tier": demo_tier,
        "reality_complete": reality_complete,
        "project_coverage_complete": project_coverage_complete,
    }


def default_evidence_sources(store: CatalogStore) -> list[str]:
    source_scores = []
    for source in store.sources:
        provider = source.provider.lower()
        score = 0
        if "bls" in provider:
            score = 100
        elif "o*net" in provider or "onet" in provider:
            score = 90
        elif "university" in provider or "catalog" in provider:
            score = 80
        source_scores.append((score, source.source_id))
    source_scores.sort(key=lambda item: (-item[0], item[1]))
    selected = [source_id for score, source_id in source_scores[:2] if score > 0]
    if not selected and source_scores:
        selected = [source_scores[0][1]]
    return selected


def compute_role_readiness_status(
    *,
    roles_rows: list[dict],
    sources_rows: list[dict],
    role_reality_rows: list[dict],
    project_template_rows: list[dict],
) -> list[dict]:
    source_ids = {
        str(row.get("source_id", "")).strip()
        for row in sources_rows
        if isinstance(row, dict)
    }
    role_reality_by_id = {
        str(row.get("role_id", "")).strip(): row
        for row in role_reality_rows
        if isinstance(row, dict)
    }
    template_skill_ids = {
        str(row.get("skill_id", "")).strip()
        for row in project_template_rows
        if isinstance(row, dict)
    }

    out: list[dict] = []
    for role in roles_rows:
        role_id = str(role.get("role_id", "")).strip()
        required_skills = [
            str(item.get("skill_id", "")).strip()
            for item in (role.get("required_skills") or [])
            if isinstance(item, dict)
        ]
        required_skills = [item for item in required_skills if item]
        evidence_sources = [
            str(item).strip() for item in (role.get("evidence_sources") or []) if str(item).strip()
        ]

        gate1_required_skills_evidence_ok = bool(required_skills) and bool(evidence_sources) and all(
            source_id in source_ids for source_id in evidence_sources
        )

        reality = role_reality_by_id.get(role_id)
        gate2_role_reality_ok = False
        if isinstance(reality, dict):
            reality_sources = [str(item).strip() for item in (reality.get("sources") or []) if str(item).strip()]
            gate2_role_reality_ok = bool(reality_sources) and all(
                source_id in source_ids for source_id in reality_sources
            )

        missing_project_skills = sorted(
            skill_id for skill_id in required_skills if skill_id not in template_skill_ids
        )
        gate3_project_coverage_ok = len(missing_project_skills) == 0

        out.append(
            {
                "role_id": role_id,
                "department_owner": str(role.get("department_owner") or ""),
                "country_scope": str(role.get("country_scope") or "USA"),
                "demo_tier": str(role.get("demo_tier") or "extended"),
                "gate1_required_skills_evidence_ok": gate1_required_skills_evidence_ok,
                "gate2_role_reality_ok": gate2_role_reality_ok,
                "gate3_project_coverage_ok": gate3_project_coverage_ok,
                "missing_project_skills": missing_project_skills,
            }
        )
    out.sort(key=lambda row: row["role_id"])
    return out


def get_draft_role_readiness_status(
    draft_id: str,
    *,
    department_owner: str | None = None,
) -> list[dict]:
    roles = load_draft_roles(draft_id)
    if department_owner:
        dept = department_owner.strip().upper()
        roles = [row for row in roles if str(row.get("department_owner") or "").upper() == dept]
    return compute_role_readiness_status(
        roles_rows=roles,
        sources_rows=_load_processed_json("market_sources.json", default=[]),
        role_reality_rows=_load_processed_json("role_reality_usa.json", default=[]),
        project_template_rows=_load_processed_json("project_templates.json", default=[]),
    )


def is_central_reviewer(username: str) -> bool:
    raw = (os.getenv("SANJAYA_CENTRAL_REVIEWERS", "").strip() or "advisor")
    allowed = {item.strip().lower() for item in raw.split(",") if item.strip()}
    return username.strip().lower() in allowed


def can_edit_department(*, username: str, department_owner: str) -> bool:
    if is_central_reviewer(username):
        return True
    mapping_raw = os.getenv("SANJAYA_DEPARTMENT_STEWARDS_JSON", "").strip()
    if not mapping_raw:
        return True
    try:
        mapping = json.loads(mapping_raw)
    except json.JSONDecodeError:
        return True
    if not isinstance(mapping, dict):
        return True
    dept = department_owner.strip().upper()
    if not dept:
        return False
    users = mapping.get(dept) or []
    if not isinstance(users, list):
        return False
    allowed = {str(item).strip().lower() for item in users if str(item).strip()}
    return username.strip().lower() in allowed


def _new_draft_id() -> str:
    return f"draft_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def _title_from_query(query: str) -> str:
    norm = normalize_role_query(query)
    if not norm:
        return "Custom Role"
    return " ".join(word.capitalize() for word in norm.split())


def _load_processed_json(filename: str, *, default):
    path = processed_dir() / filename
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default
    return payload


def _load_processed_roles_rows() -> list[dict]:
    calibrated = roles_calibrated_processed_path()
    if calibrated.exists():
        rows = _load_processed_json(calibrated.name, default=[])
        if isinstance(rows, list):
            return rows
    rows = _load_processed_json(roles_baseline_processed_path().name, default=[])
    if isinstance(rows, list):
        return rows
    return []


def _mapping_row_id(*, role_id: str, skill_id: str, course_id: str) -> str:
    raw = f"{role_id}|{skill_id}|{course_id}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _row_to_role(row) -> dict:
    return {
        "role_id": row["role_id"],
        "title": row["title"],
        "market_grounding": row["market"] or "direct",
        "source_occupation_codes": _json_load(row["source_occupation_codes_json"], default=[]),
        "summary": row["summary"] or "",
        "required_skills": _json_load(row["required_skills_json"], default=[]),
        "evidence_sources": _json_load(row["evidence_sources_json"], default=[]),
        "role_origin": row["role_origin"] or "",
        "created_by": row["created_by"] or "",
        "created_at": row["created_at"] or "",
        "department_owner": row["department_owner"] or "",
        "country_scope": row["country_scope"] or "USA",
        "demo_tier": row["demo_tier"] or "extended",
        "reality_complete": bool(row["reality_complete"]) if row["reality_complete"] is not None else False,
        "project_coverage_complete": bool(row["project_coverage_complete"]) if row["project_coverage_complete"] is not None else False,
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)


def _snapshot_if_exists(path: Path, snapshot_dir: Path) -> None:
    if path.exists():
        shutil.copyfile(path, snapshot_dir / path.name)


def _mirror_roles_to_legacy_file(draft_id: str) -> None:
    # Optional debug mirror; keeps compatibility with older tests/tools.
    roles = load_draft_roles(draft_id)
    path = draft_roles_path(draft_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(roles, ensure_ascii=True, indent=2), encoding="utf-8")


def _hash_json(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _json_load(value: str | None, *, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default
