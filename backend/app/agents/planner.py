from __future__ import annotations

from collections import defaultdict
import re

from ..data_loader import CatalogStore
from ..schemas.catalog import (
    Course,
    CourseSkillMapping,
    CuratedRoleSkillCourse,
    FusionRoleProfile,
    RoleMarket,
    SkillMarket,
)
from ..schemas.plan import (
    FusionReadiness,
    FusionSummary,
    FusionUnlockSkillStatus,
    PlanRequest,
    PlanResponse,
    PlanSemester,
    SkillCoverage,
)
from ..validators.plan_verifier import verify_plan


def build_plan(request: PlanRequest, store: CatalogStore) -> PlanResponse:
    role = _select_role(request, store)
    policy = _credit_policy(request.student_profile.level)
    filtered_courses = _level_filtered_courses(store.courses, request.student_profile.level)
    courses_by_id = {c.course_id: c for c in filtered_courses}
    skills_by_id = {s.skill_id: s for s in store.skills}

    skill_matches, curated_skills_used = _match_courses_to_role_skills(
        role=role,
        course_skills=store.course_skills,
        curated_role_skill_courses=store.curated_role_skill_courses,
        courses_by_id=courses_by_id,
        skills_by_id=skills_by_id,
    )
    curated_course_ids = {
        row.course_id
        for row in store.curated_role_skill_courses
        if row.role_id == role.role_id and row.course_id in courses_by_id
    }
    course_skill_contribution = _build_course_skill_contribution(role, skill_matches)
    target_courses = _select_target_courses(role, skill_matches, courses_by_id)
    expanded_targets = _expand_with_prereqs(target_courses, courses_by_id)
    supplemental_pool, supplemental_relevance = _build_supplemental_pool(
        role=role,
        skill_matches=skill_matches,
        expanded_targets=expanded_targets,
        courses_by_id=courses_by_id,
        level=request.student_profile.level,
    )

    semesters, planned_course_ids, unscheduled_course_ids = _schedule_semesters(
        expanded_targets=expanded_targets,
        target_courses=target_courses,
        supplemental_pool=supplemental_pool,
        supplemental_relevance=supplemental_relevance,
        courses_by_id=courses_by_id,
        role_id=role.role_id,
        curated_course_ids=curated_course_ids,
        course_skill_contribution=course_skill_contribution,
        completed_courses=set(request.student_profile.completed_courses),
        start_term=request.student_profile.start_term,
        include_optional_terms=request.student_profile.include_optional_terms,
        level=request.student_profile.level,
        min_credits=request.student_profile.min_credits,
        target_credits=request.student_profile.target_credits,
        max_credits=request.student_profile.max_credits,
        degree_total_credits=getattr(
            request.student_profile, "degree_total_credits", None
        ),
    )

    skill_coverage = _build_skill_coverage(
        role=role,
        skill_matches=skill_matches,
        completed_courses=set(request.student_profile.completed_courses),
        planned_courses=planned_course_ids,
    )

    validation_errors, verification_notes, semesters = verify_plan(
        request=request,
        role=role,
        semesters=semesters,
        courses_by_id=courses_by_id,
        skill_coverage=skill_coverage,
        all_courses_by_id=store.courses_by_id,
        course_skills=store.course_skills,
        curated_role_skill_courses=store.curated_role_skill_courses,
    )

    notes = [
        "Planner uses market-grounded roles and UD course catalog constraints.",
        f"Credit policy applied: full-time minimum {policy['full_time_min']}, normal max {policy['normal_max']}.",
    ]
    if curated_skills_used:
        notes.append(
            f"Curated mappings used for {len(curated_skills_used)} role skills: "
            f"{', '.join(sorted(curated_skills_used))}."
        )
    if unscheduled_course_ids:
        notes.append(
            f"{len(unscheduled_course_ids)} target/prerequisite courses could not be scheduled in current horizon."
        )
    notes.extend(store.warnings)
    notes.extend(verification_notes)

    response = PlanResponse(
        selected_role_id=role.role_id,
        selected_role_title=role.title,
        skill_coverage=skill_coverage,
        semesters=semesters,
        validation_errors=validation_errors,
        notes=notes,
    )
    if request.student_profile.mode == "FUSION":
        fusion_summary = _build_fusion_summary(
            role=role,
            skill_coverage=skill_coverage,
            fusion_profiles=store.fusion_role_profiles,
        )
        if fusion_summary:
            response.fusion_summary = fusion_summary
            response.notes.append(
                "Fusion mode readiness is rule-based and explainable (no prediction model)."
            )
        else:
            response.notes.append(
                "Fusion mode requested, but no fusion profile exists for selected role."
            )
    return response


