#!/usr/bin/env python
"""
Report prerequisite references that are missing from current courses dataset.

Input:
- data/processed/courses.json

Output:
- data/processed/missing_prereqs_report.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


COURSE_ID_RE = re.compile(r"^([A-Z]{2,5})-(\d{3}[A-Z]?)$")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report missing prerequisite references.")
    parser.add_argument("--courses", default="data/processed/courses.json")
    parser.add_argument("--out", default="data/processed/missing_prereqs_report.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    courses = load_json(Path(args.courses))
    existing = {c["course_id"] for c in courses if "course_id" in c}
    total_courses = len(existing)

    missing_refs = defaultdict(list)  # missing_course_id -> list[parent_course_id]

    for c in courses:
        parent = c.get("course_id")
        for prereq in c.get("prerequisites", []):
            if prereq not in existing:
                missing_refs[prereq].append(parent)

    by_department = Counter()
    malformed = []
    for missing_id in missing_refs:
        m = COURSE_ID_RE.match(missing_id)
        if not m:
            malformed.append(missing_id)
            continue
        by_department[m.group(1)] += 1

    top_missing = sorted(
        (
            {
                "missing_course_id": mid,
                "referenced_by_count": len(parents),
                "referenced_by_examples": sorted(set(parents))[:8],
            }
            for mid, parents in missing_refs.items()
        ),
        key=lambda x: (-x["referenced_by_count"], x["missing_course_id"]),
    )

    report = {
        "summary": {
            "total_courses_in_scope": total_courses,
            "unique_missing_prereq_ids": len(missing_refs),
            "total_missing_prereq_references": sum(len(v) for v in missing_refs.values()),
            "malformed_missing_ids": len(malformed),
        },
        "missing_by_department": [
            {"department": dept, "unique_missing_ids": cnt}
            for dept, cnt in sorted(by_department.items(), key=lambda x: (-x[1], x[0]))
        ],
        "malformed_missing_ids": sorted(malformed),
        "top_missing_prereqs": top_missing[:120],
    }

    dump_json(Path(args.out), report)
    print(f"Saved missing prerequisite report to {args.out}")
    print("Summary:", report["summary"])
    print("Top missing departments:", report["missing_by_department"][:10])


if __name__ == "__main__":
    main()
