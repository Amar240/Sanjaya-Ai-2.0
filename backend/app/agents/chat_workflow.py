from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
import os
import re
from threading import Lock
import time
from typing import TypedDict
from urllib import error as urllib_error
from urllib import request as urllib_request
import uuid

from ..data_loader import CatalogStore
from ..rag import MarketEvidenceRetriever
from ..schemas.chat import (
    ChatProfileDraft,
    ChatRequest,
    ChatResponse,
    ChatRoleSuggestion,
    ChatTurn,
)
from ..schemas.plan import PlanRequest, StudentProfile

try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_CHAT_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency guard
    END = "__end__"
    StateGraph = None
    LANGGRAPH_CHAT_AVAILABLE = False


@dataclass
class _Session:
    session_id: str
    profile: ChatProfileDraft = field(default_factory=ChatProfileDraft)
    conversation: list[ChatTurn] = field(default_factory=list)


class _ChatState(TypedDict, total=False):
    request: ChatRequest
    session_id: str
    profile: ChatProfileDraft
    conversation: list[ChatTurn]
    suggested_roles: list[ChatRoleSuggestion]
    missing_fields: list[str]
    ready_for_plan: bool
    plan_request_draft: PlanRequest | None
    assistant_message: str
    llm_used: bool


_SESSIONS: dict[str, _Session] = {}
_SESSION_LOCK = Lock()
_RETRIEVER_CACHE: dict[int, MarketEvidenceRetriever] = {}


def run_chat_workflow(request: ChatRequest, store: CatalogStore) -> ChatResponse:
    if LANGGRAPH_CHAT_AVAILABLE and StateGraph is not None:
        return _run_langgraph_chat(request, store)
    return _run_sequential_chat(request, store)


def _run_langgraph_chat(request: ChatRequest, store: CatalogStore) -> ChatResponse:
    graph = StateGraph(_ChatState)

    def intake_node(state: _ChatState) -> dict:
        session = _load_or_create_session(
            session_id=state["request"].session_id,
            reset=state["request"].reset_session,
        )
        conversation = list(session.conversation)
        conversation.append(
            ChatTurn(
                role="user",
                content=state["request"].message.strip(),
                timestamp_utc=_utc_now(),
            )
        )
        return {
            "session_id": session.session_id,
            "profile": session.profile.model_copy(deep=True),
            "conversation": _trim_conversation(conversation),
            "llm_used": False,
        }

    def profile_node(state: _ChatState) -> dict:
        profile = state["profile"].model_copy(deep=True)
        llm_used = _extract_profile_from_message(
            message=state["request"].message,
            profile=profile,
            store=store,
            conversation=state["conversation"],
        )
        _normalize_profile(profile)
        return {"profile": profile, "llm_used": llm_used}

    def suggestion_node(state: _ChatState) -> dict:
        suggestions = _suggest_roles(state["profile"], store)
        missing = _compute_missing_fields(state["profile"], suggestions)
        ready = len(missing) == 0
        plan_draft = _build_plan_draft(state["profile"]) if ready else None
        return {
            "suggested_roles": suggestions,
            "missing_fields": missing,
            "ready_for_plan": ready,
            "plan_request_draft": plan_draft,
        }

    def response_node(state: _ChatState) -> dict:
        message, llm_response_used = _build_assistant_message(
            user_message=state["request"].message,
            profile=state["profile"],
            suggestions=state["suggested_roles"],
            missing_fields=state["missing_fields"],
            ready_for_plan=state["ready_for_plan"],
            llm_candidate=True,
        )
        conversation = list(state["conversation"])
        conversation.append(
            ChatTurn(
                role="assistant",
                content=message,
                timestamp_utc=_utc_now(),
            )
        )
        return {
            "assistant_message": message,
            "conversation": _trim_conversation(conversation),
            "llm_used": bool(state.get("llm_used", False) or llm_response_used),
        }

    def persist_node(state: _ChatState) -> dict:
        _persist_session(
            session_id=state["session_id"],
            profile=state["profile"],
            conversation=state["conversation"],
        )
        return {}

    graph.add_node("intake", intake_node)
    graph.add_node("profile", profile_node)
    graph.add_node("suggestion", suggestion_node)
    graph.add_node("response", response_node)
    graph.add_node("persist", persist_node)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "profile")
    graph.add_edge("profile", "suggestion")
    graph.add_edge("suggestion", "response")
    graph.add_edge("response", "persist")
    graph.add_edge("persist", END)

    compiled = graph.compile()
    out = compiled.invoke({"request": request})
    return ChatResponse(
        session_id=out["session_id"],
        assistant_message=out["assistant_message"],
        profile_draft=out["profile"],
        missing_fields=out["missing_fields"],
        suggested_roles=out["suggested_roles"],
        ready_for_plan=out["ready_for_plan"],
        plan_request_draft=out.get("plan_request_draft"),
        conversation=out["conversation"],
        llm_used=bool(out.get("llm_used", False)),
    )


