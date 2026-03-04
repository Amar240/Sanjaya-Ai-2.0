#!/usr/bin/env python
"""
Generate explicit course-to-skill mappings for Sanjaya AI.

Input:
- data/processed/courses.json
- data/processed/skills_market.json
- data/processed/roles_market.json (used to guarantee coverage for required skills)

Output:
- data/processed/course_skills.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

SKILL_HINTS: dict[str, list[str]] = {
    "SK_PYTHON": ["programming", "computer science", "software development"],
    "SK_SQL": ["database", "data management", "data systems"],
    "SK_BACKEND_DEV": ["software engineering", "systems programming", "web applications", "software design"],
    "SK_FRONTEND_DEV": [
        "user interface",
        "graphical user interfaces",
        "web development",
        "javascript",
        "html",
        "css",
        "frontend",
    ],
    "SK_APIS": ["web applications", "integration", "service", "distributed systems"],
    "SK_ML_FUND": ["machine learning", "artificial intelligence", "data mining"],
    "SK_GENAI_BASICS": ["artificial intelligence", "machine learning", "intelligent systems"],
    "SK_MODEL_EVAL": ["statistics", "regression", "inference", "evaluation"],
    "SK_MLOPS": ["cloud", "deployment", "software systems", "pipelines"],
    "SK_ETL": ["data pipeline", "data integration", "database", "big data"],
    "SK_DATA_WAREHOUSE": ["database", "data platform", "analytics"],
    "SK_DEVOPS": ["cloud", "deployment", "software systems", "automation"],
    "SK_CONTAINERIZATION": [
        "container",
        "containers",
        "docker",
        "kubernetes",
        "orchestration",
        "cloud native",
    ],
    "SK_LINUX": ["linux", "unix", "command line", "shell", "operating systems"],
    "SK_SECURITY_FUND": ["security", "cybersecurity", "information security"],
    "SK_NETWORK_SECURITY": ["network security", "security", "network"],
    "SK_APP_SECURITY": ["software security", "secure coding", "security"],
    "SK_INCIDENT_RESPONSE": ["security", "risk", "threat", "response"],
}

STRICT_SKILL_KEYWORDS: dict[str, list[str]] = {
    "SK_SQL": [
        "sql",
        "structured query language",
        "database",
        "relational",
        "query",
        "data warehouse",
    ],
    "SK_DATA_VIZ": [
        "visualization",
        "dashboard",
        "tableau",
        "power bi",
        "data viz",
        "chart",
    ],
    "SK_BI_TOOLS": [
        "tableau",
        "power bi",
        "business intelligence",
        "dashboard",
        "reporting",
    ],
}

FOUNDATIONAL_TITLE_TERMS = (
    "INTERMEDIATE ALGEBRA",
    "PRE-CALCULUS",
    "PRECALCULUS",
    "SURVEY OF",
    "CONTEMPORARY MATHEMATICS",
)

APPLIED_BUSINESS_DATA_SKILLS = {
    "SK_SQL",
    "SK_BUSINESS_ANALYSIS",
    "SK_DATA_VIZ",
    "SK_BI_TOOLS",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def course_number(course_id: str) -> int | None:
    m = re.search(r"-(\d{3})", course_id)
    if not m:
        return None
    return int(m.group(1))


def has_phrase_signal(text: str, phrases: list[str]) -> bool:
    return any(phrase.lower() in text for phrase in phrases)


def is_foundational_course(course: dict) -> bool:
    title = str(course.get("title", "")).upper()
    course_id = str(course.get("course_id", ""))
    num = course_number(course_id)
    if num is not None and num < 100:
        return True
    return any(term in title for term in FOUNDATIONAL_TITLE_TERMS)


def score_course_for_skill(course: dict, skill: dict) -> float:
    text = f"{course.get('title', '')} {course.get('description', '')}".lower()
    tokens = tokenize(text)
    score = 0.0
    skill_id = skill.get("skill_id", "")

    name = skill.get("name", "").strip().lower()
    aliases = [a.strip().lower() for a in skill.get("aliases", []) if a.strip()]
    phrases = [name] + aliases

    if name and name in text:
        score += 3.6
    for alias in aliases:
        if alias in text:
            score += 2.2

    for phrase in phrases:
        pt = tokenize(phrase)
        if not pt:
            continue
        overlap = len(tokens & pt) / len(pt)
        if overlap >= 1.0:
            score += 1.8
        elif overlap >= 0.6:
            score += 0.9
        elif overlap >= 0.4:
            score += 0.35

    for hint in SKILL_HINTS.get(skill_id, []):
        hint_lower = hint.lower()
        if hint_lower in text:
            score += 1.1
            continue
        hint_tokens = tokenize(hint_lower)
        if not hint_tokens:
            continue
        overlap = len(tokens & hint_tokens) / len(hint_tokens)
        if overlap >= 1.0:
            score += 0.9
        elif overlap >= 0.5:
            score += 0.4

    dept = course.get("department", "")
    category = skill.get("category", "")
    cnum = course_number(str(course.get("course_id", "")))
    tech_departments = {"CISC", "BINF", "MISY", "STAT", "MATH"}
    if category in {
        "Programming",
        "Software Engineering",
        "Computer Science Fundamentals",
        "Data",
        "Data Engineering",
        "Machine Learning",
        "Cloud and DevOps",
        "Cybersecurity",
        "Analytics",
        "Math and Analytics",
    } and dept in tech_departments:
        score += 0.5

    if category == "Fusion Domain: Finance" and dept in {"ACCT", "FINC", "ECON", "BUAD"}:
        score += 0.7
    if category == "Fusion Domain: Biology" and dept in {"BINF", "BISC", "CHEM"}:
        score += 0.7
    if category == "Fusion Domain: Chemistry" and dept in {"CHEM", "BINF"}:
        score += 0.7

    # Guardrails to reduce noisy matches on broad/foundational courses.
    strict_phrases = STRICT_SKILL_KEYWORDS.get(skill_id, [])
    if strict_phrases and not has_phrase_signal(text, strict_phrases):
        score -= 2.8

    if skill_id in APPLIED_BUSINESS_DATA_SKILLS and is_foundational_course(course):
        score -= 2.4

    if skill_id in APPLIED_BUSINESS_DATA_SKILLS and dept in {"MATH", "STAT"} and cnum is not None and cnum < 200:
        score -= 2.0

    if skill_id == "SK_BUSINESS_ANALYSIS":
        if dept in {"MATH", "STAT"} and not has_phrase_signal(
            text,
            ["business", "management", "operations", "decision", "market", "policy"],
        ):
            score -= 1.8

    return score


def score_to_strength(score: float) -> int:
    if score >= 6.0:
        return 5
    if score >= 4.5:
        return 4
    if score >= 3.3:
        return 3
    if score >= 2.5:
        return 2
    return 1


def required_skill_ids(roles: list[dict]) -> set[str]:
    ids = set()
    for role in roles:
        for req in role.get("required_skills", []):
            sid = req.get("skill_id")
            if sid:
                ids.add(sid)
    return ids


def generate(
    courses: list[dict],
    skills: list[dict],
    roles: list[dict],
    score_threshold: float,
    top_per_course: int,
    fallback_top_per_skill: int,
) -> list[dict]:
    skill_by_id = {s["skill_id"]: s for s in skills}
    best_by_skill: dict[str, list[tuple[float, str]]] = defaultdict(list)
    mapping_strength: dict[tuple[str, str], int] = {}

    for course in courses:
        course_id = course["course_id"]
        scored: list[tuple[float, str]] = []
        for skill in skills:
            sid = skill["skill_id"]
            score = score_course_for_skill(course, skill)
            best_by_skill[sid].append((score, course_id))
            if score >= score_threshold:
                scored.append((score, sid))

        scored.sort(key=lambda x: (-x[0], x[1]))
        for score, sid in scored[:top_per_course]:
            pair = (course_id, sid)
            strength = score_to_strength(score)
            prev = mapping_strength.get(pair, 0)
            if strength > prev:
                mapping_strength[pair] = strength

    required = required_skill_ids(roles)
    mapped_required = {sid for (_, sid) in mapping_strength}
    missing_required = sorted(required - mapped_required)

    for sid in missing_required:
        candidates = sorted(best_by_skill.get(sid, []), key=lambda x: (-x[0], x[1]))
        added = 0
        for score, course_id in candidates:
            if score < 0.3:
                continue
            pair = (course_id, sid)
            strength = max(1, score_to_strength(score))
            prev = mapping_strength.get(pair, 0)
            if strength > prev:
                mapping_strength[pair] = strength
                added += 1
            if added >= fallback_top_per_skill:
                break

    out = [
        {
            "course_id": course_id,
            "skill_id": sid,
            "strength": strength,
        }
        for (course_id, sid), strength in sorted(mapping_strength.items(), key=lambda x: (x[0][0], x[0][1]))
    ]
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate explicit course-skill mappings.")
    parser.add_argument("--courses", default="data/processed/courses.json")
    parser.add_argument("--skills", default="data/processed/skills_market.json")
    parser.add_argument("--roles", default="data/processed/roles_market.json")
    parser.add_argument("--out", default="data/processed/course_skills.json")
    parser.add_argument("--score-threshold", type=float, default=2.2)
    parser.add_argument("--top-per-course", type=int, default=6)
    parser.add_argument("--fallback-top-per-skill", type=int, default=4)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    courses = load_json(Path(args.courses))
    skills = load_json(Path(args.skills))
    roles = load_json(Path(args.roles))

    mappings = generate(
        courses=courses,
        skills=skills,
        roles=roles,
        score_threshold=args.score_threshold,
        top_per_course=args.top_per_course,
        fallback_top_per_skill=args.fallback_top_per_skill,
    )

    dump_json(Path(args.out), mappings)

    skill_coverage = defaultdict(int)
    for row in mappings:
        skill_coverage[row["skill_id"]] += 1
    required = required_skill_ids(roles)
    uncovered_required = sorted([sid for sid in required if skill_coverage[sid] == 0])

    print(f"Saved {len(mappings)} course-skill mappings to {args.out}")
    print(f"Skills with >=1 mapped course: {sum(1 for v in skill_coverage.values() if v > 0)}")
    print(f"Required skills uncovered: {len(uncovered_required)}")
    if uncovered_required:
        print("Uncovered required skills:", ", ".join(uncovered_required))


if __name__ == "__main__":
    main()
