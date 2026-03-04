from __future__ import annotations

import json
import logging
import os
import time
from typing import TypedDict
import uuid

from ..analytics.events import (
    log_plan_created,
    log_role_search,
    log_unknown_role_request,
    normalize_role_query,
)
from ..analytics.role_requests import upsert_unknown_role_request
from ..cache import LruCache
from ..data_loader import CatalogStore
from ..plan_store import get_plan_store
from ..rag import MarketEvidenceRetriever
from ..schemas.plan import CandidateRole, PlanError, PlanRequest, PlanResponse
from ..validators.plan_verifier import check_evidence_integrity
from .fingerprint import compute_plan_id
from .gap_engine import build_gap_report
from .plan_enrichment import enrich_plan_outputs
from .planner import build_plan
from .reality_attach import attach_role_reality
from .repair import repair_once, retryable_errors

try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency guard
    END = "__end__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False


class WorkflowState(TypedDict, total=False):
    request_id: str
    request: PlanRequest
    selected_role_id: str
    candidate_role_ids: list[str]
    candidate_roles: list[CandidateRole]
    role_request_warning: PlanError | None
    draft_plan: PlanResponse
    validation_errors: list[PlanError]
    retries: int
    retry_codes: list[str]
    retry_required: bool
    agent_trace: list[str]
    node_timings: list[dict[str, int | str]]


_RETRIEVER_CACHE: dict[int, MarketEvidenceRetriever] = {}
_PLAN_CACHE: LruCache[PlanResponse] = LruCache()
LOGGER = logging.getLogger(__name__)


def run_plan_workflow(request: PlanRequest, store: CatalogStore) -> PlanResponse:
    data_version = store.data_version or "unknown"
    plan_id = compute_plan_id(request, data_version)
    cache_started = time.perf_counter()
    cached = _PLAN_CACHE.get(plan_id)
    if cached is not None:
        cache_total_ms = int((time.perf_counter() - cache_started) * 1000)
        response = _hydrate_cached_plan(
            cached,
            plan_id=plan_id,
            data_version=data_version,
            timing_ms=cache_total_ms,
        )
        _emit_audit_log(
            request_id=response.request_id,
            selected_role_id=response.selected_role_id,
            retries=0,
            retry_codes=[],
            final_error_codes=[error.code for error in response.validation_errors],
            vector_status=_infer_vector_status(response),
            total_time_ms=cache_total_ms,
        )
        get_plan_store().put(plan_id, response)
        _log_plan_analytics(request=request, response=response)
        return response

    retriever = _get_retriever(store)
    if LANGGRAPH_AVAILABLE and StateGraph is not None:
        response = _run_langgraph(request, store, retriever)
    else:
        response = _run_fallback(request, store, retriever)

    response.plan_id = plan_id
    response.data_version = data_version
    response.cache_status = "miss"
    _PLAN_CACHE.set(plan_id, _prepare_for_cache(response))
    get_plan_store().put(plan_id, response)
    _log_plan_analytics(request=request, response=response)
    return response


def get_retriever_for_store(
    store: CatalogStore,
    *,
    create_if_missing: bool = True,
) -> MarketEvidenceRetriever | None:
    cache_key = id(store)
    retriever = _RETRIEVER_CACHE.get(cache_key)
    if retriever is None and create_if_missing:
        retriever = _get_retriever(store)
    return retriever


def reset_plan_cache(max_size: int | None = None) -> None:
    global _PLAN_CACHE
    _PLAN_CACHE = LruCache(max_size=max_size)