def _run_sequential_chat(request: ChatRequest, store: CatalogStore) -> ChatResponse:
    session = _load_or_create_session(
        session_id=request.session_id,
        reset=request.reset_session,
    )
    conversation = list(session.conversation)
    conversation.append(
        ChatTurn(role="user", content=request.message.strip(), timestamp_utc=_utc_now())
    )

    profile = session.profile.model_copy(deep=True)
    llm_used = _extract_profile_from_message(
        message=request.message,
        profile=profile,
        store=store,
        conversation=conversation,
    )
    _normalize_profile(profile)

    suggestions = _suggest_roles(profile, store)
    missing = _compute_missing_fields(profile, suggestions)
    ready = len(missing) == 0
    plan_draft = _build_plan_draft(profile) if ready else None

    assistant_message, llm_response_used = _build_assistant_message(
        user_message=request.message,
        profile=profile,
        suggestions=suggestions,
        missing_fields=missing,
        ready_for_plan=ready,
        llm_candidate=True,
    )
    conversation.append(
        ChatTurn(role="assistant", content=assistant_message, timestamp_utc=_utc_now())
    )
    trimmed = _trim_conversation(conversation)
    _persist_session(session_id=session.session_id, profile=profile, conversation=trimmed)

    return ChatResponse(
        session_id=session.session_id,
        assistant_message=assistant_message,
        profile_draft=profile,
        missing_fields=missing,
        suggested_roles=suggestions,
        ready_for_plan=ready,
        plan_request_draft=plan_draft,
        conversation=trimmed,
        llm_used=bool(llm_used or llm_response_used),
    )


def _load_or_create_session(session_id: str | None, reset: bool) -> _Session:
    with _SESSION_LOCK:
        if session_id and not reset and session_id in _SESSIONS:
            return _SESSIONS[session_id]

        new_id = session_id if session_id else str(uuid.uuid4())
        session = _Session(session_id=new_id)
        _SESSIONS[new_id] = session
        return session


def _persist_session(
    session_id: str,
    profile: ChatProfileDraft,
    conversation: list[ChatTurn],
) -> None:
    with _SESSION_LOCK:
        _SESSIONS[session_id] = _Session(
            session_id=session_id,
            profile=profile.model_copy(deep=True),
            conversation=list(conversation),
        )


def _extract_profile_from_message(
    message: str,
    profile: ChatProfileDraft,
    store: CatalogStore,
    conversation: list[ChatTurn],
) -> bool:
    llm_used = _llm_extract_profile(
        message=message,
        profile=profile,
        store=store,
        conversation=conversation,
    )
    if llm_used:
        _apply_heuristics(message, profile, store)
        return True

    _apply_heuristics(message, profile, store)
    return False


