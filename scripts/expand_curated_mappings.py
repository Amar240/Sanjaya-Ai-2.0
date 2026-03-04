#!/usr/bin/env python
"""
Expand and harden curated role-skill-course mappings.

Goals:
- Preserve existing curated rows.
- Ensure every role-skill pair has curated coverage.
- Improve level-aware coverage by adding UG and GR options when available.
- Reuse curated same-skill precedents when rule-based course_skills lacks a
  good level-specific candidate.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.agents import planner  # noqa: E402
from app.data_loader import load_catalog_store  # noqa: E402


LOW_SIGNAL_TERMS = (
    "SEMINAR",
    "SPECIAL PROBLEM",
    "INDEPENDENT STUDY",
    "INTERNSHIP",
    "THESIS",
    "DISSERTATION",
    "RESEARCH",
)

FOUNDATIONAL_TERMS = (
    "INTERMEDIATE ALGEBRA",
    "PRE-CALCULUS",
    "PRECALCULUS",
    "SURVEY OF",
    "CONTEMPORARY MATHEMATICS",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Expand curated role-skill-course mappings.")
    parser.add_argument(
        "--out",
        default="data/processed/course_skills_curated.json",
        help="Output curated mappings file path.",
    )
    parser.add_argument(
        "--max-per-high-importance",
        type=int,
        default=2,
        help="Minimum curated courses for a skill with importance >= 4.",
    )
    parser.add_argument(
        "--max-per-low-importance",
        type=int,
        default=1,
        help="Minimum curated courses for a skill with importance < 4.",
    )
    parser.add_argument(
        "--ensure-ug",
        action="store_true",
        help="Ensure every role-skill pair has at least one UG course when available.",
    )
    parser.add_argument(
        "--ensure-gr",
        action="store_true",
        help="Ensure every role-skill pair has at least one GR course when available.",
    )
    return parser.parse_args()


def course_number(course_id: str) -> int | None:
    m = re.search(r"-(\d{3})", course_id)
    if not m:
        return None
    return int(m.group(1))


def is_low_signal(title: str) -> bool:
    t = title.upper()
    return any(term in t for term in LOW_SIGNAL_TERMS)


def is_foundational(course_id: str, title: str) -> bool:
    num = course_number(course_id)
    if num is not None and num < 100:
        return True
    t = title.upper()
    return any(term in t for term in FOUNDATIONAL_TERMS)


def level_penalty(course_id: str) -> int:
    num = course_number(course_id)
    if num is None:
        return 3
    if num < 100:
        return 6
    if num <= 299:
        return 0
    if num <= 399:
        return 1
    if num <= 499:
        return 3
    return 4


def _rank_role_skill_candidates(
    role,
    req_skill_id: str,
    *,
    by_skill: dict[str, list[tuple[int, str]]],
    courses_by_id,
    skills_by_id,
) -> list[str]:
    skill = skills_by_id.get(req_skill_id)
    category = skill.category if skill else ""

    scored: list[tuple[float, int, str]] = []
    for strength, course_id in by_skill.get(req_skill_id, []):
        course = courses_by_id.get(course_id)
        if not course:
            continue
        combined = planner._combined_match_score(  # pylint: disable=protected-access
            role_id=role.role_id,
            skill_id=req_skill_id,
            skill_category=category,
            course=course,
            strength=int(strength),
        )
        scored.append((combined, int(strength), course_id))

    scored.sort(
        key=lambda x: (-x[0], -x[1], len(courses_by_id[x[2]].prerequisites), x[2])
    )

    strong = [cid for combined, strength, cid in scored if combined >= 2.5 and strength >= 2]
    ordered = strong + [cid for _, _, cid in scored if cid not in strong]

    deduped: list[str] = []
    seen: set[str] = set()
    for cid in ordered:
        if cid in seen:
            continue
        seen.add(cid)
        deduped.append(cid)

    return deduped


def _select_candidate(
    ranked: list[str],
    used_courses: set[str],
    *,
    preferred_level: str | None,
    skill_id: str,
    courses_by_id,
    strength_index: dict[tuple[str, str], int],
) -> str | None:
    passes = [
        (2, False),
        (2, True),
        (1, True),
    ]

    for min_strength, allow_foundational in passes:
        for cid in ranked:
            if cid in used_courses:
                continue
            course = courses_by_id.get(cid)
            if not course:
                continue
            if preferred_level and course.level != preferred_level:
                continue
            if is_low_signal(course.title):
                continue
            if not allow_foundational and is_foundational(course.course_id, course.title):
                continue
            strength = strength_index.get((cid, skill_id), 0)
            if strength < min_strength:
                continue
            return cid

    return None


def _build_skill_level_fallback(curated_existing, courses_by_id) -> dict[tuple[str, str], list[str]]:
    grouped: dict[tuple[str, str], list[tuple[int, str]]] = defaultdict(list)
    seen: set[tuple[str, str, str]] = set()

    for row in curated_existing:
        course = courses_by_id.get(row.course_id)
        if not course:
            continue
        dedupe_key = (row.skill_id, course.level, row.course_id)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        grouped[(row.skill_id, course.level)].append((int(row.strength), row.course_id))

    out: dict[tuple[str, str], list[str]] = {}
    for key, rows in grouped.items():
        rows_sorted = sorted(
            rows,
            key=lambda x: (-x[0], len(courses_by_id[x[1]].prerequisites), x[1]),
        )
        out[key] = [cid for _, cid in rows_sorted]

    return out


def _select_fallback_course(
    skill_id: str,
    preferred_level: str,
    used_courses: set[str],
    *,
    fallback_by_skill_level: dict[tuple[str, str], list[str]],
    courses_by_id,
) -> str | None:
    for cid in fallback_by_skill_level.get((skill_id, preferred_level), []):
        if cid in used_courses:
            continue
        course = courses_by_id.get(cid)
        if not course:
            continue
        if is_low_signal(course.title):
            continue
        return cid
    return None


def _add_row(
    merged_rows: list[dict],
    *,
    role_id: str,
    role_title: str,
    skill_id: str,
    skill_name: str,
    course_id: str,
    strength: int,
    rationale_suffix: str,
) -> None:
    merged_rows.append(
        {
            "role_id": role_id,
            "skill_id": skill_id,
            "course_id": course_id,
            "strength": int(max(1, min(5, strength))),
            "rationale": (
                f"Auto-curated seed: {rationale_suffix} {skill_name} for {role_title}. "
                "Review recommended."
            ),
        }
    )


def main() -> None:
    args = parse_args()
    out_path = REPO_ROOT / args.out

    store = load_catalog_store()
    courses_by_id = store.courses_by_id
    skills_by_id = {s.skill_id: s for s in store.skills}

    by_skill: dict[str, list[tuple[int, str]]] = defaultdict(list)
    strength_index: dict[tuple[str, str], int] = {}
    for row in store.course_skills:
        by_skill[row.skill_id].append((int(row.strength), row.course_id))
        key = (row.course_id, row.skill_id)
        strength_index[key] = max(strength_index.get(key, 0), int(row.strength))

    curated_existing = list(store.curated_role_skill_courses)
    fallback_by_skill_level = _build_skill_level_fallback(curated_existing, courses_by_id)

    merged_rows = [
        {
            "role_id": row.role_id,
            "skill_id": row.skill_id,
            "course_id": row.course_id,
            "strength": int(row.strength),
            "rationale": row.rationale,
        }
        for row in curated_existing
    ]

    existing_pair_courses: set[tuple[str, str, str]] = {
        (row["role_id"], row["skill_id"], row["course_id"]) for row in merged_rows
    }
    pair_to_courses: dict[tuple[str, str], set[str]] = defaultdict(set)
    pair_to_levels: dict[tuple[str, str], set[str]] = defaultdict(set)

    for row in merged_rows:
        pair = (row["role_id"], row["skill_id"])
        cid = row["course_id"]
        pair_to_courses[pair].add(cid)
        course = courses_by_id.get(cid)
        if course:
            pair_to_levels[pair].add(course.level)

    added_rows = 0

    for role in store.roles:
        for req in role.required_skills:
            pair = (role.role_id, req.skill_id)
            ranked = _rank_role_skill_candidates(
                role,
                req.skill_id,
                by_skill=by_skill,
                courses_by_id=courses_by_id,
                skills_by_id=skills_by_id,
            )

            target_n = (
                args.max_per_high_importance
                if req.importance >= 4
                else args.max_per_low_importance
            )
            skill_name = skills_by_id[req.skill_id].name if req.skill_id in skills_by_id else req.skill_id

            # Ensure minimum per-pair count.
            while len(pair_to_courses[pair]) < target_n:
                candidate = _select_candidate(
                    ranked,
                    pair_to_courses[pair],
                    preferred_level=None,
                    skill_id=req.skill_id,
                    courses_by_id=courses_by_id,
                    strength_index=strength_index,
                )
                if not candidate:
                    break
                key = (role.role_id, req.skill_id, candidate)
                if key in existing_pair_courses:
                    break
                _add_row(
                    merged_rows,
                    role_id=role.role_id,
                    role_title=role.title,
                    skill_id=req.skill_id,
                    skill_name=skill_name,
                    course_id=candidate,
                    strength=strength_index.get((candidate, req.skill_id), 3),
                    rationale_suffix=f"{courses_by_id[candidate].title} aligns with",
                )
                added_rows += 1
                existing_pair_courses.add(key)
                pair_to_courses[pair].add(candidate)
                pair_to_levels[pair].add(courses_by_id[candidate].level)

            # Ensure UG/GR representation when requested and available.
            if args.ensure_ug and "UG" not in pair_to_levels[pair]:
                candidate = _select_candidate(
                    ranked,
                    pair_to_courses[pair],
                    preferred_level="UG",
                    skill_id=req.skill_id,
                    courses_by_id=courses_by_id,
                    strength_index=strength_index,
                )
                if not candidate:
                    candidate = _select_fallback_course(
                        req.skill_id,
                        "UG",
                        pair_to_courses[pair],
                        fallback_by_skill_level=fallback_by_skill_level,
                        courses_by_id=courses_by_id,
                    )
                if candidate:
                    key = (role.role_id, req.skill_id, candidate)
                    if key not in existing_pair_courses:
                        _add_row(
                            merged_rows,
                            role_id=role.role_id,
                            role_title=role.title,
                            skill_id=req.skill_id,
                            skill_name=skill_name,
                            course_id=candidate,
                            strength=strength_index.get((candidate, req.skill_id), 3),
                            rationale_suffix=f"{courses_by_id[candidate].title} provides UG-level coverage for",
                        )
                        added_rows += 1
                        existing_pair_courses.add(key)
                        pair_to_courses[pair].add(candidate)
                        pair_to_levels[pair].add("UG")

            if args.ensure_gr and "GR" not in pair_to_levels[pair]:
                candidate = _select_candidate(
                    ranked,
                    pair_to_courses[pair],
                    preferred_level="GR",
                    skill_id=req.skill_id,
                    courses_by_id=courses_by_id,
                    strength_index=strength_index,
                )
                if not candidate:
                    candidate = _select_fallback_course(
                        req.skill_id,
                        "GR",
                        pair_to_courses[pair],
                        fallback_by_skill_level=fallback_by_skill_level,
                        courses_by_id=courses_by_id,
                    )
                if candidate:
                    key = (role.role_id, req.skill_id, candidate)
                    if key not in existing_pair_courses:
                        _add_row(
                            merged_rows,
                            role_id=role.role_id,
                            role_title=role.title,
                            skill_id=req.skill_id,
                            skill_name=skill_name,
                            course_id=candidate,
                            strength=strength_index.get((candidate, req.skill_id), 3),
                            rationale_suffix=f"{courses_by_id[candidate].title} provides GR-level coverage for",
                        )
                        added_rows += 1
                        existing_pair_courses.add(key)
                        pair_to_courses[pair].add(candidate)
                        pair_to_levels[pair].add("GR")

    merged_rows = sorted(
        merged_rows,
        key=lambda x: (
            x["role_id"],
            x["skill_id"],
            -x["strength"],
            level_penalty(x["course_id"]),
            x["course_id"],
        ),
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(merged_rows, indent=2), encoding="utf-8")

    all_pairs = [
        (role.role_id, req.skill_id)
        for role in store.roles
        for req in role.required_skills
    ]
    covered_pairs = {(row["role_id"], row["skill_id"]) for row in merged_rows}

    pair_levels: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in merged_rows:
        course = courses_by_id.get(row["course_id"])
        if course:
            pair_levels[(row["role_id"], row["skill_id"])].add(course.level)

    missing_any = [pair for pair in all_pairs if pair not in covered_pairs]
    missing_ug = [pair for pair in all_pairs if "UG" not in pair_levels.get(pair, set())]
    missing_gr = [pair for pair in all_pairs if "GR" not in pair_levels.get(pair, set())]

    print(f"Existing curated rows kept: {len(curated_existing)}")
    print(f"Added rows: {added_rows}")
    print(f"Saved merged curated file: {out_path}")
    print(f"Total curated rows: {len(merged_rows)}")
    print(f"Role-skill pairs covered: {len(covered_pairs)}/{len(all_pairs)}")
    print(f"Pairs missing any coverage: {len(missing_any)}")
    print(f"Pairs missing UG coverage: {len(missing_ug)}")
    print(f"Pairs missing GR coverage: {len(missing_gr)}")


if __name__ == "__main__":
    main()
