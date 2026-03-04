#!/usr/bin/env python
"""
Calibrate role skill importance from role-skill evidence confidence + source breadth.

Inputs:
- data/processed/roles_market.json
- data/processed/role_skill_evidence.json

Outputs:
- data/processed/roles_market_calibrated.json
- data/processed/role_importance_calibration_report.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def to_importance(score_0_to_1: float) -> int:
    if score_0_to_1 >= 0.86:
        return 5
    if score_0_to_1 >= 0.68:
        return 4
    if score_0_to_1 >= 0.50:
        return 3
    if score_0_to_1 >= 0.34:
        return 2
    return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calibrate role importance from evidence.")
    parser.add_argument("--roles", default="data/processed/roles_market.json")
    parser.add_argument("--evidence", default="data/processed/role_skill_evidence.json")
    parser.add_argument("--out", default="data/processed/roles_market_calibrated.json")
    parser.add_argument(
        "--report",
        default="data/processed/role_importance_calibration_report.json",
    )
    return parser.parse_args()


def build_evidence_index(evidence_rows: list[dict]) -> dict[tuple[str, str], dict]:
    index: dict[tuple[str, str], dict] = {}
    for row in evidence_rows:
        key = (row.get("role_id"), row.get("skill_id"))
        if key not in index:
            index[key] = {
                "max_confidence": 0.0,
                "sources": set(),
                "entries": 0,
            }
        bucket = index[key]
        bucket["max_confidence"] = max(bucket["max_confidence"], float(row.get("confidence", 0.0)))
        bucket["sources"].update(row.get("evidence_sources", []))
        bucket["entries"] += 1
    return index


def calibrate(
    roles: list[dict],
    evidence_index: dict[tuple[str, str], dict],
) -> tuple[list[dict], list[dict]]:
    report_rows: list[dict] = []
    calibrated_roles = json.loads(json.dumps(roles))

    for role in calibrated_roles:
        role_id = role.get("role_id")
        for req in role.get("required_skills", []):
            skill_id = req.get("skill_id")
            current = int(req.get("importance", 3))
            key = (role_id, skill_id)
            ev = evidence_index.get(key)

            if ev:
                source_count = len(ev["sources"])
                confidence = float(ev["max_confidence"])
                source_score = min(source_count, 3) / 3.0

                # Blend evidence with current manual judgment for stability.
                evidence_raw = confidence * 0.80 + source_score * 0.20
                blended = evidence_raw * 0.70 + (current / 5.0) * 0.30
                calibrated = to_importance(blended)
                method = "evidence_blend"
            else:
                source_count = 0
                confidence = None
                blended = current / 5.0
                calibrated = current
                method = "no_evidence_keep_current"

            req["importance"] = int(calibrated)

            report_rows.append(
                {
                    "role_id": role_id,
                    "skill_id": skill_id,
                    "old_importance": current,
                    "new_importance": calibrated,
                    "delta": calibrated - current,
                    "evidence_max_confidence": confidence,
                    "evidence_source_count": source_count,
                    "method": method,
                }
            )

    return calibrated_roles, report_rows


def main() -> None:
    args = parse_args()
    roles = load_json(Path(args.roles))
    evidence = load_json(Path(args.evidence))

    evidence_index = build_evidence_index(evidence)
    calibrated_roles, report_rows = calibrate(roles, evidence_index)

    dump_json(Path(args.out), calibrated_roles)
    summary = {
        "total_role_skill_rows": len(report_rows),
        "changed_rows": sum(1 for r in report_rows if r["delta"] != 0),
        "increased_rows": sum(1 for r in report_rows if r["delta"] > 0),
        "decreased_rows": sum(1 for r in report_rows if r["delta"] < 0),
        "unchanged_rows": sum(1 for r in report_rows if r["delta"] == 0),
    }
    dump_json(
        Path(args.report),
        {
            "summary": summary,
            "rows": report_rows,
        },
    )

    print(f"Saved calibrated roles to {args.out}")
    print(f"Saved calibration report to {args.report}")
    print("Summary:", summary)


if __name__ == "__main__":
    main()