def _select_role(request: PlanRequest, store: CatalogStore) -> RoleMarket:
    if request.preferred_role_id:
        role = store.roles_by_id.get(request.preferred_role_id)
        if role:
            return role
    return store.roles[0]


def _level_filtered_courses(courses: list[Course], level: str) -> list[Course]:
    if level == "GR":
        return [c for c in courses if c.level in {"UG", "GR"}]
    return [c for c in courses if c.level == "UG"]


def _match_courses_to_role_skills(
    role: RoleMarket,
    course_skills: list[CourseSkillMapping],
    curated_role_skill_courses: list[CuratedRoleSkillCourse],
    courses_by_id: dict[str, Course],
    skills_by_id: dict[str, SkillMarket],
) -> tuple[dict[str, list[str]], set[str]]:
    by_skill: dict[str, list[tuple[int, str]]] = defaultdict(list)
    curated_by_skill: dict[str, list[tuple[int, str]]] = defaultdict(list)
    valid_course_ids = set(courses_by_id.keys())

    for row in course_skills:
        if row.course_id not in valid_course_ids:
            continue
        by_skill[row.skill_id].append((row.strength, row.course_id))

    for row in curated_role_skill_courses:
        if row.role_id != role.role_id:
            continue
        if row.course_id not in valid_course_ids:
            continue
        curated_by_skill[row.skill_id].append((row.strength, row.course_id))

    matches: dict[str, list[str]] = {}
    curated_skills_used: set[str] = set()
    for req in role.required_skills:
        skill = skills_by_id.get(req.skill_id)
        category = skill.category if skill else ""
        scored = sorted(
            [
                (
                    _combined_match_score(
                        role_id=role.role_id,
                        skill_id=req.skill_id,
                        skill_category=category,
                        course=courses_by_id[course_id],
                        strength=strength,
                    ),
                    strength,
                    course_id,
                )
                for strength, course_id in by_skill.get(req.skill_id, [])
            ],
            key=lambda x: (-x[0], -x[1], len(courses_by_id[x[2]].prerequisites), x[2]),
        )
        strong = [course_id for combined, strength, course_id in scored if combined >= 2.5 and strength >= 2]
        if strong:
            heuristic = strong[:12]
        else:
            heuristic = [course_id for combined, _, course_id in scored if combined >= 0][:12]

        curated_entries = sorted(
            curated_by_skill.get(req.skill_id, []),
            key=lambda x: (-x[0], len(courses_by_id[x[1]].prerequisites), x[1]),
        )
        curated = []
        for _, cid in curated_entries:
            if cid not in curated:
                curated.append(cid)

        if curated:
            curated_skills_used.add(req.skill_id)
            matches[req.skill_id] = curated[:12]
        else:
            matches[req.skill_id] = heuristic

    return matches, curated_skills_used