def _run_langgraph(
    request: PlanRequest,
    store: CatalogStore,
    retriever: MarketEvidenceRetriever,
) -> PlanResponse:
    run_started = time.perf_counter()
    graph = StateGraph(WorkflowState)

    def intake_node(state: WorkflowState) -> dict:
        started = time.perf_counter()
        trace = list(state.get("agent_trace", []))
        request_id = state["request_id"]
        if not any(item.startswith("request_id:") for item in trace):
            trace.append(f"request_id:{request_id}")
        trace.append("intake: normalized student profile into planner state")
        timings = list(state.get("node_timings", []))
        timings.append(_node_timing("intake", started))
        return {"agent_trace": trace, "node_timings": timings}

    def role_retrieval_node(state: WorkflowState) -> dict:
        started = time.perf_counter()
        trace = list(state.get("agent_trace", []))
        selected_role_id, candidates, candidate_roles, unresolved_warning = _resolve_role_candidates(
            state["request"],
            store,
            retriever,
        )
        trace.append(
            f"role_retrieval: selected {selected_role_id} from {len(candidates)} candidates"
        )
        trace.extend(_role_retrieval_trace_lines(retriever))
        timings = list(state.get("node_timings", []))
        timings.append(_node_timing("role_retrieval", started))
        return {
            "selected_role_id": selected_role_id,
            "candidate_role_ids": candidates,
            "candidate_roles": candidate_roles,
            "role_request_warning": unresolved_warning,
            "agent_trace": trace,
            "node_timings": timings,
        }

    def planner_node(state: WorkflowState) -> dict:
        started = time.perf_counter()
        trace = list(state.get("agent_trace", []))
        plan_request = state["request"].model_copy(deep=True)
        plan_request.preferred_role_id = state.get("selected_role_id")
        draft_plan = build_plan(plan_request, store)
        trace.append(
            f"planner: produced {len(draft_plan.semesters)} semesters with "
            f"{len(draft_plan.validation_errors)} validation errors"
        )
        timings = list(state.get("node_timings", []))
        timings.append(_node_timing("planner", started))
        return {
            "draft_plan": draft_plan,
            "validation_errors": list(draft_plan.validation_errors),
            "agent_trace": trace,
            "node_timings": timings,
        }

    def verifier_node(state: WorkflowState) -> dict:
        started = time.perf_counter()
        trace = list(state.get("agent_trace", []))
        retries = int(state.get("retries", 0))
        errors = list(state.get("validation_errors", []))
        retryable = retryable_errors(errors)
        retry_codes = list(state.get("retry_codes", []))

        if retryable and retries < 1:
            patched, metadata = repair_once(
                request=state["request"],
                draft_plan=state["draft_plan"],
                errors=retryable,
                store=store,
            )
            for code in sorted({error.code for error in retryable}):
                if code not in retry_codes:
                    retry_codes.append(code)
            for event in metadata.get("trace_events", []):
                trace.append(event)
            trace.append("verifier: retrying planner after deterministic repair")
            timings = list(state.get("node_timings", []))
            timings.append(_node_timing("verifier", started))
            return {
                "request": patched,
                "retries": retries + 1,
                "retry_required": True,
                "agent_trace": trace,
                "retry_codes": retry_codes,
                "node_timings": timings,
            }

        if errors:
            if retryable and retries >= 1:
                trace.append("verifier: retry budget exhausted for retryable errors")
            elif retryable:
                trace.append("verifier: retryable errors detected but repair unavailable")
            else:
                trace.append("verifier: non-retryable validation issues detected")
        else:
            trace.append("verifier: plan passed structural validation checks")
        timings = list(state.get("node_timings", []))
        timings.append(_node_timing("verifier", started))
        return {"retry_required": False, "agent_trace": trace, "node_timings": timings}

    def evidence_node(state: WorkflowState) -> dict:
        started = time.perf_counter()
        trace = list(state.get("agent_trace", []))
        draft = state["draft_plan"]
        role = store.roles_by_id[draft.selected_role_id]

        evidence_panel = retriever.retrieve_role_evidence(role=role, top_k=10)
        course_cards = retriever.build_course_purpose_cards(
            plan=draft,
            role=role,
            evidence_panel=evidence_panel,
        )
        draft.evidence_panel = evidence_panel
        draft.course_purpose_cards = course_cards
        draft.candidate_roles = list(state.get("candidate_roles", []))
        role_request_warning = state.get("role_request_warning")
        if role_request_warning is not None:
            draft.validation_errors.append(role_request_warning)
        draft.validation_errors.extend(check_evidence_integrity(draft))
        role_reality, reality_warnings = attach_role_reality(draft, store)
        draft.role_reality = role_reality
        draft.validation_errors.extend(reality_warnings)
        draft.intake_snapshot = state["request"].student_profile.model_copy(deep=True)
        draft.gap_report = build_gap_report(
            draft,
            store,
            confidence_level=draft.intake_snapshot.confidence_level,
            hours_per_week=draft.intake_snapshot.hours_per_week,
        )
        enrich_plan_outputs(
            plan=draft,
            request=state["request"],
            store=store,
        )
        vector_status = "enabled" if retriever.using_chroma else "fallback_lexical"
        trace.append(f"evidence: attached {len(evidence_panel)} evidence snippets via {vector_status}")
        trace.extend(_evidence_retrieval_trace_lines(retriever))
        timings = list(state.get("node_timings", []))
        timings.append(_node_timing("evidence", started))
        draft.request_id = state["request_id"]
        draft.node_timings = timings
        draft.agent_trace = trace
        return {"draft_plan": draft, "agent_trace": trace, "node_timings": timings}

    def verifier_route(state: WorkflowState) -> str:
        return "retry" if state.get("retry_required") else "evidence"

    graph.add_node("intake", intake_node)
    graph.add_node("role_retrieval", role_retrieval_node)
    graph.add_node("planner", planner_node)
    graph.add_node("verifier", verifier_node)
    graph.add_node("evidence", evidence_node)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "role_retrieval")
    graph.add_edge("role_retrieval", "planner")
    graph.add_edge("planner", "verifier")
    graph.add_conditional_edges(
        "verifier",
        verifier_route,
        {"retry": "planner", "evidence": "evidence"},
    )
    graph.add_edge("evidence", END)

    compiled = graph.compile()
    out = compiled.invoke(
        {
            "request_id": str(uuid.uuid4()),
            "request": request,
            "retries": 0,
            "retry_codes": [],
            "retry_required": False,
            "agent_trace": [],
            "node_timings": [],
        }
    )
    draft = out["draft_plan"]
    _emit_audit_log(
        request_id=draft.request_id,
        selected_role_id=draft.selected_role_id,
        retries=int(out.get("retries", 0)),
        retry_codes=list(out.get("retry_codes", [])),
        final_error_codes=[error.code for error in draft.validation_errors],
        vector_status="enabled" if retriever.using_chroma else "fallback_lexical",
        total_time_ms=int((time.perf_counter() - run_started) * 1000),
        role_top1=_audit_top1_value(retriever.get_last_role_diagnostics(), "role_id"),
        evidence_top1=_audit_top1_value(retriever.get_last_evidence_diagnostics(), "evidence_id"),
    )
    return draft


