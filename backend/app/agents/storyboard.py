from __future__ import annotations

import json
import os
import re
import time
from urllib import error as urllib_error
from urllib import request as urllib_request

from ..data_loader import CatalogStore
from ..schemas.plan import PlanResponse
from ..schemas.storyboard import (
    StoryboardCitation,
    StoryboardRequest,
    StoryboardResponse,
    StoryboardSection,
)


def build_storyboard(
    *,
    request: StoryboardRequest,
    plan: PlanResponse,
    store: CatalogStore,
) -> StoryboardResponse:
    sections = _deterministic_sections(request=request, plan=plan, store=store)
    llm_status = "disabled"
    llm_error: str | None = None
    if _llm_storyboard_enabled():
        rewritten, llm_error = _llm_rewrite_sections(
            request=request,
            sections=sections,
        )
        if rewritten is not None:
            sections = rewritten
            llm_status = "used"
        else:
            llm_status = "fallback"

    return StoryboardResponse(
        plan_id=plan.plan_id,
        sections=sections,
        llm_status=llm_status,
        llm_error=llm_error,
    )


def _deterministic_sections(
    *,
    request: StoryboardRequest,
    plan: PlanResponse,
    store: CatalogStore,
) -> list[StoryboardSection]:
    sections: list[StoryboardSection] = []
    guidance = _guidance_snapshot(plan)
    goal_type = guidance["goal_type"]
    confidence_level = guidance["confidence_level"]
    hours_per_week = guidance["hours_per_week"]

    selected = plan.selected_role_title
    alternatives = [item for item in (plan.candidate_roles or []) if item.role_id != plan.selected_role_id]
    alt_text = ", ".join(
        f"{item.role_title} ({item.score:.2f})" for item in alternatives[:2]
    ) or "No ranked alternatives were available in this run."
    coverage_total = len(plan.skill_coverage)
    coverage_done = sum(1 for item in plan.skill_coverage if item.covered)
    if goal_type == "explore":
        top_paths = ", ".join(
            item.role_title for item in (plan.candidate_roles or [])[:3]
        ) or selected
        role_snapshot_body = (
            "You're exploring - here are 3 strong paths based on your interests: "
            f"{top_paths}. Current required-skill coverage for {selected} is "
            f"{coverage_done}/{coverage_total}."
        )
    elif goal_type == "type_role":
        role_snapshot_body = (
            f"We matched your typed role to {selected}. Current required-skill coverage is "
            f"{coverage_done}/{coverage_total}. Close alternatives in this run: {alt_text}."
        )
    else:
        role_snapshot_body = (
            f"This roadmap targets {selected}. Current required-skill coverage is "
            f"{coverage_done}/{coverage_total}. Top alternatives in this run: {alt_text}."
        )
    sections.append(
        StoryboardSection(
            title="Role Snapshot",
            body=role_snapshot_body,
            citations=_unique_citations(
                [
                    StoryboardCitation(kind="evidence_id", id=item.evidence_id)
                    for item in (plan.evidence_panel or [])[:2]
                    if item.evidence_id
                ]
            ),
        )
    )

    reality = plan.role_reality
    if reality is not None:
        salary = reality.salary_usd
        salary_bits = []
        if salary.p25 is not None:
            salary_bits.append(f"p25 ${salary.p25:,}")
        if salary.median is not None:
            salary_bits.append(f"median ${salary.median:,}")
        if salary.p75 is not None:
            salary_bits.append(f"p75 ${salary.p75:,}")
        salary_text = ", ".join(salary_bits) if salary_bits else "range unavailable"
        tasks = "; ".join(reality.typical_tasks[:3]) or "Task examples unavailable."
        sections.append(
            StoryboardSection(
                title="USA Role Reality",
                body=(
                    f"Typical tasks in the U.S. market include: {tasks}. "
                    f"Salary ranges (not guarantees): {salary_text}."
                ),
                citations=_unique_citations(
                    [StoryboardCitation(kind="source_id", id=source_id) for source_id in reality.sources]
                ),
            )
        )
    else:
        sections.append(
            StoryboardSection(
                title="USA Role Reality",
                body="No USA reality profile is attached for this role yet, so salary/task ranges are currently unavailable.",
                citations=[],
            )
        )

    milestone_bits = []
    for sem in plan.semesters[:4]:
        if sem.courses:
            milestone_bits.append(
                f"Semester {sem.semester_index} ({sem.term}): {', '.join(sem.courses[:3])}"
            )
    milestone_text = " | ".join(milestone_bits) if milestone_bits else "No semester milestones available."
    sections.append(
        StoryboardSection(
            title="Roadmap Milestones",
            body=(
                f"The plan has {len(plan.semesters)} semester blocks. "
                f"Near-term milestones: {milestone_text}."
            ),
            citations=_unique_citations(
                [
                    StoryboardCitation(kind="evidence_id", id=item.evidence_id)
                    for item in (plan.evidence_panel or [])[:3]
                    if item.evidence_id
                ]
            ),
        )
    )

    gap = plan.gap_report
    if gap and gap.missing_skills:
        action_lines = []
        for item in gap.missing_skills[:3]:
            project_names = ", ".join(project.title for project in item.recommended_projects[:2]) or "no templates yet"
            action_lines.append(f"{item.skill_name}: {project_names}")
        gap_text = " | ".join(action_lines)
    else:
        gap_text = "No uncovered required skills were detected in this plan."
    sections.append(
        StoryboardSection(
            title="Gap-to-Project Plan",
            body=(
                f"Missing-skill project recommendations: {gap_text}. "
                "Use these projects as portfolio evidence tied to uncovered requirements."
            ),
            citations=_gap_citations(plan=plan, store=store),
        )
    )

    if request.audience_level == "beginner":
        lines = [f"Plan assumes ~{hours_per_week} hours/week for projects."]
        if confidence_level == "low":
            lines.append("This roadmap is written in beginner-friendly steps.")
        sections.append(
            StoryboardSection(
                title="Execution Notes",
                body=(
                    " ".join(lines)
                    + " Start with beginner templates first, keep weekly checkpoints, and avoid adding extra commitments before prerequisite-heavy terms."
                ),
                citations=[],
            )
        )
    else:
        lines = [f"Plan assumes ~{hours_per_week} hours/week for projects."]
        if confidence_level == "low":
            lines.append("This roadmap is written in beginner-friendly steps.")
        sections.append(
            StoryboardSection(
                title="Execution Notes",
                body=" ".join(lines),
                citations=[],
            )
        )
    return sections