def _combined_match_score(
    role_id: str,
    skill_id: str,
    skill_category: str,
    course: Course,
    strength: int,
) -> float:
    preferred = _preferred_departments(role_id, skill_category)
    dept_bonus = 1.2 if course.department in preferred else -1.2
    score = float(strength) + dept_bonus + _skill_department_bias(skill_id, course.department)

    if _is_low_signal_course(course):
        score -= 2.0

    course_num = _course_number(course.course_id)
    analytical_roles = {
        "ROLE_OPERATIONS_RESEARCH_ANALYST",
        "ROLE_STATISTICIAN",
        "ROLE_ACTUARIAL_ANALYST",
        "ROLE_FINANCIAL_RISK_SPECIALIST",
        "ROLE_MARKET_RESEARCH_ANALYST",
        "ROLE_DATA_ANALYST",
    }
    if role_id in {
        "ROLE_SOFTWARE_ENGINEER",
        "ROLE_DATA_ENGINEER",
        "ROLE_ML_ENGINEER",
        "ROLE_AI_ENGINEER",
        "ROLE_CYBERSECURITY_ANALYST",
    }:
        if course_num and course_num < 100:
            score -= 1.5
        elif course_num and 200 <= course_num <= 499:
            score += 0.4
    if role_id in analytical_roles:
        if course_num and course_num < 100:
            score -= 2.1
        elif course_num and 200 <= course_num <= 499:
            score += 0.3
    if _is_foundational_course(course):
        score -= 1.6
    return score


def _skill_department_bias(skill_id: str, department: str) -> float:
    if skill_id == "SK_BUSINESS_ANALYSIS":
        if department in {"MISY", "BUAD", "ECON", "FINC", "ACCT"}:
            return 1.3
        if department in {"MATH", "STAT"}:
            return -1.2
    if skill_id == "SK_SQL":
        if department in {"MISY", "CISC", "BINF"}:
            return 1.0
        if department in {"MATH", "STAT"}:
            return -0.8
    if skill_id == "SK_DATA_VIZ":
        if department in {"BUAD", "MISY", "STAT", "CISC"}:
            return 0.8
    return 0.0


def _preferred_departments(role_id: str, skill_category: str) -> set[str]:
    core_tech = {"CISC", "BINF", "MISY", "STAT", "MATH"}
    finance = {"ACCT", "FINC", "ECON", "BUAD", "STAT", "MATH", "MISY", "CISC"}
    biology = {"BINF", "BISC", "CHEM", "STAT", "CISC", "MATH"}
    chemistry = {"CHEM", "BINF", "CISC", "MATH", "STAT"}
    policy = {"ECON", "BUAD", "MISY", "STAT", "CISC", "MATH"}
    operations = {"BUAD", "ECON", "MISY", "STAT", "MATH", "CISC"}
    health_informatics = {"BINF", "BISC", "CHEM", "MISY", "STAT", "CISC", "MATH"}
    statistics = {"STAT", "MATH", "CISC", "MISY", "ECON"}
    product_analytics = {"MISY", "BUAD", "CISC", "STAT", "MATH", "ECON"}

    if skill_category == "Fusion Domain: Finance":
        return finance
    if skill_category == "Fusion Domain: Biology":
        return biology
    if skill_category == "Fusion Domain: Chemistry":
        return chemistry
    if skill_category == "Fusion Domain: Policy":
        return policy

    if role_id in {
        "ROLE_SOFTWARE_ENGINEER",
        "ROLE_DATA_ENGINEER",
        "ROLE_ML_ENGINEER",
        "ROLE_AI_ENGINEER",
        "ROLE_CYBERSECURITY_ANALYST",
        "ROLE_CLOUD_SECURITY_ENGINEER",
        "ROLE_COMPUTER_SYSTEMS_ANALYST",
        "ROLE_DIGITAL_FORENSICS_ANALYST",
        "ROLE_PRIVACY_ENGINEER",
    }:
        return core_tech
    if role_id in {
        "ROLE_QUANT_RISK_ANALYST",
        "ROLE_FINANCIAL_RISK_SPECIALIST",
        "ROLE_ACTUARIAL_ANALYST",
        "ROLE_FINTECH_ENGINEER",
    }:
        return finance
    if role_id in {"ROLE_OPERATIONS_RESEARCH_ANALYST", "ROLE_SUPPLY_CHAIN_ANALYTICS_SPECIALIST"}:
        return operations
    if role_id in {"ROLE_MARKET_RESEARCH_ANALYST", "ROLE_AI_PRODUCT_MANAGER"}:
        return product_analytics
    if role_id == "ROLE_BIOINFORMATICS_SCIENTIST":
        return biology
    if role_id == "ROLE_HEALTH_INFORMATICS_ANALYST":
        return health_informatics
    if role_id == "ROLE_STATISTICIAN":
        return statistics
    return core_tech