def _run_fallback(
    request: PlanRequest,
    store: CatalogStore,
    retriever: MarketEvidenceRetriever,
) -> PlanResponse:
    run_started = time.perf_counter()
    state: WorkflowState = {
        "request_id": str(uuid.uuid4()),
        "request": request,
        "retries": 0,
        "retry_codes": [],
        "agent_trace": [],
        "node_timings": [],
    }
    state["agent_trace"].append(f"request_id:{state['request_id']}")
    state["agent_trace"].append(
        "workflow: langgraph unavailable, using deterministic sequential fallback"
    )

    intake_started = time.perf_counter()
    state["node_timings"].append(_node_timing("intake", intake_started))

    role_started = time.perf_counter()
    selected_role_id, candidates, candidate_roles, unresolved_warning = _resolve_role_candidates(
        request,
        store,
        retriever,
    )
    state["selected_role_id"] = selected_role_id
    state["candidate_role_ids"] = candidates
    state["candidate_roles"] = candidate_roles
    state["role_request_warning"] = unresolved_warning
    state["agent_trace"].append(
        f"role_retrieval: selected {selected_role_id} from {len(candidates)} candidates"
    )
    state["agent_trace"].extend(_role_retrieval_trace_lines(retriever))
    state["node_timings"].append(_node_timing("role_retrieval", role_started))

    max_retries = 1
    while True:
        planner_started = time.perf_counter()
        plan_request = state["request"].model_copy(deep=True)
        plan_request.preferred_role_id = state["selected_role_id"]
        draft_plan = build_plan(plan_request, store)
        state["draft_plan"] = draft_plan
        state["validation_errors"] = list(draft_plan.validation_errors)
        state["agent_trace"].append(
            f"planner: produced {len(draft_plan.semesters)} semesters with "
            f"{len(draft_plan.validation_errors)} validation errors"
        )
        state["node_timings"].append(_node_timing("planner", planner_started))

        verifier_started = time.perf_counter()
        errors = state["validation_errors"]
        retries = int(state.get("retries", 0))
        retryable = retryable_errors(errors)
        if retryable and retries < max_retries:
            patched, metadata = repair_once(
                request=state["request"],
                draft_plan=state["draft_plan"],
                errors=retryable,
                store=store,
            )
            for code in sorted({error.code for error in retryable}):
                if code not in state["retry_codes"]:
                    state["retry_codes"].append(code)
            state["request"] = patched
            state["retries"] = retries + 1
            for event in metadata.get("trace_events", []):
                state["agent_trace"].append(event)
            state["agent_trace"].append(
                "verifier: retrying planner after deterministic repair"
            )
            state["node_timings"].append(_node_timing("verifier", verifier_started))
            continue
        if errors:
            if retryable and retries >= max_retries:
                state["agent_trace"].append(
                    "verifier: retry budget exhausted for retryable errors"
                )
            else:
                state["agent_trace"].append(
                    "verifier: non-retryable validation issues detected"
                )
        else:
            state["agent_trace"].append("verifier: plan passed structural validation checks")
        state["node_timings"].append(_node_timing("verifier", verifier_started))
        break

    evidence_started = time.perf_counter()
    role = store.roles_by_id[state["draft_plan"].selected_role_id]
    evidence_panel = retriever.retrieve_role_evidence(role=role, top_k=10)
    course_cards = retriever.build_course_purpose_cards(
        plan=state["draft_plan"],
        role=role,
        evidence_panel=evidence_panel,
    )
    state["draft_plan"].evidence_panel = evidence_panel
    state["draft_plan"].course_purpose_cards = course_cards
    state["draft_plan"].candidate_roles = list(state.get("candidate_roles", []))
    role_request_warning = state.get("role_request_warning")
    if role_request_warning is not None:
        state["draft_plan"].validation_errors.append(role_request_warning)
    state["draft_plan"].validation_errors.extend(check_evidence_integrity(state["draft_plan"]))
    role_reality, reality_warnings = attach_role_reality(state["draft_plan"], store)
    state["draft_plan"].role_reality = role_reality
    state["draft_plan"].validation_errors.extend(reality_warnings)
    state["draft_plan"].intake_snapshot = state["request"].student_profile.model_copy(deep=True)
    state["draft_plan"].gap_report = build_gap_report(
        state["draft_plan"],
        store,
        confidence_level=state["draft_plan"].intake_snapshot.confidence_level,
        hours_per_week=state["draft_plan"].intake_snapshot.hours_per_week,
    )
    enrich_plan_outputs(
        plan=state["draft_plan"],
        request=state["request"],
        store=store,
    )
    vector_status = "enabled" if retriever.using_chroma else "fallback_lexical"
    state["agent_trace"].append(
        f"evidence: attached {len(evidence_panel)} evidence snippets via {vector_status}"
    )
    state["agent_trace"].extend(_evidence_retrieval_trace_lines(retriever))
    state["node_timings"].append(_node_timing("evidence", evidence_started))
    state["draft_plan"].request_id = state["request_id"]
    state["draft_plan"].node_timings = state["node_timings"]
    state["draft_plan"].agent_trace = state["agent_trace"]
    _emit_audit_log(
        request_id=state["draft_plan"].request_id,
        selected_role_id=state["draft_plan"].selected_role_id,
        retries=int(state.get("retries", 0)),
        retry_codes=list(state.get("retry_codes", [])),
        final_error_codes=[error.code for error in state["draft_plan"].validation_errors],
        vector_status=vector_status,
        total_time_ms=int((time.perf_counter() - run_started) * 1000),
        role_top1=_audit_top1_value(retriever.get_last_role_diagnostics(), "role_id"),
        evidence_top1=_audit_top1_value(retriever.get_last_evidence_diagnostics(), "evidence_id"),
    )
    return state["draft_plan"]


