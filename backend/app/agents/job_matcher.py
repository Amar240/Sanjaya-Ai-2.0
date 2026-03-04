from __future__ import annotations

import re
from dataclasses import dataclass

from ..data_loader import CatalogStore
from ..schemas.job_match import (
    JobExtractResult,
    JobMatchResponse,
    JobSkillProjects,
    MappedSkillItem,
    MappingSummary,
    UnmappedTerm,
)
from ..schemas.plan import PlanResponse, SkillCoverage
from .gap_engine import build_gap_report

_SOURCE_PRIORITY = {"required": 0, "preferred": 1, "tool": 2}
_MATCH_THRESHOLD = 0.35

# Small deterministic synonym hints for demo robustness.
_TERM_SYNONYMS: dict[str, tuple[str, ...]] = {
    "python": ("python", "py"),
    "sql": ("sql", "postgresql", "mysql"),
    "machine learning": ("machine learning", "ml"),
    "statistics": ("statistics", "statistical"),
    "cybersecurity": ("cybersecurity", "cyber security", "infosec"),
    "cloud": ("cloud", "aws", "azure", "gcp"),
    "apis": ("api", "apis", "rest api"),
}


@dataclass(slots=True)
class _TermMatch:
    item: MappedSkillItem | None
    term: str
    source: str


def match_extracted_to_skills(
    extracted: JobExtractResult,
    store: CatalogStore,
    *,
    threshold: float = _MATCH_THRESHOLD,
) -> tuple[list[MappedSkillItem], list[UnmappedTerm], MappingSummary]:
    raw_terms = _ordered_terms(extracted)
    matches: list[_TermMatch] = []
    unmapped: list[tuple[str, str]] = []

    for source, term in raw_terms:
        match = _best_skill_match(term=term, source=source, store=store)
        if match is None or match.match_confidence < threshold:
            unmapped.append((term, source))
            continue
        matches.append(_TermMatch(item=match, term=term, source=source))

    deduped: dict[str, MappedSkillItem] = {}
    for match in matches:
        if match.item is None:
            continue
        existing = deduped.get(match.item.skill_id)
        if existing is None:
            deduped[match.item.skill_id] = match.item
            continue
        new_priority = _SOURCE_PRIORITY.get(match.item.source, 9)
        old_priority = _SOURCE_PRIORITY.get(existing.source, 9)
        if (new_priority, -match.item.match_confidence, match.item.skill_id) < (
            old_priority,
            -existing.match_confidence,
            existing.skill_id,
        ):
            deduped[match.item.skill_id] = match.item

    mapped_skills = sorted(
        deduped.values(),
        key=lambda item: (
            _SOURCE_PRIORITY.get(item.source, 9),
            item.skill_id,
        ),
    )
    unmapped_terms, total_unmapped_unique = _normalize_unmapped_terms(unmapped, limit=20)
    summary = MappingSummary(
        mapped_count=len(mapped_skills),
        unmapped_count=total_unmapped_unique,
        threshold_used=float(threshold),
    )
    return mapped_skills, unmapped_terms, summary


def build_job_match_response(
    *,
    extracted: JobExtractResult,
    mapped_skills: list[MappedSkillItem],
    unmapped_terms: list[UnmappedTerm],
    mapping_summary: MappingSummary,
    store: CatalogStore,
    plan: PlanResponse | None,
    llm_status: str,
    llm_error: str | None,
) -> JobMatchResponse:
    mapped_ids = [item.skill_id for item in mapped_skills]
    covered: list[str] = []
    missing: list[str] = []
    out_of_scope: list[str] = []

    if plan is not None:
        coverage_by_skill = {
            item.required_skill_id: item.covered for item in (plan.skill_coverage or [])
        }
        for skill_id in mapped_ids:
            if skill_id not in coverage_by_skill:
                out_of_scope.append(skill_id)
            elif coverage_by_skill.get(skill_id):
                covered.append(skill_id)
            else:
                missing.append(skill_id)
    else:
        missing = list(mapped_ids)

    confidence_level, hours_per_week = _resolve_guidance(plan)
    recommended_projects = _recommended_projects_for_missing(
        missing_skill_ids=missing,
        plan=plan,
        store=store,
        confidence_level=confidence_level,
        hours_per_week=hours_per_week,
    )

    return JobMatchResponse(
        job_title=extracted.job_title,
        extracted=extracted,
        mapped_skills=mapped_skills,
        unmapped_terms=unmapped_terms,
        mapping_summary=mapping_summary,
        covered_skill_ids=covered,
        missing_skill_ids=missing,
        out_of_scope_skill_ids=out_of_scope,
        recommended_projects=recommended_projects,
        llm_status=llm_status,  # type: ignore[arg-type]
        llm_error=llm_error,
    )


def _ordered_terms(extracted: JobExtractResult) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for source, values in (
        ("required", extracted.required_skills),
        ("preferred", extracted.preferred_skills),
        ("tool", extracted.tools),
    ):
        for value in values:
            term = _normalize_phrase(value)
            if term:
                out.append((source, term))
    return out