def _course_number(course_id: str) -> int | None:
    m = re.search(r"-(\d{3})", course_id)
    if not m:
        return None
    return int(m.group(1))


def _select_target_courses(
    role: RoleMarket,
    skill_matches: dict[str, list[str]],
    courses_by_id: dict[str, Course],
) -> set[str]:
    targets: set[str] = set()
    prereq_cache: dict[str, set[str]] = {}
    for req in role.required_skills:
        matched = [cid for cid in skill_matches.get(req.skill_id, []) if cid in courses_by_id]
        if not matched:
            continue
        overlap = [cid for cid in matched if cid in targets]
        primary_candidates = overlap if overlap else matched
        primary = _choose_accessible_course(
            primary_candidates,
            courses_by_id,
            prereq_cache,
            role_id=role.role_id,
            skill_id=req.skill_id,
        )
        if primary:
            targets.add(primary)
        if req.importance >= 5 and len(matched) > 1:
            remaining = [cid for cid in matched if cid != primary]
            secondary = _choose_accessible_course(
                remaining,
                courses_by_id,
                prereq_cache,
                role_id=role.role_id,
                skill_id=req.skill_id,
            )
            if secondary:
                targets.add(secondary)
    return targets


def _expand_with_prereqs(target_courses: set[str], courses_by_id: dict[str, Course]) -> set[str]:
    expanded = set(target_courses)
    queue = list(target_courses)
    while queue:
        current = queue.pop()
        course = courses_by_id.get(current)
        if not course:
            continue
        for prereq in course.prerequisites:
            if prereq in courses_by_id and prereq not in expanded:
                expanded.add(prereq)
                queue.append(prereq)
    return expanded


def _build_course_skill_contribution(
    role: RoleMarket,
    skill_matches: dict[str, list[str]],
) -> dict[str, int]:
    required_skill_ids = {req.skill_id for req in role.required_skills}
    contribution: dict[str, set[str]] = defaultdict(set)
    for skill_id in required_skill_ids:
        for course_id in skill_matches.get(skill_id, []):
            contribution[course_id].add(skill_id)
    return {course_id: len(skills) for course_id, skills in contribution.items()}


def _choose_accessible_course(
    candidates: list[str],
    courses_by_id: dict[str, Course],
    prereq_cache: dict[str, set[str]],
    role_id: str,
    skill_id: str,
) -> str | None:
    if not candidates:
        return None
    forced = _target_course_override(role_id=role_id, skill_id=skill_id, candidates=candidates)
    if forced:
        return forced
    idx_by_course = {cid: idx for idx, cid in enumerate(candidates)}
    ranked = sorted(
        candidates,
        key=lambda cid: (
            _course_level_penalty(_course_number(cid)) * 2
            + len(_prereq_closure(cid, courses_by_id, prereq_cache)),
            idx_by_course.get(cid, 999),
            cid,
        ),
    )
    return ranked[0] if ranked else None


def _target_course_override(role_id: str, skill_id: str, candidates: list[str]) -> str | None:
    if role_id == "ROLE_OPERATIONS_RESEARCH_ANALYST" and skill_id == "SK_DATA_VIZ":
        if "BUAD-345" in candidates:
            return "BUAD-345"
    return None