def _resolve_role_candidates(
    request: PlanRequest,
    store: CatalogStore,
    retriever: MarketEvidenceRetriever,
) -> tuple[str, list[str], list[CandidateRole], PlanError | None]:
    preferred_role_id = request.preferred_role_id
    top_k = _topk_roles_from_env()
    interest_terms = list(request.student_profile.interests)
    requested_role_text = (request.requested_role_text or "").strip()
    if requested_role_text:
        interest_terms.append(requested_role_text)
    ranked = retriever.retrieve_roles_by_interest_scored(
        interest_terms,
        top_k=max(top_k, 5),
    )
    fusion_role_ids = {profile.role_id for profile in store.fusion_role_profiles}
    if request.student_profile.mode == "FUSION" and fusion_role_ids:
        ranked = [item for item in ranked if item["role_id"] in fusion_role_ids]

    if not ranked:
        ranked = [
            {
                "role_id": role.role_id,
                "score": 0.0,
                "bm25": 0.0,
                "vector": 0.0,
                "overlap_tokens": 0,
                "phrase_hits": 0,
            }
            for role in store.roles[:max(top_k, 1)]
            if request.student_profile.mode != "FUSION" or role.role_id in fusion_role_ids
        ]

    candidate_roles = _build_candidate_roles(ranked, request, store, retriever, top_k=top_k)
    if not candidate_roles:
        fallback_role = (
            store.roles_by_id.get(preferred_role_id)
            if preferred_role_id and preferred_role_id in store.roles_by_id
            else store.roles[0]
        )
        candidate_roles = [
            CandidateRole(
                role_id=fallback_role.role_id,
                role_title=fallback_role.title,
                score=0.0,
                reasons=["Fallback candidate due to empty retrieval output."],
            )
        ]

    # If the student explicitly selected a preferred role, honor it by
    # making that role the first candidate when available.
    if preferred_role_id:
        # Try to move an existing candidate to the front.
        idx = next(
            (i for i, item in enumerate(candidate_roles) if item.role_id == preferred_role_id),
            None,
        )
        if idx is not None:
            if idx != 0:
                candidate_roles.insert(0, candidate_roles.pop(idx))
        else:
            # If retrieval did not return the preferred role but it exists
            # in the catalog, prepend it as a candidate.
            role = store.roles_by_id.get(preferred_role_id)
            if role is not None:
                candidate_roles.insert(
                    0,
                    CandidateRole(
                        role_id=role.role_id,
                        role_title=role.title,
                        score=0.0,
                        reasons=["Explicitly selected by student as preferred_role_id."],
                    ),
                )

    selected_role_id = candidate_roles[0].role_id
    candidates = [item.role_id for item in candidate_roles]
    unresolved_warning = _requested_role_warning(
        request=request,
        candidate_roles=candidate_roles,
    )
    return selected_role_id, candidates, candidate_roles, unresolved_warning


