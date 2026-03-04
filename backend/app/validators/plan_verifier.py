from __future__ import annotations

from collections import defaultdict
import re

from ..schemas.catalog import Course, CourseSkillMapping, CuratedRoleSkillCourse, RoleMarket
from ..schemas.plan import PlanError, PlanRequest, PlanResponse, PlanSemester, SkillCoverage


def verify_plan(
    request: PlanRequest,
    role: RoleMarket,
    semesters: list[PlanSemester],
    courses_by_id: dict[str, Course],
    skill_coverage: list[SkillCoverage],
    all_courses_by_id: dict[str, Course],
    course_skills: list[CourseSkillMapping],
    curated_role_skill_courses: list[CuratedRoleSkillCourse],
    plan: PlanResponse | None = None,
) -> tuple[list[PlanError], list[str], list[PlanSemester]]:
    errors: list[PlanError] = []
    notes: list[str] = []

    _verify_course_existence(semesters, courses_by_id, errors)
    _verify_duplicate_courses(semesters, errors)
    _verify_level_and_offering(request, semesters, courses_by_id, errors)
    _verify_antirequisite_conflicts(semesters, courses_by_id, errors)
    _verify_corequisite_alignment(semesters, courses_by_id, errors)
    _verify_prerequisites(request, semesters, courses_by_id, errors, notes)
    _verify_credit_rules(request, semesters, errors)
    _verify_skill_coverage(role, skill_coverage, notes, errors)
    _verify_skill_level_availability(
        request=request,
        role=role,
        all_courses_by_id=all_courses_by_id,
        course_skills=course_skills,
        curated_role_skill_courses=curated_role_skill_courses,
        notes=notes,
    )
    if plan is not None:
        errors.extend(check_evidence_integrity(plan))

    return errors, notes, semesters


def check_evidence_integrity(plan: PlanResponse) -> list[PlanError]:
    warnings: list[PlanError] = []
    allowed_skill_ids = {item.required_skill_id for item in plan.skill_coverage}
    evidence_ids_in_panel = {item.evidence_id for item in plan.evidence_panel}
    evidence_counts: dict[str, int] = defaultdict(int)

    for item in plan.evidence_panel:
        evidence_counts[item.evidence_id] += 1
        if item.role_id != plan.selected_role_id:
            warnings.append(
                PlanError(
                    code="EVIDENCE_INTEGRITY_VIOLATION",
                    message=(
                        f"Evidence '{item.evidence_id}' role '{item.role_id}' does not match selected role "
                        f"'{plan.selected_role_id}'."
                    ),
                    details={
                        "severity": "warning",
                        "kind": "role_mismatch",
                        "evidence_id": item.evidence_id,
                        "expected_role": plan.selected_role_id,
                        "got_role": item.role_id,
                    },
                )
            )
        if item.skill_id not in allowed_skill_ids:
            warnings.append(
                PlanError(
                    code="EVIDENCE_INTEGRITY_VIOLATION",
                    message=(
                        f"Evidence '{item.evidence_id}' skill '{item.skill_id}' is not in plan skill coverage."
                    ),
                    details={
                        "severity": "warning",
                        "kind": "skill_not_in_plan",
                        "evidence_id": item.evidence_id,
                        "skill_id": item.skill_id,
                    },
                )
            )

    for evidence_id, count in sorted(evidence_counts.items()):
        if count > 1:
            warnings.append(
                PlanError(
                    code="EVIDENCE_INTEGRITY_VIOLATION",
                    message=f"Duplicate evidence_id '{evidence_id}' detected in evidence panel.",
                    details={
                        "severity": "warning",
                        "kind": "duplicate_evidence_id",
                        "evidence_id": evidence_id,
                        "count": count,
                    },
                )
            )

    for card in plan.course_purpose_cards:
        for item in card.evidence:
            if item.evidence_id not in evidence_ids_in_panel:
                warnings.append(
                    PlanError(
                        code="EVIDENCE_INTEGRITY_VIOLATION",
                        message=(
                            f"Course '{card.course_id}' references evidence '{item.evidence_id}' "
                            "that is not present in evidence panel."
                        ),
                        course_id=card.course_id,
                        details={
                            "severity": "warning",
                            "kind": "card_evidence_not_in_panel",
                            "course_id": card.course_id,
                            "evidence_id": item.evidence_id,
                        },
                    )
                )

    return warnings


def _verify_course_existence(
    semesters: list[PlanSemester],
    courses_by_id: dict[str, Course],
    errors: list[PlanError],
) -> None:
    for sem in semesters:
        for course_id in sem.courses:
            if course_id not in courses_by_id:
                errors.append(
                    PlanError(
                        code="COURSE_NOT_FOUND",
                        message=(
                            f"Semester {sem.semester_index}: course '{course_id}' does not exist in course catalog."
                        ),
                        course_id=course_id,
                        term=sem.term,
                        details={"semester_index": sem.semester_index},
                    )
                )