def _prereq_closure(
    course_id: str,
    courses_by_id: dict[str, Course],
    cache: dict[str, set[str]],
) -> set[str]:
    if course_id in cache:
        return cache[course_id]
    course = courses_by_id.get(course_id)
    if not course:
        cache[course_id] = set()
        return cache[course_id]
    closure: set[str] = set()
    for prereq in course.prerequisites:
        if prereq in courses_by_id:
            closure.add(prereq)
            closure.update(_prereq_closure(prereq, courses_by_id, cache))
    cache[course_id] = closure
    return closure


def _course_level_penalty(course_num: int | None) -> int:
    if course_num is None:
        return 3
    if course_num < 100:
        return 6
    if course_num <= 299:
        return 0
    if course_num <= 399:
        return 1
    if course_num <= 499:
        return 4
    return 5


def _schedule_semesters(
    expanded_targets: set[str],
    target_courses: set[str],
    supplemental_pool: list[str],
    supplemental_relevance: dict[str, float],
    courses_by_id: dict[str, Course],
    role_id: str,
    curated_course_ids: set[str],
    course_skill_contribution: dict[str, int],
    completed_courses: set[str],
    start_term: str,
    include_optional_terms: bool,
    level: str,
    min_credits: int,
    target_credits: int,
    max_credits: int,
    degree_total_credits: int | None = None,
) -> tuple[list[PlanSemester], set[str], set[str]]:
    remaining = set(c for c in expanded_targets if c in courses_by_id and c not in completed_courses)
    supplemental_remaining = set(
        c for c in supplemental_pool if c in courses_by_id and c not in completed_courses
    )
    planned: set[str] = set()
    semesters: list[PlanSemester] = []
    completed = set(completed_courses)
    preferred_departments = _preferred_departments(role_id=role_id, skill_category="")
    min_courses_soft, max_courses_soft = _course_count_policy(level)

    if level == "UG" and not include_optional_terms:
        term_cycle = ["Fall", "Spring"]
    else:
        term_cycle = ["Fall", "Spring", "Summer", "Winter"]
    try:
        start_idx = term_cycle.index(start_term)
    except ValueError:
        start_idx = 0

    in_graph_dependencies: dict[str, set[str]] = {}
    for course_id in remaining:
        prereqs = set()
        course = courses_by_id[course_id]
        for prereq in course.prerequisites:
            if prereq in remaining and prereq in courses_by_id:
                prereqs.add(prereq)
        in_graph_dependencies[course_id] = prereqs
    prereq_depths = _dependency_depths(in_graph_dependencies)

    max_horizon = 16
    cycle_progress = False
    for term_offset in range(max_horizon):
        if not remaining:
            break
        term = term_cycle[(start_idx + term_offset) % len(term_cycle)]

        available = []
        for cid in sorted(remaining):
            course = courses_by_id[cid]
            if not in_graph_dependencies.get(cid, set()).issubset(completed):
                continue
            if not _is_offered_in_term(course, term):
                continue
            available.append(course)
        if not available:
            if (term_offset + 1) % len(term_cycle) == 0:
                if not cycle_progress:
                    break
                cycle_progress = False
            continue

        available.sort(
            key=lambda c: (
                c.course_id not in curated_course_ids,
                -course_skill_contribution.get(c.course_id, 0),
                prereq_depths.get(c.course_id, 0),
                c.course_id,
            )
        )
        cumulative_before = sum(s.total_credits for s in semesters)
        selected: list[Course] = []
        credit_sum = 0.0

        for course in available:
            if len(selected) >= max_courses_soft:
                break
            if credit_sum + course.credits > max_credits:
                continue
            if degree_total_credits is not None and (
                cumulative_before + credit_sum + course.credits > degree_total_credits
            ):
                continue
            selected.append(course)
            credit_sum += course.credits
            if credit_sum >= target_credits:
                break

        if not selected and available:
            selected = [available[0]]
            credit_sum = available[0].credits

        # Fill underloaded terms with additional role-relevant courses.
        if selected and (credit_sum < min_credits or len(selected) < min_courses_soft):
            fill_candidates = [
                courses_by_id[cid]
                for cid in supplemental_remaining
                if cid not in remaining
                and cid not in {c.course_id for c in selected}
                and _prereqs_ready(courses_by_id[cid], completed, courses_by_id)
                and _is_offered_in_term(courses_by_id[cid], term)
            ]
            fill_candidates.sort(
                key=lambda c: (
                    supplemental_relevance.get(c.course_id, 0.0) <= 0.0,
                    -supplemental_relevance.get(c.course_id, 0.0),
                    _is_low_signal_course(c),
                    _is_foundational_course(c),
                    c.department not in preferred_departments,
                    _course_number(c.course_id) is None,
                    _course_number(c.course_id) < 100 if _course_number(c.course_id) else True,
                    abs(c.credits - 3),
                    len(c.prerequisites),
                    c.course_id,
                )
            )
            prioritized_fill = [
                c
                for c in fill_candidates
                if supplemental_relevance.get(c.course_id, 0.0) >= 1.0
            ]
            secondary_fill = [
                c
                for c in fill_candidates
                if c not in prioritized_fill and not _is_foundational_course(c)
            ]
            last_resort_fill = [
                c
                for c in fill_candidates
                if c not in prioritized_fill and c not in secondary_fill
            ]

            for bucket in (prioritized_fill, secondary_fill, last_resort_fill):
                for course in bucket:
                    if len(selected) >= max_courses_soft:
                        break
                    if credit_sum + course.credits > max_credits:
                        continue
                    if degree_total_credits is not None and (
                        cumulative_before + credit_sum + course.credits > degree_total_credits
                    ):
                        continue
                    selected.append(course)
                    credit_sum += course.credits
                    if credit_sum >= min_credits and len(selected) >= min_courses_soft:
                        break
                if credit_sum >= min_credits and len(selected) >= min_courses_soft:
                    break

        if not selected:
            if (term_offset + 1) % len(term_cycle) == 0:
                if not cycle_progress:
                    break
                cycle_progress = False
            continue

        semester_ids = [c.course_id for c in selected]
        warnings = []
        for course in selected:
            if not course.offered_terms:
                warnings.append(
                    f"{course.course_id}: offering term not yet decided by department."
                )
        semesters.append(
            PlanSemester(
                semester_index=len(semesters) + 1,
                term=term,
                courses=semester_ids,
                total_credits=round(credit_sum, 2),
                warnings=warnings,
            )
        )
        for cid in semester_ids:
            if cid in remaining:
                remaining.remove(cid)
            if cid in supplemental_remaining:
                supplemental_remaining.remove(cid)
            planned.add(cid)
            completed.add(cid)
        cycle_progress = True
        if degree_total_credits is not None:
            cumulative_now = sum(s.total_credits for s in semesters)
            if cumulative_now >= degree_total_credits:
                break
        if (term_offset + 1) % len(term_cycle) == 0:
            cycle_progress = False

    return semesters, planned, remaining