def _topk_roles_from_env(default_value: int = 3) -> int:
    raw = os.getenv("SANJAYA_TOPK_ROLES", "").strip()
    if not raw:
        return default_value
    try:
        parsed = int(raw)
    except ValueError:
        return default_value
    return max(1, parsed)


def _role_match_min_score(default_value: float = 0.35) -> float:
    raw = os.getenv("SANJAYA_ROLE_MATCH_MIN_SCORE", "").strip()
    if not raw:
        return default_value
    try:
        parsed = float(raw)
    except ValueError:
        return default_value
    return max(0.0, min(1.0, parsed))


def _build_candidate_roles(
    ranked: list[dict],
    request: PlanRequest,
    store: CatalogStore,
    retriever: MarketEvidenceRetriever,
    *,
    top_k: int,
) -> list[CandidateRole]:
    out: list[CandidateRole] = []
    for item in ranked:
        role = store.roles_by_id.get(item["role_id"])
        if not role:
            continue
        mapped_skills, total_skills = retriever.role_required_skills_match_count(role.role_id)
        evidence_score = retriever.role_trust_weighted_evidence_availability(role.role_id)
        reasons = [
            (
                f"Interest overlap tokens: {int(item.get('overlap_tokens', 0))}; "
                f"phrase hits: {int(item.get('phrase_hits', 0))}."
            ),
            f"Required skills with course matches: {mapped_skills}/{total_skills}.",
            f"Trust-weighted evidence availability: {round(evidence_score, 3)}.",
        ]
        if request.preferred_role_id and role.role_id == request.preferred_role_id:
            reasons.append("Matches requested preferred_role_id from input.")
        out.append(
            CandidateRole(
                role_id=role.role_id,
                role_title=role.title,
                score=float(item.get("score", 0.0)),
                reasons=reasons,
            )
        )

    out.sort(key=lambda role: (-role.score, role.role_id))
    return out[:top_k]


