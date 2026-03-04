from __future__ import annotations

import hashlib
import json

from ..schemas.plan import PlanRequest


def compute_plan_id(request: PlanRequest, data_version: str) -> str:
    payload = {
        "preferred_role_id": request.preferred_role_id,
        "requested_role_text": (request.requested_role_text or "").strip().lower() or None,
        "student_profile": {
            "level": request.student_profile.level,
            "mode": request.student_profile.mode,
            "goal_type": request.student_profile.goal_type,
            "confidence_level": request.student_profile.confidence_level,
            "hours_per_week": int(request.student_profile.hours_per_week),
            "fusion_domain": request.student_profile.fusion_domain,
            "current_semester": int(request.student_profile.current_semester),
            "start_term": request.student_profile.start_term,
            "include_optional_terms": bool(request.student_profile.include_optional_terms),
            "completed_courses": sorted(set(request.student_profile.completed_courses)),
            "min_credits": int(request.student_profile.min_credits),
            "target_credits": int(request.student_profile.target_credits),
            "max_credits": int(request.student_profile.max_credits),
            "degree_total_credits": getattr(
                request.student_profile, "degree_total_credits", None
            ),
            "interests": sorted(set(request.student_profile.interests)),
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{data_version}|{canonical}".encode("utf-8")).hexdigest()
    return digest[:16]