def _llm_extract_profile(
    message: str,
    profile: ChatProfileDraft,
    store: CatalogStore,
    conversation: list[ChatTurn],
) -> bool:
    if not _llm_available():
        return False

    role_lines = [f"{role.role_id}: {role.title}" for role in store.roles]
    current = profile.model_dump()
    recent = [
        {"role": turn.role, "content": turn.content}
        for turn in conversation[-8:]
    ]
    schema_hint = {
        "level": "UG|GR|null",
        "mode": "CORE|FUSION|null",
        "fusion_domain": "string|null",
        "current_semester": "int|null",
        "start_term": "Fall|Spring|Summer|Winter|null",
        "include_optional_terms": "bool|null",
        "min_credits": "int|null",
        "target_credits": "int|null",
        "max_credits": "int|null",
        "degree_total_credits": "int|null",
        "interests": ["string"],
        "completed_courses": ["COURSE-ID"],
        "preferred_role_id": "ROLE_ID|null",
    }

    system_prompt = (
        "Extract structured planning profile from conversation. "
        "Return only valid JSON object. Unknown fields must be null or empty list."
    )
    user_prompt = json.dumps(
        {
            "instruction": "Extract/refresh profile fields from latest message and context.",
            "latest_user_message": message,
            "current_profile": current,
            "recent_conversation": recent,
            "valid_roles": role_lines,
            "required_output_schema": schema_hint,
        },
        ensure_ascii=True,
    )

    content = _llm_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        json_mode=True,
        task="chat",
    )
    if not content:
        return False

    payload = _safe_parse_json_object(content)
    if not isinstance(payload, dict):
        return False

    _merge_profile_payload(profile, payload, store)
    return True


def _apply_heuristics(message: str, profile: ChatProfileDraft, store: CatalogStore) -> None:
    text = message.lower()
    role_by_title = {role.title.lower(): role.role_id for role in store.roles}
    fusion_role_ids = {profile_item.role_id for profile_item in store.fusion_role_profiles}

    if re.search(r"\b(undergrad|undergraduate|ug)\b", text):
        profile.level = "UG"
    if re.search(r"\b(graduate|grad|masters|master's|ms|phd)\b", text):
        profile.level = "GR"

    if "fusion" in text or "domain + tech" in text or "domain and tech" in text:
        profile.mode = "FUSION"
    if "core mode" in text or "core role" in text:
        profile.mode = "CORE"

    if "fall" in text:
        profile.start_term = "Fall"
    elif "spring" in text:
        profile.start_term = "Spring"
    elif "summer" in text:
        profile.start_term = "Summer"
    elif "winter" in text:
        profile.start_term = "Winter"

    sem_match = re.search(r"\b(?:semester|sem)\s*([1-9]|1[0-2])\b", text)
    if sem_match:
        profile.current_semester = int(sem_match.group(1))

    completed = re.findall(r"\b[A-Z]{2,5}-\d{3}[A-Z]?\b", message)
    if completed:
        merged = set(profile.completed_courses)
        for cid in completed:
            merged.add(cid.upper())
        profile.completed_courses = sorted(merged)

    for title_lower, role_id in role_by_title.items():
        if title_lower in text:
            if profile.mode == "FUSION" and role_id not in fusion_role_ids:
                continue
            profile.preferred_role_id = role_id
            break

    domain_terms = [
        "finance",
        "biology",
        "healthcare",
        "policy",
        "operations",
        "marketing",
        "cybersecurity",
    ]
    for term in domain_terms:
        if term in text:
            profile.fusion_domain = term.title()
            break

    interests = _extract_interest_terms(message)
    if interests:
        merged_interests = list(dict.fromkeys(profile.interests + interests))
        profile.interests = merged_interests[:10]