def _verify_duplicate_courses(
    semesters: list[PlanSemester],
    errors: list[PlanError],
) -> None:
    occurrences: dict[str, list[dict[str, str | int]]] = defaultdict(list)
    for sem in semesters:
        for course_id in sem.courses:
            occurrences[course_id].append(
                {"semester_index": sem.semester_index, "term": sem.term}
            )

    for course_id, slots in sorted(occurrences.items()):
        if len(slots) <= 1:
            continue
        errors.append(
            PlanError(
                code="DUPLICATE_COURSE",
                message=f"Course '{course_id}' appears in multiple semesters.",
                course_id=course_id,
                details={
                    "severity": "error",
                    "count": len(slots),
                    "occurrences": slots,
                },
            )
        )


def _verify_level_and_offering(
    request: PlanRequest,
    semesters: list[PlanSemester],
    courses_by_id: dict[str, Course],
    errors: list[PlanError],
) -> None:
    for sem in semesters:
        for course_id in sem.courses:
            course = courses_by_id.get(course_id)
            if not course:
                continue
            if course.level != request.student_profile.level:
                errors.append(
                    PlanError(
                        code="LEVEL_MISMATCH",
                        message=(
                            f"Semester {sem.semester_index}: course '{course_id}' level {course.level} "
                            f"does not match student level {request.student_profile.level}."
                        ),
                        course_id=course_id,
                        term=sem.term,
                        details={
                            "semester_index": sem.semester_index,
                            "course_level": course.level,
                            "student_level": request.student_profile.level,
                        },
                    )
                )
            offered_terms = {
                normalized
                for raw in course.offered_terms
                if (normalized := _normalize_term_label(raw))
            }
            sem_term = _normalize_term_label(sem.term)
            if offered_terms and sem_term not in offered_terms:
                errors.append(
                    PlanError(
                        code="OFFERING_MISMATCH",
                        message=(
                            f"Semester {sem.semester_index}: course '{course_id}' is not offered in {sem.term}."
                        ),
                        course_id=course_id,
                        term=sem.term,
                        details={
                            "semester_index": sem.semester_index,
                            "offered_terms": sorted(offered_terms),
                        },
                    )
                )


def _verify_antirequisite_conflicts(
    semesters: list[PlanSemester],
    courses_by_id: dict[str, Course],
    errors: list[PlanError],
) -> None:
    scheduled = _course_occurrences(semesters)
    scheduled_ids = set(scheduled.keys())
    emitted_pairs: set[tuple[str, str]] = set()

    for course_id in sorted(scheduled_ids):
        course = courses_by_id.get(course_id)
        if not course:
            continue
        for antireq_id in sorted(set(course.antirequisites)):
            if antireq_id not in scheduled_ids:
                continue
            pair = tuple(sorted((course_id, antireq_id)))
            if pair in emitted_pairs:
                continue
            emitted_pairs.add(pair)
            errors.append(
                PlanError(
                    code="ANTIREQ_CONFLICT",
                    message=(
                        f"Antirequisite conflict: '{pair[0]}' and '{pair[1]}' are both scheduled."
                    ),
                    course_id=pair[0],
                    prereq_id=pair[1],
                    details={
                        "severity": "warning",
                        "course_a": pair[0],
                        "course_b": pair[1],
                    },
                )
            )


def _verify_corequisite_alignment(
    semesters: list[PlanSemester],
    courses_by_id: dict[str, Course],
    errors: list[PlanError],
) -> None:
    scheduled = _course_occurrences(semesters)
    for course_id in sorted(scheduled.keys()):
        course = courses_by_id.get(course_id)
        if not course or not course.corequisites:
            continue
        course_semesters = {slot["semester_index"] for slot in scheduled[course_id]}
        for coreq_id in sorted(set(course.corequisites)):
            coreq_slots = scheduled.get(coreq_id, [])
            if not coreq_slots:
                errors.append(
                    PlanError(
                        code="COREQ_NOT_SATISFIED",
                        message=(
                            f"Corequisite '{coreq_id}' for '{course_id}' is not scheduled."
                        ),
                        course_id=course_id,
                        prereq_id=coreq_id,
                        details={
                            "severity": "warning",
                            "kind": "coreq_missing",
                            "course_id": course_id,
                            "coreq_id": coreq_id,
                        },
                    )
                )
                continue
            coreq_semesters = {slot["semester_index"] for slot in coreq_slots}
            if course_semesters & coreq_semesters:
                continue
            errors.append(
                PlanError(
                    code="COREQ_NOT_SATISFIED",
                    message=(
                        f"Corequisite '{coreq_id}' for '{course_id}' is not scheduled in the same term."
                    ),
                    course_id=course_id,
                    prereq_id=coreq_id,
                    details={
                        "severity": "warning",
                        "kind": "coreq_not_same_term",
                        "course_id": course_id,
                        "coreq_id": coreq_id,
                    },
                )
            )


