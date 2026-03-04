#!/usr/bin/env python
"""
Normalize raw scraped UD courses into Sanjaya AI courses schema.

Input: data/raw/courses_raw.json
Output: data/processed/courses.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

COURSE_CODE_RE = re.compile(r"\b([A-Z]{2,5})\s*[- ]?\s*(\d{3}[A-Z]?)\b")
CREDITS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:credit|credits|cr\.?\b)", re.IGNORECASE)
PREREQ_SPLIT_RE = re.compile(r"[;,]|\bor\b|\band\b", re.IGNORECASE)
PREREQ_LABELS = ["PREREQ", "PREREQUISITE", "PREREQUISITES"]
COREQ_LABELS = ["COREQ", "COREQUISITE", "COREQUISITES"]
ANTIREQ_LABELS = ["ANTIREQ", "ANTIREQUISITE", "ANTIREQUISITES"]
STOP_LABELS = [
    "PREREQ",
    "PREREQUISITE",
    "PREREQUISITES",
    "COREQ",
    "COREQUISITE",
    "COREQUISITES",
    "ANTIREQ",
    "ANTIREQUISITE",
    "ANTIREQUISITES",
    "RESTRICTIONS",
    "CROSSLISTED",
    "COURSE TYPICALLY OFFERED",
    "GENERAL EDUCATION OBJECTIVES",
    "REPEATABLE FOR CREDIT",
    "ALLOWED UNITS",
    "MULTIPLE TERM ENROLLMENT",
    "GRADING BASIS",
    "UNIVERSITY BREADTH",
    "COLLEGE OF ARTS AND SCIENCES BREADTH",
    "REQUIREMENT DESIGNATIONS",
    "CAPSTONE",
    "COMPONENT",
    "CREDIT(S)",
    "CREDITS",
]
NOISE_PATTERNS = [
    re.compile(r"HELP\s+\d{4}-\d{4}\s+(Undergraduate|Graduate)\s+Catalog", re.IGNORECASE),
    re.compile(r"Print-Friendly Page\s*\(opens a new window\)", re.IGNORECASE),
    re.compile(r"Print-Friendly Page", re.IGNORECASE),
    re.compile(r"Facebook this Page\s*\(opens a new window\)", re.IGNORECASE),
    re.compile(r"Facebook this Page", re.IGNORECASE),
    re.compile(r"Tweet this Page\s*\(opens a new window\)", re.IGNORECASE),
    re.compile(r"Tweet this Page", re.IGNORECASE),
    re.compile(r"Back to Top", re.IGNORECASE),
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_course_id(text: str, fallback_dept: str) -> str | None:
    m = COURSE_CODE_RE.search(text)
    if not m:
        return None
    dept, num = m.group(1), m.group(2)
    return f"{dept}-{num}" if dept else f"{fallback_dept}-{num}"


def parse_title(header: str, body: str) -> str:
    header = re.sub(r"\s+", " ", header).strip()
    m = re.search(r"\d{3}[A-Z]?\s*[-:]?\s*(.+)$", header)
    if m:
        return m.group(1).strip(" .")[:200]

    body_line = body.split(".")[0]
    body_line = re.sub(r"\s+", " ", body_line).strip()
    return body_line[:120] if body_line else "Untitled Course"


def parse_credits(text: str) -> float | int:
    m = CREDITS_RE.search(text)
    if not m:
        return 3
    val = float(m.group(1))
    return int(val) if val.is_integer() else val


def extract_section_text(body: str, labels: list[str]) -> str:
    if not body:
        return ""
    label_regex = "|".join(re.escape(x) for x in labels)
    stop_regex = "|".join(re.escape(x) for x in STOP_LABELS)
    pattern = re.compile(
        rf"(?:{label_regex})\s*[:\.]?\s*(.+?)(?=(?:{stop_regex})\s*[:\.]?|$)",
        flags=re.IGNORECASE,
    )
    parts = [m.group(1).strip() for m in pattern.finditer(body) if m.group(1).strip()]
    return " ".join(parts)


def extract_course_codes(text: str) -> list[str]:
    if not text:
        return []
    codes = set()
    for match in COURSE_CODE_RE.finditer(text.upper()):
        dept, num = match.group(1), match.group(2)
        codes.add(f"{dept}-{num}")
    return sorted(codes)


def parse_requirement_sections(
    prereq_text: str,
    body: str,
) -> tuple[list[str], str, list[str], str, list[str], str]:
    prereq_from_body = extract_section_text(body, PREREQ_LABELS)
    if prereq_text:
        prereq_combined = f"{prereq_from_body} {prereq_text}".strip()
    else:
        prereq_combined = prereq_from_body
    prereq_clean = clean_body_text(prereq_combined)[:500]
    prereqs = extract_course_codes(prereq_clean)

    coreq_clean = clean_body_text(extract_section_text(body, COREQ_LABELS))[:500]
    coreqs = extract_course_codes(coreq_clean)

    antireq_clean = clean_body_text(extract_section_text(body, ANTIREQ_LABELS))[:500]
    antireqs = extract_course_codes(antireq_clean)

    return prereqs, prereq_clean, coreqs, coreq_clean, antireqs, antireq_clean


def parse_offered_terms(body: str) -> list[str]:
    offered_text = extract_section_text(body, ["COURSE TYPICALLY OFFERED"])
    offered_text = clean_body_text(offered_text)
    terms = []
    for term in ["Fall", "Winter", "Spring", "Summer"]:
        if re.search(rf"\b{term}\b", offered_text, flags=re.IGNORECASE):
            terms.append(term)
    return terms


def clean_body_text(text: str) -> str:
    cleaned = text
    for pat in NOISE_PATTERNS:
        cleaned = pat.sub(" ", cleaned)
    cleaned = re.sub(r"\s*\|\s*", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def infer_level(source_url: str) -> str:
    # UD current catalogs: catoid=94 undergrad, catoid=93 graduate.
    if "catoid=93" in source_url:
        return "GR"
    return "UG"


def normalize(input_path: Path, output_path: Path) -> None:
    raw = load_json(input_path)
    courses = raw.get("courses", [])
    normalized = []
    seen_ids = set()

    for item in courses:
        header = item.get("raw_header", "")
        body = clean_body_text(item.get("raw_body", ""))
        dept = item.get("department_hint", "GEN")
        source_url = item.get("source_url", "")

        course_id = parse_course_id(f"{header} {body}", dept)
        if not course_id or course_id in seen_ids:
            continue
        seen_ids.add(course_id)

        prereqs, prereq_text, coreqs, coreq_text, antireqs, antireq_text = (
            parse_requirement_sections(item.get("raw_prerequisites", ""), body)
        )
        offered_terms = parse_offered_terms(body)

        record = {
            "course_id": course_id,
            "title": parse_title(header, body),
            "department": course_id.split("-")[0],
            "level": infer_level(source_url),
            "credits": parse_credits(f"{header} {body}"),
            "description": body[:1200],
            "topics": [],
            "prerequisites": prereqs,
            "prerequisites_text": prereq_text,
            "corequisites": coreqs,
            "corequisites_text": coreq_text,
            "antirequisites": antireqs,
            "antirequisites_text": antireq_text,
            "offered_terms": offered_terms,
            "source_url": source_url,
        }
        normalized.append(record)

    dump_json(output_path, normalized)
    print(f"Saved {len(normalized)} normalized courses to {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize raw UD course data")
    parser.add_argument("--input", default="data/raw/courses_raw.json")
    parser.add_argument("--output", default="data/processed/courses.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    normalize(Path(args.input), Path(args.output))


if __name__ == "__main__":
    main()