def _extract_interest_terms(message: str) -> list[str]:
    text = message.strip()
    if not text:
        return []

    keywords = [
        "ai",
        "machine learning",
        "data",
        "analytics",
        "software",
        "cloud",
        "security",
        "finance",
        "biology",
        "healthcare",
        "policy",
        "marketing",
        "operations",
        "risk",
        "quant",
    ]
    lower = text.lower()
    found = [k for k in keywords if k in lower]
    if found:
        return found[:6]

    course_like = re.findall(r"\b[A-Z]{2,5}-\d{3}[A-Z]?\b", text)
    if course_like and len(text.split()) <= 8:
        return []

    raw_parts = [p.strip() for p in re.split(r"[,\|;/]", text) if p.strip()]
    if len(raw_parts) >= 2:
        cleaned = []
        for part in raw_parts:
            item = _clean_interest(part)
            if not item:
                continue
            if len(item.split()) > 4:
                continue
            cleaned.append(item)
        return [p for p in cleaned if p]

    patterns = [
        r"interested in ([a-z0-9\s\-/+]+)",
        r"interests?\s*[:\-]\s*([a-z0-9\s,\-/+]+)",
        r"i like ([a-z0-9\s\-/+]+)",
        r"focus on ([a-z0-9\s\-/+]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, lower)
        if not match:
            continue
        segment = match.group(1)
        parts = []
        for item in re.split(r"[,/]", segment):
            cleaned = _clean_interest(item)
            if not cleaned:
                continue
            if len(cleaned.split()) > 4:
                continue
            parts.append(cleaned)
        out = [p for p in parts if p]
        if out:
            return out

    return []


def _clean_interest(value: str) -> str:
    out = re.sub(r"\s+", " ", value.strip().lower())
    out = re.sub(r"[^a-z0-9\s\-/+]", "", out)
    if len(out) < 2:
        return ""
    return out


def _merge_profile_payload(
    profile: ChatProfileDraft,
    payload: dict,
    store: CatalogStore,
) -> None:
    level = payload.get("level")
    if isinstance(level, str) and level in {"UG", "GR"}:
        profile.level = level

    mode = payload.get("mode")
    if isinstance(mode, str) and mode in {"CORE", "FUSION"}:
        profile.mode = mode

    fusion_domain = payload.get("fusion_domain")
    if fusion_domain is None:
        pass
    elif isinstance(fusion_domain, str):
        profile.fusion_domain = fusion_domain.strip() or None

    current_semester = payload.get("current_semester")
    if isinstance(current_semester, int) and 1 <= current_semester <= 12:
        profile.current_semester = current_semester

    start_term = payload.get("start_term")
    if isinstance(start_term, str) and start_term in {"Fall", "Spring", "Summer", "Winter"}:
        profile.start_term = start_term

    include_optional_terms = payload.get("include_optional_terms")
    if isinstance(include_optional_terms, bool):
        profile.include_optional_terms = include_optional_terms

    for field_name in ("min_credits", "target_credits", "max_credits"):
        value = payload.get(field_name)
        if isinstance(value, int) and 0 <= value <= 30:
            setattr(profile, field_name, value)

    degree_total = payload.get("degree_total_credits")
    if isinstance(degree_total, int) and 1 <= degree_total <= 200:
        profile.degree_total_credits = degree_total

    interests = payload.get("interests")
    if isinstance(interests, list):
        cleaned = [
            _clean_interest(str(item))
            for item in interests
            if isinstance(item, str)
        ]
        profile.interests = [item for item in dict.fromkeys(cleaned) if item][:10]

    completed_courses = payload.get("completed_courses")
    if isinstance(completed_courses, list):
        normalized = []
        for course_id in completed_courses:
            if not isinstance(course_id, str):
                continue
            cid = course_id.strip().upper()
            if re.fullmatch(r"[A-Z]{2,5}-\d{3}[A-Z]?", cid):
                normalized.append(cid)
        profile.completed_courses = list(dict.fromkeys(normalized))

    preferred_role_id = payload.get("preferred_role_id")
    if isinstance(preferred_role_id, str) and preferred_role_id in store.roles_by_id:
        profile.preferred_role_id = preferred_role_id


def _normalize_profile(profile: ChatProfileDraft) -> None:
    if profile.level == "GR":
        if profile.min_credits == 12 and profile.target_credits == 15 and profile.max_credits == 17:
            profile.min_credits = 9
            profile.target_credits = 9
            profile.max_credits = 12
    else:
        if profile.min_credits == 9 and profile.target_credits == 9 and profile.max_credits == 12:
            profile.min_credits = 12
            profile.target_credits = 15
            profile.max_credits = 17

    profile.target_credits = max(profile.min_credits, min(profile.target_credits, profile.max_credits))
    profile.current_semester = max(1, min(profile.current_semester, 12))
    profile.interests = [item for item in dict.fromkeys(profile.interests) if item][:10]
    profile.completed_courses = sorted(
        {cid for cid in profile.completed_courses if re.fullmatch(r"[A-Z]{2,5}-\d{3}[A-Z]?", cid)}
    )


def _suggest_roles(profile: ChatProfileDraft, store: CatalogStore) -> list[ChatRoleSuggestion]:
    retriever = _get_retriever(store)
    fusion_role_ids = {item.role_id for item in store.fusion_role_profiles}

    if profile.interests:
        candidate_ids = retriever.retrieve_roles_by_interest(profile.interests, top_k=8)
    else:
        candidate_ids = [role.role_id for role in store.roles[:8]]

    if profile.mode == "FUSION" and fusion_role_ids:
        candidate_ids = [role_id for role_id in candidate_ids if role_id in fusion_role_ids]
        if not candidate_ids:
            candidate_ids = sorted(fusion_role_ids)[:5]

    seen: set[str] = set()
    ordered: list[str] = []
    if profile.preferred_role_id and profile.preferred_role_id in store.roles_by_id:
        if profile.mode != "FUSION" or profile.preferred_role_id in fusion_role_ids:
            ordered.append(profile.preferred_role_id)
            seen.add(profile.preferred_role_id)
    for role_id in candidate_ids:
        if role_id in store.roles_by_id and role_id not in seen:
            ordered.append(role_id)
            seen.add(role_id)
        if len(ordered) >= 5:
            break

    if not profile.preferred_role_id and ordered:
        profile.preferred_role_id = ordered[0]

    out = []
    for role_id in ordered:
        role = store.roles_by_id.get(role_id)
        if not role:
            continue
        out.append(ChatRoleSuggestion(role_id=role_id, title=role.title))
    return out


def _compute_missing_fields(
    profile: ChatProfileDraft,
    suggestions: list[ChatRoleSuggestion],
) -> list[str]:
    missing: list[str] = []
    if not profile.interests:
        missing.append("interests")
    if profile.mode == "FUSION" and not profile.fusion_domain:
        missing.append("fusion_domain")
    if not profile.preferred_role_id:
        if suggestions:
            profile.preferred_role_id = suggestions[0].role_id
        else:
            missing.append("preferred_role_id")
    return missing


def _build_plan_draft(profile: ChatProfileDraft) -> PlanRequest | None:
    try:
        return PlanRequest(
            student_profile=StudentProfile(
                level=profile.level,
                mode=profile.mode,
                goal_type=profile.goal_type,
                confidence_level=profile.confidence_level,
                hours_per_week=profile.hours_per_week,
                fusion_domain=profile.fusion_domain,
                current_semester=profile.current_semester,
                start_term=profile.start_term,
                include_optional_terms=profile.include_optional_terms,
                completed_courses=list(profile.completed_courses),
                min_credits=profile.min_credits,
                target_credits=profile.target_credits,
                max_credits=profile.max_credits,
                degree_total_credits=profile.degree_total_credits,
                interests=list(profile.interests),
            ),
            preferred_role_id=profile.preferred_role_id,
        )
    except Exception:
        return None


def _build_assistant_message(
    user_message: str,
    profile: ChatProfileDraft,
    suggestions: list[ChatRoleSuggestion],
    missing_fields: list[str],
    ready_for_plan: bool,
    llm_candidate: bool,
) -> tuple[str, bool]:
    if llm_candidate:
        llm_text = _llm_generate_assistant_message(
            user_message=user_message,
            profile=profile,
            suggestions=suggestions,
            missing_fields=missing_fields,
            ready_for_plan=ready_for_plan,
        )
        if llm_text:
            return llm_text, True

    top_roles = ", ".join([item.title for item in suggestions[:3]]) if suggestions else "None yet"
    summary = (
        f"Captured profile: level={profile.level}, mode={profile.mode}, "
        f"term={profile.start_term}, semester={profile.current_semester}, "
        f"interests={', '.join(profile.interests) if profile.interests else 'not set'}."
    )
    if ready_for_plan:
        return (
            f"{summary}\n"
            f"Top role suggestions: {top_roles}.\n"
            "I have enough context to generate a plan. Use 'Generate Plan From Chat Draft'."
        ), False

    question = _missing_field_question(missing_fields)
    return (
        f"{summary}\n"
        f"Top role suggestions: {top_roles}.\n"
        f"Next step: {question}"
    ), False


def _llm_generate_assistant_message(
    user_message: str,
    profile: ChatProfileDraft,
    suggestions: list[ChatRoleSuggestion],
    missing_fields: list[str],
    ready_for_plan: bool,
) -> str | None:
    if not _llm_available():
        return None

    role_preview = [
        {"role_id": item.role_id, "title": item.title}
        for item in suggestions[:5]
    ]
    system_prompt = (
        "You are Sanjaya AI intake assistant. "
        "Be concise, grounded, and ask at most one follow-up question. "
        "Do not promise jobs. Mention readiness when sufficient."
    )
    user_prompt = json.dumps(
        {
            "latest_user_message": user_message,
            "profile_draft": profile.model_dump(),
            "role_suggestions": role_preview,
            "missing_fields": missing_fields,
            "ready_for_plan": ready_for_plan,
        },
        ensure_ascii=True,
    )
    return _llm_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        json_mode=False,
        task="chat",
    )