def _prereqs_ready(course: Course, completed: set[str], courses_by_id: dict[str, Course]) -> bool:
    for prereq in course.prerequisites:
        if prereq in completed:
            continue
        if prereq not in courses_by_id:
            # Out-of-scope prerequisite: allow planning but verifier will flag context.
            continue
        return False
    return True


def _dependency_depths(dependencies: dict[str, set[str]]) -> dict[str, int]:
    memo: dict[str, int] = {}

    def depth(course_id: str, stack: set[str]) -> int:
        if course_id in memo:
            return memo[course_id]
        if course_id in stack:
            return 0
        stack.add(course_id)
        prereqs = dependencies.get(course_id, set())
        if not prereqs:
            out = 0
        else:
            out = 1 + max(depth(prereq, stack) for prereq in prereqs)
        stack.remove(course_id)
        memo[course_id] = out
        return out

    for course_id in dependencies:
        depth(course_id, set())
    return memo


def _is_offered_in_term(course: Course, term: str) -> bool:
    if not course.offered_terms:
        return True
    normalized_term = _normalize_term_label(term)
    offered_terms = {
        normalized
        for raw in course.offered_terms
        if (normalized := _normalize_term_label(raw))
    }
    if not offered_terms:
        return True
    return normalized_term in offered_terms


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