def _verify_prerequisites(
    request: PlanRequest,
    semesters: list[PlanSemester],
    courses_by_id: dict[str, Course],
    errors: list[PlanError],
    notes: list[str],
) -> None:
    completed = set(request.student_profile.completed_courses)
    external_count = 0
    complex_flagged: set[str] = set()

    for sem in semesters:
        for course_id in sem.courses:
            course = courses_by_id.get(course_id)
            if not course:
                continue

            if course_id not in complex_flagged and _has_complex_prereq_logic(course.prerequisites_text):
                complex_flagged.add(course_id)
                errors.append(
                    PlanError(
                        code="PREREQ_COMPLEX_UNSUPPORTED",
                        message=(
                            f"Semester {sem.semester_index}: course '{course_id}' has complex prerequisite "
                            "logic that may be partially represented by parsed prerequisite IDs."
                        ),
                        course_id=course_id,
                        term=sem.term,
                        details={
                            "semester_index": sem.semester_index,
                            "severity": "warning",
                        },
                    )
                )

            for prereq in course.prerequisites:
                if prereq in completed:
                    continue
                if prereq not in courses_by_id:
                    external_count += 1
                    errors.append(
                        PlanError(
                            code="PREREQ_EXTERNAL_REF",
                            message=(
                                f"Semester {sem.semester_index}: '{course_id}' has external prerequisite "
                                f"'{prereq}' not in current dataset scope."
                            ),
                            course_id=course_id,
                            prereq_id=prereq,
                            term=sem.term,
                            details={
                                "semester_index": sem.semester_index,
                                "severity": "warning",
                            },
                        )
                    )
                    continue
                errors.append(
                    PlanError(
                        code="PREREQ_ORDER",
                        message=(
                            f"Semester {sem.semester_index}: prerequisite '{prereq}' not satisfied before "
                            f"'{course_id}'."
                        ),
                        course_id=course_id,
                        prereq_id=prereq,
                        term=sem.term,
                        details={"semester_index": sem.semester_index},
                    )
                )
        completed.update(sem.courses)

    # Plan-specific summary is more useful than global catalog-level counts.
    notes.append(f"Plan-specific external prerequisite references: {external_count}.")


def _verify_credit_rules(
    request: PlanRequest,
    semesters: list[PlanSemester],
    errors: list[PlanError],
) -> None:
    policy = _credit_policy(request.student_profile.level)
    min_credits = request.student_profile.min_credits
    for sem in semesters:
        total = sem.total_credits
        is_optional_term = sem.term in {"Summer", "Winter"}
        if min_credits > 0 and total < min_credits:
            errors.append(
                PlanError(
                    code="CREDITS_BELOW_MIN",
                    message=(
                        f"Semester {sem.semester_index}: planned credits {total} are below "
                        f"min_credits {min_credits}."
                    ),
                    term=sem.term,
                    details={
                        "severity": "warning",
                        "semester_index": sem.semester_index,
                        "planned_credits": total,
                        "min_credits": min_credits,
                    },
                )
            )
        if total < policy["full_time_min"] and not is_optional_term:
            sem.warnings.append(
                f"Below full-time minimum ({policy['full_time_min']} credits)."
            )
        if total > policy["normal_max"]:
            overload_msg = (
                "Advisor approval required for overload."
                if request.student_profile.level == "UG"
                else "Over typical graduate load; advisor approval recommended."
            )
            sem.warnings.append(overload_msg)
        if total > request.student_profile.max_credits:
            errors.append(
                PlanError(
                    code="CREDIT_OVER_MAX",
                    message=(
                        f"Semester {sem.semester_index}: planned credits {total} exceed "
                        f"max_credits {request.student_profile.max_credits}."
                    ),
                    term=sem.term,
                    details={
                        "semester_index": sem.semester_index,
                        "planned_credits": total,
                        "max_credits": request.student_profile.max_credits,
                    },
                )
            )

    degree_total = getattr(
        request.student_profile, "degree_total_credits", None
    )
    if degree_total is not None:
        plan_total = sum(sem.total_credits for sem in semesters)
        if plan_total > degree_total:
            errors.append(
                PlanError(
                    code="TOTAL_CREDITS_OVER_DEGREE",
                    message=(
                        f"Plan total is {plan_total:.0f} credits; degree allows {degree_total}."
                    ),
                    details={
                        "severity": "error",
                        "plan_total_credits": plan_total,
                        "degree_total_credits": degree_total,
                    },
                )
            )
        elif plan_total < 0.8 * degree_total:
            errors.append(
                PlanError(
                    code="TOTAL_CREDITS_UNDER_DEGREE",
                    message=(
                        f"Plan total is {plan_total:.0f} credits; degree typically requires {degree_total}."
                    ),
                    details={
                        "severity": "warning",
                        "plan_total_credits": plan_total,
                        "degree_total_credits": degree_total,
                    },
                )
            )