def _missing_field_question(missing_fields: list[str]) -> str:
    if not missing_fields:
        return "Please confirm and proceed."
    key = missing_fields[0]
    prompts = {
        "interests": "Tell me your top interests (comma-separated), e.g., analytics, finance, optimization.",
        "fusion_domain": "Which non-tech domain should we combine with technology (e.g., Finance, Biology, Policy)?",
        "preferred_role_id": "Which role do you want to target from the suggested options?",
    }
    return prompts.get(key, "Provide one more detail to continue.")


def _safe_parse_json_object(content: str) -> dict | None:
    content = content.strip()
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return None
    return None


def _llm_available() -> bool:
    provider, _, _, _ = _resolve_llm_target(task="chat")
    return provider is not None


def _resolve_llm_target(task: str) -> tuple[str | None, str, str, str]:
    provider_pref = os.getenv("LLM_PROVIDER", "auto").strip().lower()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    if task == "chat":
        openai_model = (
            os.getenv("OPENAI_MODEL_CHAT", "").strip()
            or os.getenv("OPENAI_MODEL", "").strip()
            or "gpt-4o-mini"
        )
        gemini_model = (
            os.getenv("GEMINI_MODEL_CHAT", "").strip()
            or os.getenv("GEMINI_MODEL", "").strip()
            or "gemini-2.0-flash"
        )
        groq_model = (
            os.getenv("GROQ_MODEL_CHAT", "").strip()
            or os.getenv("GROQ_MODEL", "").strip()
            or "llama-3.3-70b-versatile"
        )
    else:
        openai_model = (
            os.getenv("OPENAI_MODEL", "").strip()
            or "gpt-4o-mini"
        )
        gemini_model = (
            os.getenv("GEMINI_MODEL", "").strip()
            or "gemini-2.0-flash"
        )
        groq_model = (
            os.getenv("GROQ_MODEL", "").strip()
            or "llama-3.3-70b-versatile"
        )

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