def _build_skill_coverage(
    role: RoleMarket,
    skill_matches: dict[str, list[str]],
    completed_courses: set[str],
    planned_courses: set[str],
) -> list[SkillCoverage]:
    seen_courses = completed_courses | planned_courses
    out: list[SkillCoverage] = []
    for req in role.required_skills:
        candidates = skill_matches.get(req.skill_id, [])
        matched = [cid for cid in candidates if cid in seen_courses][:5]
        out.append(
            SkillCoverage(
                required_skill_id=req.skill_id,
                covered=bool(matched),
                matched_courses=matched,
            )
        )
    return out


def _build_fusion_summary(
    role: RoleMarket,
    skill_coverage: list[SkillCoverage],
    fusion_profiles: list[FusionRoleProfile],
) -> FusionSummary | None:
    profile = next((item for item in fusion_profiles if item.role_id == role.role_id), None)
    if not profile:
        return None

    coverage_by_skill = {item.required_skill_id: item for item in skill_coverage}
    domain_skill_coverage = [
        _to_skill_coverage(spec.skill_id, coverage_by_skill) for spec in profile.domain_skills
    ]
    tech_skill_coverage = [
        _to_skill_coverage(spec.skill_id, coverage_by_skill) for spec in profile.tech_skills
    ]

    domain_ready = _weighted_ready_pct(profile.domain_skills, coverage_by_skill)
    tech_ready = _weighted_ready_pct(profile.tech_skills, coverage_by_skill)
    overall = (
        domain_ready * profile.skill_bands.domain_weight
        + tech_ready * profile.skill_bands.tech_weight
    )

    unlock = []
    for item in profile.unlock_skills:
        cov = coverage_by_skill.get(item.skill_id)
        unlock.append(
            FusionUnlockSkillStatus(
                skill_id=item.skill_id,
                reason=item.reason,
                covered=bool(cov and cov.covered),
                matched_courses=(cov.matched_courses if cov else []),
            )
        )

    return FusionSummary(
        domain=profile.domain,
        domain_weight=profile.skill_bands.domain_weight,
        tech_weight=profile.skill_bands.tech_weight,
        domain_skill_coverage=domain_skill_coverage,
        tech_skill_coverage=tech_skill_coverage,
        unlock_skills=unlock,
        readiness=FusionReadiness(
            domain_ready_pct=domain_ready,
            tech_ready_pct=tech_ready,
            overall_fit_pct=overall,
        ),
    )


def _to_skill_coverage(
    skill_id: str,
    coverage_by_skill: dict[str, SkillCoverage],
) -> SkillCoverage:
    cov = coverage_by_skill.get(skill_id)
    if cov:
        return SkillCoverage(
            required_skill_id=cov.required_skill_id,
            covered=cov.covered,
            matched_courses=list(cov.matched_courses),
        )
    return SkillCoverage(required_skill_id=skill_id, covered=False, matched_courses=[])


def _weighted_ready_pct(
    requirements,
    coverage_by_skill: dict[str, SkillCoverage],
) -> float:
    total_weight = sum(max(1, int(item.importance)) for item in requirements)
    if total_weight <= 0:
        return 0.0
    covered_weight = 0
    for item in requirements:
        cov = coverage_by_skill.get(item.skill_id)
        if cov and cov.covered:
            covered_weight += max(1, int(item.importance))
    return covered_weight / total_weight


def _credit_policy(level: str) -> dict[str, int]:
    if level == "GR":
        return {
            "full_time_min": 9,
            "assistantship_min": 6,
            "target": 9,
            "normal_max": 12,
            "overload_threshold": 13,
        }
    return {
        "full_time_min": 12,
        "assistantship_min": 12,
        "target": 15,
        "normal_max": 17,
        "overload_threshold": 18,
    }


