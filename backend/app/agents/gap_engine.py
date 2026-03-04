from __future__ import annotations

import os
from typing import Literal

from ..data_loader import CatalogStore
from ..schemas.plan import PlanResponse
from ..schemas.reality import CoveredSkillItem, GapReport, MissingSkillItem, ProjectTemplateRef

_LEVEL_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2}
_ALL_LEVELS: list[Literal["beginner", "intermediate", "advanced"]] = [
    "beginner",
    "intermediate",
    "advanced",
]


def build_gap_report(
    plan: PlanResponse,
    store: CatalogStore,
    *,
    confidence_level: str = "medium",
    hours_per_week: int = 6,
) -> GapReport:
    skills_by_id = {item.skill_id: item for item in store.skills}
    templates_by_skill: dict[str, list] = {}
    for template in store.project_templates:
        templates_by_skill.setdefault(template.skill_id, []).append(template)

    top_n = _projects_per_skill()
    allowed_levels = _base_allowed_levels(confidence_level)
    hours_cap = _hours_preference_cap(hours_per_week)
    missing: list[MissingSkillItem] = []
    covered: list[CoveredSkillItem] = []
    for item in plan.skill_coverage:
        skill_name = (
            skills_by_id[item.required_skill_id].name
            if item.required_skill_id in skills_by_id
            else item.required_skill_id
        )
        if item.covered:
            covered.append(
                CoveredSkillItem(
                    skill_id=item.required_skill_id,
                    skill_name=skill_name,
                    matched_courses=list(item.matched_courses),
                )
            )
            continue
        templates = list(templates_by_skill.get(item.required_skill_id, []))
        filtered, expanded_levels = _filter_templates_with_fallback(templates, allowed_levels)
        expanded_rank = {level: idx for idx, level in enumerate(expanded_levels)}
        filtered.sort(
            key=lambda row: (
                expanded_rank.get(row.level, _LEVEL_ORDER.get(row.level, 99)),
                _fits_bucket_rank(time_hours=int(row.time_hours), hours_cap=hours_cap),
                int(row.time_hours),
                row.template_id,
            )
        )
        refs = [
            ProjectTemplateRef(
                template_id=template.template_id,
                title=template.title,
                level=template.level,
                time_hours=template.time_hours,
                effort_fit=_effort_fit_label(
                    time_hours=int(template.time_hours),
                    hours_per_week=hours_per_week,
                ),
                deliverables=list(template.deliverables[:3]),
            )
            for template in filtered[:top_n]
        ]
        missing.append(
            MissingSkillItem(
                skill_id=item.required_skill_id,
                skill_name=skill_name,
                reason="Required role skill is not currently covered by planned/completed courses.",
                recommended_projects=refs,
            )
        )
    missing.sort(key=lambda row: row.skill_id)
    covered.sort(key=lambda row: row.skill_id)
    return GapReport(missing_skills=missing, covered_skills=covered)


def _projects_per_skill(default_value: int = 2) -> int:
    raw = os.getenv("SANJAYA_PROJECTS_PER_SKILL", "").strip()
    if not raw:
        return default_value
    try:
        parsed = int(raw)
    except ValueError:
        return default_value
    return max(1, min(5, parsed))


def _base_allowed_levels(confidence_level: str) -> list[str]:
    normalized = confidence_level.strip().lower()
    if normalized == "low":
        return ["beginner"]
    if normalized == "high":
        return ["beginner", "intermediate", "advanced"]
    return ["beginner", "intermediate"]


def _filter_templates_with_fallback(
    templates: list,
    allowed_levels: list[str],
) -> tuple[list, list[str]]:
    if not templates:
        return [], list(allowed_levels)
    expanded_levels = list(allowed_levels)
    filtered = [item for item in templates if item.level in expanded_levels]
    if filtered:
        return filtered, expanded_levels

    for level in _ALL_LEVELS:
        if level in expanded_levels:
            continue
        expanded_levels.append(level)
        filtered = [item for item in templates if item.level in expanded_levels]
        if filtered:
            return filtered, expanded_levels
    return list(templates), expanded_levels


def _hours_preference_cap(hours_per_week: int) -> int | None:
    if hours_per_week <= 4:
        return 8
    if 5 <= hours_per_week <= 8:
        return 12
    return None


def _fits_bucket_rank(*, time_hours: int, hours_cap: int | None) -> int:
    if hours_cap is None:
        return 0
    return 0 if time_hours <= hours_cap else 1


def _effort_fit_label(*, time_hours: int, hours_per_week: int) -> Literal["fits", "stretch", "heavy"]:
    if time_hours <= max(0, hours_per_week) * 2:
        return "fits"
    if time_hours <= max(0, hours_per_week) * 4:
        return "stretch"
    return "heavy"