def _llm_chat_completion(
    messages: list[dict],
    json_mode: bool,
    task: str,
) -> str | None:
    provider, api_key, model, endpoint = _resolve_llm_target(task=task)
    if not provider:
        return None

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 700,
    }
    if json_mode and provider != "gemini":
        payload["response_format"] = {"type": "json_object"}

    raw = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        url=endpoint,
        data=raw,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    retries = 2
    transient_http_codes = {408, 409, 425, 429, 500, 502, 503, 504}

    for attempt in range(retries + 1):
        try:
            with urllib_request.urlopen(req, timeout=60) as response:
                text = response.read().decode("utf-8")
        except urllib_error.HTTPError as exc:
            if exc.code in transient_http_codes and attempt < retries:
                time.sleep(1.2 * (attempt + 1))
                continue
            return None
        except (urllib_error.URLError, TimeoutError):
            if attempt < retries:
                time.sleep(1.2 * (attempt + 1))
                continue
            return None

        try:
            parsed = json.loads(text)
            content = (
                parsed.get("choices", [{}])[0]
                .get("message", {})
                .get("content")
            )
            return content if isinstance(content, str) and content.strip() else None
        except Exception:
            if attempt < retries:
                time.sleep(0.8 * (attempt + 1))
                continue
            return None

    return None


def _trim_conversation(conversation: list[ChatTurn], keep_last: int = 24) -> list[ChatTurn]:
    if len(conversation) <= keep_last:
        return conversation
    return conversation[-keep_last:]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _get_retriever(store: CatalogStore) -> MarketEvidenceRetriever:
    cache_key = id(store)
    retriever = _RETRIEVER_CACHE.get(cache_key)
    if retriever is None:
        retriever = MarketEvidenceRetriever(store)
        _RETRIEVER_CACHE[cache_key] = retriever
    return retriever