def _requested_role_warning(
    *,
    request: PlanRequest,
    candidate_roles: list[CandidateRole],
) -> PlanError | None:
    requested = (request.requested_role_text or "").strip()
    if not requested:
        return None
    top1_score = float(candidate_roles[0].score) if candidate_roles else 0.0
    threshold = _role_match_min_score()
    if top1_score >= threshold:
        return None
    return PlanError(
        code="ROLE_REQUEST_UNRESOLVED",
        message=(
            f"Requested role text '{requested}' did not map confidently to an existing curated role."
        ),
        details={
            "severity": "warning",
            "role_query_norm": normalize_role_query(requested),
            "top1_score": top1_score,
            "threshold": threshold,
        },
    )


def _get_retriever(store: CatalogStore) -> MarketEvidenceRetriever:
    cache_key = id(store)
    retriever = _RETRIEVER_CACHE.get(cache_key)
    if retriever is None:
        retriever = MarketEvidenceRetriever(store)
        _RETRIEVER_CACHE[cache_key] = retriever
    return retriever


def _prepare_for_cache(response: PlanResponse) -> PlanResponse:
    cached = response.model_copy(deep=True)
    cached.request_id = ""
    cached.node_timings = []
    cached.cache_status = "miss"
    cached.agent_trace = [
        entry for entry in cached.agent_trace if not entry.startswith("request_id:")
    ]
    return cached


def _hydrate_cached_plan(
    cached: PlanResponse,
    *,
    plan_id: str,
    data_version: str,
    timing_ms: int,
) -> PlanResponse:
    out = cached.model_copy(deep=True)
    request_id = str(uuid.uuid4())
    out.request_id = request_id
    out.plan_id = plan_id
    out.data_version = data_version
    out.cache_status = "hit"
    out.node_timings = _cache_hit_timings(timing_ms)
    trace = [entry for entry in out.agent_trace if not entry.startswith("request_id:")]
    out.agent_trace = [f"request_id:{request_id}", *trace, "cache: hit deterministic plan fingerprint"]
    return out


