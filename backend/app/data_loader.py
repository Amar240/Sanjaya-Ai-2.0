from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .schemas.catalog import (
    Course,
    CourseSkillMapping,
    CuratedRoleSkillCourse,
    FusionPack,
    FusionRoleProfile,
    RoleMarket,
    RoleSkillEvidence,
    SkillMarket,
    SourceReference,
)
from .schemas.reality import ProjectTemplate, RoleRealityUSA


class DataValidationError(RuntimeError):
    pass


@dataclass(slots=True)
class CatalogStore:
    courses: list[Course]
    course_skills: list[CourseSkillMapping]
    curated_role_skill_courses: list[CuratedRoleSkillCourse]
    fusion_role_profiles: list[FusionRoleProfile]
    roles: list[RoleMarket]
    roles_source_file: str
    skills: list[SkillMarket]
    evidence_links: list[RoleSkillEvidence]
    sources: list[SourceReference]
    fusion_packs_usa: list[FusionPack] = field(default_factory=list)
    role_reality_usa: list[RoleRealityUSA] = field(default_factory=list)
    project_templates: list[ProjectTemplate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    data_version: str = ""

    @property
    def roles_by_id(self) -> dict[str, RoleMarket]:
        return {r.role_id: r for r in self.roles}

    @property
    def courses_by_id(self) -> dict[str, Course]:
        return {c.course_id: c for c in self.courses}


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_catalog_store(data_dir: Path | None = None) -> CatalogStore:
    root = _project_root()
    processed = data_dir or (root / "data" / "processed")
    data_files, roles_path = _resolve_data_files(processed)
    data_version = _compute_data_version(data_files)

    courses = [Course.model_validate(x) for x in _read_json(processed / "courses.json")]
    course_skills = [
        CourseSkillMapping.model_validate(x)
        for x in _read_json(processed / "course_skills.json")
    ]
    curated_path = processed / "course_skills_curated.json"
    curated_role_skill_courses = (
        [CuratedRoleSkillCourse.model_validate(x) for x in _read_json(curated_path)]
        if curated_path.exists()
        else []
    )
    fusion_path = processed / "fusion_roles.json"
    fusion_role_profiles = (
        [FusionRoleProfile.model_validate(x) for x in _read_json(fusion_path)]
        if fusion_path.exists()
        else []
    )
    fusion_packs_path = processed / "fusion_packs_usa.json"
    fusion_packs_usa = (
        [FusionPack.model_validate(x) for x in _read_json(fusion_packs_path)]
        if fusion_packs_path.exists()
        else []
    )
    roles = [RoleMarket.model_validate(x) for x in _read_json(roles_path)]
    skills = [SkillMarket.model_validate(x) for x in _read_json(processed / "skills_market.json")]
    evidence_links = [
        RoleSkillEvidence.model_validate(x)
        for x in _read_json(processed / "role_skill_evidence.json")
    ]
    sources = [
        SourceReference.model_validate(x) for x in _read_json(processed / "market_sources.json")
    ]
    role_reality_usa = [
        RoleRealityUSA.model_validate(x)
        for x in _read_json(processed / "role_reality_usa.json")
    ]
    project_templates = [
        ProjectTemplate.model_validate(x)
        for x in _read_json(processed / "project_templates.json")
    ]

    _validate_cross_references(
        courses,
        course_skills,
        curated_role_skill_courses,
        fusion_role_profiles,
        roles,
        skills,
        evidence_links,
        sources,
        fusion_packs_usa,
        role_reality_usa,
        project_templates,
    )
    warnings = _validate_course_prereqs(courses)
    if curated_role_skill_courses:
        warnings.append(
            f"Curated role-skill-course mappings loaded: {len(curated_role_skill_courses)}."
        )
    if fusion_role_profiles:
        warnings.append(
            f"Fusion role profiles loaded: {len(fusion_role_profiles)}."
        )

    return CatalogStore(
        courses=courses,
        course_skills=course_skills,
        curated_role_skill_courses=curated_role_skill_courses,
        fusion_role_profiles=fusion_role_profiles,
        roles=roles,
        roles_source_file=roles_path.name,
        skills=skills,
        evidence_links=evidence_links,
        sources=sources,
        fusion_packs_usa=fusion_packs_usa,
        role_reality_usa=role_reality_usa,
        project_templates=project_templates,
        warnings=warnings,
        data_version=data_version,
    )


def _validate_cross_references(
    courses: list[Course],
    course_skills: list[CourseSkillMapping],
    curated_role_skill_courses: list[CuratedRoleSkillCourse],
    fusion_role_profiles: list[FusionRoleProfile],
    roles: list[RoleMarket],
    skills: list[SkillMarket],
    evidence_links: list[RoleSkillEvidence],
    sources: list[SourceReference],
    fusion_packs_usa: list[FusionPack],
    role_reality_usa: list[RoleRealityUSA],
    project_templates: list[ProjectTemplate],
) -> None:
    role_ids = {r.role_id for r in roles}
    skill_ids = {s.skill_id for s in skills}
    source_ids = {s.source_id for s in sources}
    course_ids = {c.course_id for c in courses}
    errors: list[str] = []

    for mapping in course_skills:
        if mapping.course_id not in course_ids:
            errors.append(
                f"Course-skill mapping references missing course '{mapping.course_id}'."
            )
        if mapping.skill_id not in skill_ids:
            errors.append(
                f"Course-skill mapping references missing skill '{mapping.skill_id}'."
            )

    for mapping in curated_role_skill_courses:
        if mapping.role_id not in role_ids:
            errors.append(
                f"Curated mapping references missing role '{mapping.role_id}'."
            )
        if mapping.course_id not in course_ids:
            errors.append(
                f"Curated mapping references missing course '{mapping.course_id}'."
            )
        if mapping.skill_id not in skill_ids:
            errors.append(
                f"Curated mapping references missing skill '{mapping.skill_id}'."
            )

    for profile in fusion_role_profiles:
        if profile.role_id not in role_ids:
            errors.append(
                f"Fusion profile references missing role '{profile.role_id}'."
            )
        for item in profile.domain_skills:
            if item.skill_id not in skill_ids:
                errors.append(
                    f"Fusion profile '{profile.role_id}' domain skill missing: '{item.skill_id}'."
                )
        for item in profile.tech_skills:
            if item.skill_id not in skill_ids:
                errors.append(
                    f"Fusion profile '{profile.role_id}' tech skill missing: '{item.skill_id}'."
                )
        for item in profile.unlock_skills:
            if item.skill_id not in skill_ids:
                errors.append(
                    f"Fusion profile '{profile.role_id}' unlock skill missing: '{item.skill_id}'."
                )
        for source_id in profile.evidence_sources:
            if source_id not in source_ids:
                errors.append(
                    f"Fusion profile '{profile.role_id}' references missing source '{source_id}'."
                )

    for role in roles:
        for req in role.required_skills:
            if req.skill_id not in skill_ids:
                errors.append(
                    f"Role '{role.role_id}' references missing skill '{req.skill_id}'."
                )
        for source_id in role.evidence_sources:
            if source_id not in source_ids:
                errors.append(
                    f"Role '{role.role_id}' references missing source '{source_id}'."
                )

    for skill in skills:
        for source_id in skill.source_refs:
            if source_id not in source_ids:
                errors.append(
                    f"Skill '{skill.skill_id}' references missing source '{source_id}'."
                )

    for evidence in evidence_links:
        if evidence.role_id not in role_ids:
            errors.append(f"Evidence references missing role '{evidence.role_id}'.")
        if evidence.skill_id not in skill_ids:
            errors.append(f"Evidence references missing skill '{evidence.skill_id}'.")
        for source_id in evidence.evidence_sources:
            if source_id not in source_ids:
                errors.append(
                    f"Evidence ({evidence.role_id}/{evidence.skill_id}) missing source '{source_id}'."
                )

    for reality in role_reality_usa:
        if reality.role_id not in role_ids:
            errors.append(f"Role reality references missing role '{reality.role_id}'.")
        for source_id in reality.sources:
            if source_id not in source_ids:
                errors.append(
                    f"Role reality '{reality.role_id}' references missing source '{source_id}'."
                )

    for template in project_templates:
        if template.skill_id not in skill_ids:
            errors.append(
                f"Project template '{template.template_id}' references missing skill '{template.skill_id}'."
            )

    template_ids = {item.template_id for item in project_templates}
    for pack in fusion_packs_usa:
        for role_id in pack.target_roles:
            if role_id not in role_ids:
                errors.append(
                    f"Fusion pack '{pack.fusion_pack_id}' references missing role '{role_id}'."
                )
        for skill_id in pack.unlock_skills:
            if skill_id not in skill_ids:
                errors.append(
                    f"Fusion pack '{pack.fusion_pack_id}' references missing skill '{skill_id}'."
                )
        for template_id in pack.starter_projects:
            if template_id not in template_ids:
                errors.append(
                    f"Fusion pack '{pack.fusion_pack_id}' references missing project template '{template_id}'."
                )
        for source_id in pack.evidence_sources:
            if source_id not in source_ids:
                errors.append(
                    f"Fusion pack '{pack.fusion_pack_id}' references missing source '{source_id}'."
                )

    if errors:
        msg = "Market data integrity check failed:\n- " + "\n- ".join(errors)
        raise DataValidationError(msg)


def _validate_course_prereqs(courses: list[Course]) -> list[str]:
    existing = {c.course_id for c in courses}
    missing_refs = set()
    for course in courses:
        for prereq in course.prerequisites:
            if prereq not in existing:
                missing_refs.add((course.course_id, prereq))

    warnings = []
    if missing_refs:
        warnings.append(
            f"Global catalog-wide external prerequisite references: {len(missing_refs)}."
        )
    return warnings


def _resolve_data_files(processed: Path) -> tuple[list[Path], Path]:
    calibrated_roles_path = processed / "roles_market_calibrated.json"
    default_roles_path = processed / "roles_market.json"
    roles_path = calibrated_roles_path if calibrated_roles_path.exists() else default_roles_path

    files = [
        processed / "courses.json",
        processed / "course_skills.json",
        roles_path,
        processed / "skills_market.json",
        processed / "role_skill_evidence.json",
        processed / "market_sources.json",
        processed / "role_reality_usa.json",
        processed / "project_templates.json",
    ]
    optional_files = [
        processed / "course_skills_curated.json",
        processed / "fusion_roles.json",
        processed / "fusion_packs_usa.json",
    ]
    for path in optional_files:
        if path.exists():
            files.append(path)

    files = sorted(files, key=lambda p: str(p.resolve()).lower())
    return files, roles_path


def _compute_data_version(files: list[Path]) -> str:
    hasher = hashlib.sha256()
    for path in files:
        hasher.update(str(path.resolve()).encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()
