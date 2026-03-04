#!/usr/bin/env python
"""
Validate data/processed/course_skills.json integrity.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate course_skills.json")
    parser.add_argument("--input", default="data/processed/course_skills.json")
    parser.add_argument("--courses", default="data/processed/courses.json")
    parser.add_argument("--skills", default="data/processed/skills_market.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mappings = load_json(Path(args.input))
    courses = load_json(Path(args.courses))
    skills = load_json(Path(args.skills))

    course_ids = {c["course_id"] for c in courses}
    skill_ids = {s["skill_id"] for s in skills}
    errors: list[str] = []
    seen_pairs = set()

    if not isinstance(mappings, list):
        print("Validation failed: mapping file is not a JSON array.")
        sys.exit(1)

    for ix, row in enumerate(mappings):
        at = f"index={ix}"
        course_id = row.get("course_id")
        skill_id = row.get("skill_id")
        strength = row.get("strength")

        if not course_id or not skill_id:
            errors.append(f"{at}: missing course_id or skill_id")
            continue

        pair = (course_id, skill_id)
        if pair in seen_pairs:
            errors.append(f"{at}: duplicate mapping {course_id}/{skill_id}")
        seen_pairs.add(pair)

        if course_id not in course_ids:
            errors.append(f"{at}: unknown course_id '{course_id}'")
        if skill_id not in skill_ids:
            errors.append(f"{at}: unknown skill_id '{skill_id}'")

        if not isinstance(strength, int):
            errors.append(f"{at}: strength must be integer")
        elif strength < 1 or strength > 5:
            errors.append(f"{at}: strength out of range (1..5)")

    if errors:
        print("Validation failed:")
        for err in errors[:200]:
            print("-", err)
        if len(errors) > 200:
            print(f"... and {len(errors) - 200} more errors")
        sys.exit(1)

    print(
        f"Validation passed for {len(mappings)} mappings "
        f"(courses={len(course_ids)}, skills={len(skill_ids)})."
    )


if __name__ == "__main__":
    main()