def _cache_hit_timings(timing_ms: int) -> list[dict[str, int | str]]:
    split = max(0, timing_ms // 5)
    return [
        {"node": "intake", "timing_ms": split},
        {"node": "role_retrieval", "timing_ms": split},
        {"node": "planner", "timing_ms": split},
        {"node": "verifier", "timing_ms": split},
        {"node": "evidence", "timing_ms": max(0, timing_ms - (split * 4))},
    ]


def _infer_vector_status(response: PlanResponse) -> str:
    if any(item.retrieval_method in {"vector", "hybrid"} for item in response.evidence_panel):
        return "enabled"
    return "fallback_lexical"


def _role_retrieval_trace_lines(retriever: MarketEvidenceRetriever) -> list[str]:
    diag = retriever.get_last_role_diagnostics()
    if not diag:
        return []
    top = diag.get("top", [])
    if _retrieval_debug_enabled():
        payload = json.dumps(top[:5], ensure_ascii=True)
        return [f"retrieval_debug: role_top5={payload}"]
    if not top:
        return [f"retrieval_summary: role_candidates={diag.get('candidate_count', 0)}"]
    top1 = top[0]
    return [
        (
            "retrieval_summary: "
            f"role_candidates={diag.get('candidate_count', 0)} "
            f"top1={top1.get('role_id')} "
            f"hybrid={top1.get('hybrid_score', 0.0)}"
        )
    ]


def _evidence_retrieval_trace_lines(retriever: MarketEvidenceRetriever) -> list[str]:
    diag = retriever.get_last_evidence_diagnostics()
    if not diag:
        return []
    top = diag.get("top", [])
    if _retrieval_debug_enabled():
        payload = json.dumps(top[:5], ensure_ascii=True)
        return [f"retrieval_debug: evidence_top5={payload}"]
    if not top:
        return [f"retrieval_summary: evidence_candidates={diag.get('candidate_count', 0)}"]
    top1 = top[0]
    return [
        (
            "retrieval_summary: "
            f"evidence_candidates={diag.get('candidate_count', 0)} "
            f"top1={top1.get('evidence_id')} "
            f"score={top1.get('rank_score', 0.0)}"
        )
    ]


def _retrieval_debug_enabled() -> bool:
    return os.getenv("SANJAYA_RETRIEVAL_DEBUG", "").strip() == "1"


def _node_timing(node: str, started: float) -> dict[str, int | str]:
    return {"node": node, "timing_ms": max(0, int((time.perf_counter() - started) * 1000))}


def _emit_audit_log(
    *,
    request_id: str,
    selected_role_id: str,
    retries: int,
    retry_codes: list[str],
    final_error_codes: list[str],
    vector_status: str,
    total_time_ms: int,
    role_top1: str | None = None,
    evidence_top1: str | None = None,
) -> None:
    LOGGER.info(
        json.dumps(
            {
                "event": "plan_audit",
                "request_id": request_id,
                "selected_role_id": selected_role_id,
                "retries": retries,
                "retry_codes": retry_codes,
                "final_error_codes": final_error_codes,
                "vector_status": vector_status,
                "total_time_ms": total_time_ms,
                "role_top1": role_top1,
                "evidence_top1": evidence_top1,
            },
            ensure_ascii=True,
        )
    )


def _audit_top1_value(diag: dict, key: str) -> str | None:
    top = diag.get("top") if isinstance(diag, dict) else None
    if isinstance(top, list) and top:
        first = top[0]
        if isinstance(first, dict):
            value = first.get(key)
            if isinstance(value, str):
                return value
    return None


def _log_plan_analytics(*, request: PlanRequest, response: PlanResponse) -> None:
    try:
        log_plan_created(response, request)
        requested = (request.requested_role_text or "").strip()
        if requested:
            candidates = [
                {"role_id": item.role_id, "score": float(item.score)}
                for item in (response.candidate_roles or [])[:3]
            ]
            log_role_search(
                request_id=response.request_id or None,
                data_version=response.data_version or None,
                role_query=requested,
                candidate_roles=candidates,
                plan_id=response.plan_id or None,
            )
            unresolved = next(
                (
                    error
                    for error in response.validation_errors
                    if error.code == "ROLE_REQUEST_UNRESOLVED"
                ),
                None,
            )
            if unresolved is not None:
                top1_score = 0.0
                details = unresolved.details or {}
                try:
                    top1_score = float(details.get("top1_score", 0.0))
                except (TypeError, ValueError):
                    top1_score = 0.0
                event = log_unknown_role_request(
                    request_id=response.request_id or None,
                    data_version=response.data_version or None,
                    role_query=requested,
                    candidate_roles=candidates,
                    top1_score=top1_score,
                    plan_id=response.plan_id or None,
                )
                upsert_unknown_role_request(event)
    except Exception:
        LOGGER.exception("analytics logging failed")