def _guidance_snapshot(plan: PlanResponse) -> dict[str, str | int]:
    snapshot = plan.intake_snapshot
    if snapshot is None:
        return {
            "goal_type": "select_role",
            "confidence_level": "medium",
            "hours_per_week": 6,
        }
    return {
        "goal_type": snapshot.goal_type,
        "confidence_level": snapshot.confidence_level,
        "hours_per_week": int(snapshot.hours_per_week),
    }


def _gap_citations(*, plan: PlanResponse, store: CatalogStore) -> list[StoryboardCitation]:
    if plan.role_reality is None:
        return []
    # Prefer role reality citations so salary/task statements always tie back to source ids.
    sources = [StoryboardCitation(kind="source_id", id=source_id) for source_id in plan.role_reality.sources]
    if sources:
        return _unique_citations(sources[:3])
    return []


def _unique_citations(items: list[StoryboardCitation]) -> list[StoryboardCitation]:
    seen: set[tuple[str, str]] = set()
    out: list[StoryboardCitation] = []
    for item in items:
        key = (item.kind, item.id)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _llm_storyboard_enabled() -> bool:
    return os.getenv("SANJAYA_ENABLE_LLM_STORYBOARD", "").strip() == "1"


def _llm_rewrite_sections(
    *,
    request: StoryboardRequest,
    sections: list[StoryboardSection],
) -> tuple[list[StoryboardSection] | None, str | None]:
    provider, api_key, model, endpoint = _resolve_llm_target()
    if not provider:
        return None, "llm_not_configured"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Rewrite only storyboard section body text for clarity. "
                    "Do not add or remove facts, titles, or citations. "
                    "Return strict JSON."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "tone": request.tone,
                        "audience_level": request.audience_level,
                        "sections": [section.model_dump() for section in sections],
                        "required_output_schema": {
                            "sections": [
                                {"title": "string", "body": "string", "citations": [{"kind": "source_id|evidence_id", "id": "string"}]}
                            ]
                        },
                    },
                    ensure_ascii=True,
                ),
            },
        ],
        "temperature": 0.35,
        "max_tokens": 900,
    }
    if provider != "gemini":
        payload["response_format"] = {"type": "json_object"}
    req = urllib_request.Request(
        url=endpoint,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    retries = 2
    last_error: str | None = None
    for attempt in range(retries + 1):
        try:
            with urllib_request.urlopen(req, timeout=60) as response:
                text = response.read().decode("utf-8")
        except urllib_error.HTTPError as exc:
            last_error = f"{provider}_http_{exc.code}"
            if attempt < retries and exc.code in {408, 409, 425, 429, 500, 502, 503, 504}:
                time.sleep(1.0 * (attempt + 1))
                continue
            return None, last_error
        except urllib_error.URLError:
            last_error = f"{provider}_network_error"
            if attempt < retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            return None, last_error
        except TimeoutError:
            last_error = f"{provider}_timeout"
            if attempt < retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            return None, last_error

        parsed = _parse_llm_payload(text)
        if parsed is None:
            last_error = f"{provider}_parse_error"
            if attempt < retries:
                time.sleep(0.6 * (attempt + 1))
                continue
            return None, last_error
        validated = _validate_rewritten_sections(original=sections, candidate=parsed)
        if validated is None:
            last_error = f"{provider}_schema_mismatch"
            if attempt < retries:
                time.sleep(0.6 * (attempt + 1))
                continue
            return None, last_error
        return validated, None

    return None, last_error or "llm_unknown"


def _parse_llm_payload(raw_text: str) -> list[dict] | None:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return None
    content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
    if isinstance(content, str):
        try:
            obj = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            if not match:
                return None
            try:
                obj = json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        sections = obj.get("sections")
        if isinstance(sections, list):
            return sections
    return None


def _validate_rewritten_sections(
    *,
    original: list[StoryboardSection],
    candidate: list[dict],
) -> list[StoryboardSection] | None:
    if len(candidate) != len(original):
        return None
    out: list[StoryboardSection] = []
    for idx, base in enumerate(original):
        row = candidate[idx]
        if not isinstance(row, dict):
            return None
        title = row.get("title")
        body = row.get("body")
        citations = row.get("citations")
        if title != base.title:
            return None
        if not isinstance(body, str) or not body.strip():
            return None
        if not isinstance(citations, list):
            return None
        normalized = []
        for citation in citations:
            if not isinstance(citation, dict):
                return None
            kind = citation.get("kind")
            cid = citation.get("id")
            if kind not in {"source_id", "evidence_id"} or not isinstance(cid, str):
                return None
            normalized.append({"kind": kind, "id": cid})
        if normalized != [item.model_dump() for item in base.citations]:
            return None
        out.append(
            StoryboardSection(
                title=base.title,
                body=body.strip(),
                citations=base.citations,
            )
        )
    return out


def _resolve_llm_target() -> tuple[str | None, str, str, str]:
    provider_pref = os.getenv("LLM_PROVIDER", "auto").strip().lower()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    openai_model = os.getenv("OPENAI_MODEL_STORYBOARD", "").strip() or os.getenv("OPENAI_MODEL", "").strip() or "gpt-4o-mini"
    gemini_model = os.getenv("GEMINI_MODEL_STORYBOARD", "").strip() or os.getenv("GEMINI_MODEL", "").strip() or "gemini-2.0-flash"
    groq_model = os.getenv("GROQ_MODEL_STORYBOARD", "").strip() or os.getenv("GROQ_MODEL", "").strip() or "llama-3.3-70b-versatile"

    if provider_pref == "openai":
        if openai_key:
            return "openai", openai_key, openai_model, "https://api.openai.com/v1/chat/completions"
        return None, "", "", ""
    if provider_pref == "groq":
        if groq_key:
            return "groq", groq_key, groq_model, "https://api.groq.com/openai/v1/chat/completions"
        return None, "", "", ""
    if provider_pref == "gemini":
        if gemini_key:
            return (
                "gemini",
                gemini_key,
                gemini_model,
                "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            )
        return None, "", "", ""
    if openai_key:
        return "openai", openai_key, openai_model, "https://api.openai.com/v1/chat/completions"
    if gemini_key:
        return (
            "gemini",
            gemini_key,
            gemini_model,
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        )
    if groq_key:
        return "groq", groq_key, groq_model, "https://api.groq.com/openai/v1/chat/completions"
    return None, "", "", ""