def _verify_skill_coverage(
    role: RoleMarket,
    skill_coverage: list[SkillCoverage],
    notes: list[str],
    errors: list[PlanError],
) -> None:
    uncovered = [s.required_skill_id for s in skill_coverage if not s.covered]
    if uncovered:
        notes.append(
            f"Role '{role.role_id}' has {len(uncovered)} uncovered required skills in current plan: {', '.join(uncovered)}."
        )
        for skill_id in uncovered:
            errors.append(
                PlanError(
                    code="SKILL_GAP",
                    message=f"Required skill '{skill_id}' is uncovered in current plan.",
                    details={
                        "role_id": role.role_id,
                        "required_skill_id": skill_id,
                        "severity": "warning",
                    },
                )
            )


def _verify_skill_level_availability(
    request: PlanRequest,
    role: RoleMarket,
    all_courses_by_id: dict[str, Course],
    course_skills: list[CourseSkillMapping],
    curated_role_skill_courses: list[CuratedRoleSkillCourse],
    notes: list[str],
) -> None:
    curated_levels_by_skill: dict[str, set[str]] = defaultdict(set)
    for row in curated_role_skill_courses:
        if row.role_id != role.role_id:
            continue
        course = all_courses_by_id.get(row.course_id)
        if course:
            curated_levels_by_skill[row.skill_id].add(course.level)

    fallback_levels_by_skill: dict[str, set[str]] = defaultdict(set)
    for row in course_skills:
        course = all_courses_by_id.get(row.course_id)
        if course:
            fallback_levels_by_skill[row.skill_id].add(course.level)

    ug_only_skills: list[str] = []
    gr_only_skills: list[str] = []
    for req in role.required_skills:
        levels = curated_levels_by_skill.get(req.skill_id)
        if not levels:
            levels = fallback_levels_by_skill.get(req.skill_id, set())

        if not levels:
            notes.append(
                f"Required skill '{req.skill_id}' has no mapped courses in current dataset."
            )
            continue

        if levels == {"UG"}:
            ug_only_skills.append(req.skill_id)
        elif levels == {"GR"}:
            gr_only_skills.append(req.skill_id)

    if ug_only_skills:
        notes.append(
            "Skill-level mapping constraint (UG-only): "
            + ", ".join(sorted(ug_only_skills))
            + "."
        )
    if gr_only_skills:
        notes.append(
            "Skill-level mapping constraint (GR-only): "
            + ", ".join(sorted(gr_only_skills))
            + "."
        )

    if request.student_profile.level == "UG" and gr_only_skills:
        notes.append(
            "UG planning impact: GR-only mapped skills may remain uncovered until graduate-level study or mapping updates."
        )
    if request.student_profile.level == "GR" and ug_only_skills:
        notes.append(
            "GR planning impact: some skills currently map only to UG courses; confirm policy with advisor/program."
        )


def _has_complex_prereq_logic(prerequisites_text: str) -> bool:
    text = (prerequisites_text or "").strip()
    if not text:
        return False
    lower = text.lower()
    if any(token in lower for token in ("permission of instructor", "consent of instructor", "equivalent")):
        return True
    if "one of" in lower:
        return True
    if re.search(r"\(.+\)", text) and " and " in lower and " or " in lower:
        return True
    return False


def _course_occurrences(semesters: list[PlanSemester]) -> dict[str, list[dict[str, str | int]]]:
    out: dict[str, list[dict[str, str | int]]] = defaultdict(list)
    for sem in semesters:
        for course_id in sem.courses:
            out[course_id].append({"semester_index": sem.semester_index, "term": sem.term})
    return out


def _credit_policy(level: str) -> dict[str, int]:
    if level == "GR":
        return {"full_time_min": 9, "normal_max": 12}
    return {"full_time_min": 12, "normal_max": 17}


def _normalize_term_label(value: str) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return ""
    if raw.startswith("fall") or raw.startswith("autumn"):
        return "Fall"
    if raw.startswith("spring"):
        return "Spring"
    if raw.startswith("summer"):
        return "Summer"
    if raw.startswith("winter"):
        return "Winter"
    return value.strip().title()