def _build_supplemental_pool(
    role: RoleMarket,
    skill_matches: dict[str, list[str]],
    expanded_targets: set[str],
    courses_by_id: dict[str, Course],
    level: str,
) -> tuple[list[str], dict[str, float]]:
    preferred = _preferred_departments(role.role_id, "")
    seen = set(expanded_targets)
    pool: list[str] = []
    low_signal_backlog: list[str] = []
    relevance: dict[str, float] = {}
    required_importance = {req.skill_id: req.importance for req in role.required_skills}

    # First pass: additional courses already linked to required skills.
    for req in role.required_skills:
        max_per_skill = 6 if req.importance >= 5 else 3 if req.importance >= 4 else 1
        for rank, cid in enumerate(skill_matches.get(req.skill_id, [])[:max_per_skill]):
            if cid in courses_by_id and cid not in seen:
                course = courses_by_id[cid]
                cnum = _course_number(cid)
                if level == "UG" and cnum and cnum >= 400 and req.importance < 5:
                    continue
                score = float(required_importance.get(req.skill_id, 3)) * max(0.35, 1.0 - rank * 0.06)
                if _is_foundational_course(course):
                    score -= 1.8
                if _is_low_signal_course(course):
                    low_signal_backlog.append(cid)
                    relevance[cid] = max(relevance.get(cid, 0.0), 0.05)
                    continue
                if score <= 0.4 and not (rank < 2 and required_importance.get(req.skill_id, 3) >= 4):
                    continue
                seen.add(cid)
                pool.append(cid)
                relevance[cid] = max(relevance.get(cid, 0.0), score)

    # Second pass: department-based supportive electives for load balancing.
    extras = [
        c.course_id
        for c in courses_by_id.values()
        if c.department in preferred
        and c.course_id not in seen
        and not _is_low_signal_course(c)
        and not _is_foundational_course(c)
        and (_course_number(c.course_id) is None or _course_number(c.course_id) >= 100)
        and (level != "UG" or _course_number(c.course_id) is None or _course_number(c.course_id) < 400)
    ]
    extras.sort(
        key=lambda cid: (
            _course_number(cid) is None,
            _course_number(cid) < 100 if _course_number(cid) else True,
            cid,
        )
    )
    for cid in extras[:120]:
        course = courses_by_id[cid]
        bonus = 0.0
        if course.department in {"MISY", "STAT", "CISC", "BUAD", "ECON"}:
            bonus += 0.35
        cnum = _course_number(cid)
        if cnum and cnum >= 300:
            bonus += 0.2
        seen.add(cid)
        pool.append(cid)
        relevance[cid] = max(relevance.get(cid, 0.0), 0.55 + bonus)

    # Keep low-signal classes as last-resort fillers only.
    for cid in low_signal_backlog[:24]:
        if cid not in seen:
            seen.add(cid)
            pool.append(cid)
            relevance[cid] = max(relevance.get(cid, 0.0), 0.05)

    return pool, relevance


def _course_count_policy(level: str) -> tuple[int, int]:
    if level == "GR":
        return 3, 4
    return 4, 5


def _is_low_signal_course(course: Course) -> bool:
    title_upper = course.title.upper()
    low_signal_terms = (
        "SEMINAR",
        "SPECIAL PROBLEM",
        "INDEPENDENT STUDY",
        "INTERNSHIP",
        "THESIS",
        "DISSERTATION",
        "RESEARCH",
    )
    return any(term in title_upper for term in low_signal_terms)


def _is_foundational_course(course: Course) -> bool:
    cnum = _course_number(course.course_id)
    if cnum is not None and cnum < 100:
        return True
    title_upper = course.title.upper()
    foundational_terms = (
        "INTERMEDIATE ALGEBRA",
        "PRE-CALCULUS",
        "PRECALCULUS",
        "SURVEY OF",
        "CONTEMPORARY MATHEMATICS",
    )
    return any(term in title_upper for term in foundational_terms)
