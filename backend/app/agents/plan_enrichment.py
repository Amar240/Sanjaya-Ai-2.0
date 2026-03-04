from __future__ import annotations

from collections import Counter

from ..data_loader import CatalogStore
from ..schemas.plan import (
    DepartmentContext,
    FusionPackSummary,
    PlanRequest,
    PlanResponse,
    ReadinessFactor,
    ReadinessSummary,
)


def enrich_plan_outputs(
    *,
    plan: PlanResponse,
    request: PlanRequest,
    store: CatalogStore,
) -> None:
    plan.department_context = build_department_context(plan=plan, store=store)
    plan.readiness_summary = build_readiness_summary(plan=plan)
    if request.student_profile.mode == "FUSION":
        plan.fusion_pack_summary = build_fusion_pack_summary(plan=plan, store=store)


def build_readiness_summary(*, plan: PlanResponse) -> ReadinessSummary:
    total_skills = len(plan.skill_coverage)
    covered_skills = sum(1 for item in plan.skill_coverage if item.covered)
    coverage_ratio = (covered_skills / total_skills) if total_skills else 0.0

    warnings = 0
    for error in plan.validation_errors:
        severity = str(error.details.get("severity", "")).lower() if error.details else ""
        if severity == "warning" or (severity != "error" and error.code not in {
            "COURSE_NOT_FOUND",
            "PREREQ_ORDER",
            "CREDIT_OVER_MAX",
            "LEVEL_MISMATCH",
        }):
            warnings += 1

    missing_skill_count = len(plan.gap_report.missing_skills) if plan.gap_report else 0
    missing_with_projects = 0
    if plan.gap_report:
        missing_with_projects = sum(
            1 for item in plan.gap_report.missing_skills if item.recommended_projects
        )
    project_cover_ratio = (
        (missing_with_projects / missing_skill_count) if missing_skill_count else 1.0
    )

    warning_health = 1.0 - min(1.0, warnings / 6.0)
    score = (coverage_ratio * 0.6) + (warning_health * 0.2) + (project_cover_ratio * 0.2)

    if score >= 0.8 and warnings <= 2:
        band = "Market-Ready Track"
    elif score >= 0.55:
        band = "Developing"
    else:
        band = "Early"

    factors = [
        ReadinessFactor(
            name="skill_coverage_ratio",
            value=round(coverage_ratio, 4),
            description=f"{covered_skills}/{total_skills} required skills currently covered.",
        ),
        ReadinessFactor(
            name="warning_health",
            value=round(warning_health, 4),
            description=f"{warnings} unresolved warnings currently flagged.",
        ),
        ReadinessFactor(
            name="project_gap_coverage_ratio",
            value=round(project_cover_ratio, 4),
            description=(
                f"{missing_with_projects}/{missing_skill_count} missing skills have "
                "project recommendations."
            ),
        ),
    ]
    return ReadinessSummary(
        readiness_band=band,
        score=round(max(0.0, min(1.0, score)), 4),
        factors=factors,
        unresolved_warning_count=warnings,
        missing_skill_count=missing_skill_count,
    )


def build_department_context(*, plan: PlanResponse, store: CatalogStore) -> DepartmentContext:
    course_by_id = {course.course_id: course for course in store.courses}
    department_counts: Counter[str] = Counter()

    for mapping in store.curated_role_skill_courses:
        if mapping.role_id != plan.selected_role_id:
            continue
        course = course_by_id.get(mapping.course_id)
        if course:
            department_counts[course.department] += 1

    if not department_counts:
        for semester in plan.semesters:
            for course_id in semester.courses:
                course = course_by_id.get(course_id)
                if course:
                    department_counts[course.department] += 1

    if not department_counts:
        return DepartmentContext(primary_department="", supporting_departments=[])

    ranked = sorted(department_counts.items(), key=lambda item: (-item[1], item[0]))
    primary = ranked[0][0]
    supporting = [dept for dept, _ in ranked[1:4]]
    return DepartmentContext(
        primary_department=primary,
        supporting_departments=supporting,
    )


def build_fusion_pack_summary(
    *,
    plan: PlanResponse,
    store: CatalogStore,
) -> FusionPackSummary | None:
    if not store.fusion_packs_usa:
        return None

    selected_id = plan.selected_role_id
    selected = next(
        (pack for pack in store.fusion_packs_usa if selected_id in pack.target_roles),
        None,
    )
    if selected is None:
        candidate_ids = {item.role_id for item in plan.candidate_roles[:5]}
        ranked = []
        for pack in store.fusion_packs_usa:
            overlap = len(candidate_ids.intersection(set(pack.target_roles)))
            ranked.append((overlap, pack.fusion_pack_id, pack))
        ranked.sort(key=lambda row: (-row[0], row[1]))
        selected = ranked[0][2] if ranked and ranked[0][0] > 0 else None
    if selected is None:
        return None
    return FusionPackSummary(
        fusion_pack_id=selected.fusion_pack_id,
        title=selected.title,
        domain_a=selected.domain_a,
        domain_b=selected.domain_b,
        target_roles=list(selected.target_roles),
        unlock_skills=list(selected.unlock_skills),
        starter_projects=list(selected.starter_projects),
        evidence_sources=list(selected.evidence_sources),
    )
