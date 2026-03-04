#!/usr/bin/env python
"""
Validate normalized courses.json for Sanjaya AI constraints.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

COURSE_ID_RE = re.compile(r"^[A-Z]{2,5}-\d{3}[A-Z]?$")


def load_courses(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(courses: list[dict]) -> list[str]:
    errors: list[str] = []
    ids: set[str] = set()

    for idx, c in enumerate(courses):
        at = f"index={idx}"
        cid = c.get("course_id")

        if not cid:
            errors.append(f"{at}: missing course_id")
            continue

        if not COURSE_ID_RE.match(cid):
            errors.append(f"{at}: malformed course_id '{cid}'")

        if cid in ids:
            errors.append(f"{at}: duplicate course_id '{cid}'")
        ids.add(cid)

        if not c.get("title"):
            errors.append(f"{cid}: missing title")

        credits = c.get("credits")
        if not isinstance(credits, (int, float)):
            errors.append(f"{cid}: credits must be numeric")
        elif credits <= 0 or credits > 8:
            errors.append(f"{cid}: suspicious credits '{credits}'")

        _validate_course_id_list(c, cid, "prerequisites", errors)
        _validate_course_id_list(c, cid, "corequisites", errors)
        _validate_course_id_list(c, cid, "antirequisites", errors)

        if not c.get("source_url"):
            errors.append(f"{cid}: missing source_url")

    return errors


def _validate_course_id_list(
    course: dict,
    course_id: str,
    field_name: str,
    errors: list[str],
) -> None:
    values = course.get(field_name, [])
    if not isinstance(values, list):
        errors.append(f"{course_id}: {field_name} must be a list")
        return
    for value in values:
        if not COURSE_ID_RE.match(value):
            errors.append(f"{course_id}: malformed {field_name[:-1]} '{value}'")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate courses.json")
    parser.add_argument("--input", default="data/processed/courses.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    path = Path(args.input)
    courses = load_courses(path)
    errors = validate(courses)

    if errors:
        print("Validation failed:")
        for e in errors:
            print(f"- {e}")
        sys.exit(1)

    print(f"Validation passed for {len(courses)} courses: {path}")


if __name__ == "__main__":
    main()