def _best_skill_match(*, term: str, source: str, store: CatalogStore) -> MappedSkillItem | None:
    term_tokens = set(_tokenize(term))
    best: tuple[float, str, str | None, str | None] | None = None
    # (score, skill_id, matched_by, matched_on)
    for skill in store.skills:
        skill_name = skill.name
        score, matched_by, matched_on = _score_match(
            term=term,
            term_tokens=term_tokens,
            skill_name=skill_name,
            aliases=list(skill.aliases),
        )
        if best is None or score > best[0] or (score == best[0] and skill.skill_id < best[1]):
            best = (score, skill.skill_id, matched_by, matched_on)

    if best is None:
        return None
    score, skill_id, matched_by, matched_on = best
    skill_name = next((item.name for item in store.skills if item.skill_id == skill_id), skill_id)
    return MappedSkillItem(
        skill_id=skill_id,
        skill_name=skill_name,
        source=source,  # type: ignore[arg-type]
        match_confidence=round(max(0.0, min(1.0, score)), 4),
        matched_by=matched_by,  # type: ignore[arg-type]
        matched_on=matched_on,
    )


def _score_match(
    *,
    term: str,
    term_tokens: set[str],
    skill_name: str,
    aliases: list[str],
) -> tuple[float, str | None, str | None]:
    norm_skill = _normalize_phrase(skill_name)
    skill_tokens = set(_tokenize(norm_skill))
    best_score = _overlap_score(term_tokens, skill_tokens)
    matched_by: str | None = "name_overlap" if best_score > 0 else None
    matched_on: str | None = skill_name if best_score > 0 else None

    if term == norm_skill:
        return 1.0, "name_overlap", skill_name

    for alias in aliases:
        norm_alias = _normalize_phrase(alias)
        if not norm_alias:
            continue
        if term == norm_alias:
            return 0.98, "synonym", alias
        alias_tokens = set(_tokenize(norm_alias))
        alias_score = _overlap_score(term_tokens, alias_tokens)
        if alias_score > best_score:
            best_score = alias_score
            matched_by = "synonym"
            matched_on = alias

    for canonical, synonyms in _TERM_SYNONYMS.items():
        if term not in {_normalize_phrase(value) for value in synonyms}:
            continue
        if canonical in {norm_skill, _normalize_phrase(skill_name)}:
            return 0.94, "synonym", canonical

    if norm_skill and (term in norm_skill or norm_skill in term):
        substring_score = 0.55
        if substring_score > best_score:
            best_score = substring_score
            matched_by = "substring"
            matched_on = skill_name
    return best_score, matched_by, matched_on


def _overlap_score(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    inter = len(left & right)
    if inter == 0:
        return 0.0
    return inter / max(len(left), len(right))


def _normalize_unmapped_terms(
    terms: list[tuple[str, str]],
    *,
    limit: int,
) -> tuple[list[UnmappedTerm], int]:
    best_source_by_term: dict[str, str] = {}
    for term, source in terms:
        current = best_source_by_term.get(term)
        if current is None or _SOURCE_PRIORITY.get(source, 9) < _SOURCE_PRIORITY.get(current, 9):
            best_source_by_term[term] = source
    ordered_full = sorted(
        best_source_by_term.items(),
        key=lambda item: (_SOURCE_PRIORITY.get(item[1], 9), item[0]),
    )
    ordered = ordered_full[:limit]
    result = [
        UnmappedTerm(term=term, source=source)  # type: ignore[arg-type]
        for term, source in ordered
    ]
    return result, len(ordered_full)


def _recommended_projects_for_missing(
    *,
    missing_skill_ids: list[str],
    plan: PlanResponse | None,
    store: CatalogStore,
    confidence_level: str,
    hours_per_week: int,
) -> list[JobSkillProjects]:
    if not missing_skill_ids:
        return []
    temp_plan = PlanResponse(
        selected_role_id=plan.selected_role_id if plan else "ROLE_JOB_MATCH",
        selected_role_title=plan.selected_role_title if plan else "Job Match",
        skill_coverage=[
            SkillCoverage(required_skill_id=skill_id, covered=False, matched_courses=[])
            for skill_id in sorted(set(missing_skill_ids))
        ],
    )
    gap_report = build_gap_report(
        temp_plan,
        store,
        confidence_level=confidence_level,
        hours_per_week=hours_per_week,
    )
    return [
        JobSkillProjects(
            skill_id=item.skill_id,
            skill_name=item.skill_name,
            projects=item.recommended_projects,
        )
        for item in gap_report.missing_skills
    ]


def _resolve_guidance(plan: PlanResponse | None) -> tuple[str, int]:
    if plan is None or plan.intake_snapshot is None:
        return "medium", 6
    return plan.intake_snapshot.confidence_level, int(plan.intake_snapshot.hours_per_week)


def _normalize_phrase(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\+#\. ]+", " ", value.lower())).strip()


def _tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9\+#\.]+", _normalize_phrase(value))
