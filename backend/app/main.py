from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from .admin_auth import admin_username, require_admin
from .analytics.events import log_advisor_question
from .analytics.insights import summary as insights_summary
from .analytics.role_requests import (
    get_role_request,
    list_role_requests,
    set_role_request_status,
)
from .agents.advisor_agent import answer_advisor_question
from .agents.chat_workflow import run_chat_workflow
from .agents.job_extractor import extract_job_skills
from .agents.job_matcher import build_job_match_response, match_extracted_to_skills
from .agents.storyboard import build_storyboard
from .agents.workflow import (
    get_retriever_for_store,
    reset_plan_cache,
    run_plan_workflow,
)
from .curation.roles_drafts import (
    create_draft,
    create_role_in_draft,
    create_role_stub_from_request,
    delete_role_in_draft,
    get_draft_role_readiness_status,
    is_central_reviewer,
    list_draft_roles,
    publish_draft_roles,
    update_role_in_draft,
)
from .data_loader import CatalogStore, DataValidationError, load_catalog_store
from .integration.myud import (
    build_myud_launch_response,
    build_myud_summary_response,
    build_plan_request_from_myud,
    validate_myud_signature,
)
from .ops.db import init_db as init_ops_db
from .ops.db import insert_audit_log
from .plan_store import get_plan_store, reset_plan_store
from .schemas.advisor import AdvisorRequest, AdvisorResponse
from .schemas.chat import ChatRequest, ChatResponse
from .schemas.health import ChromaHealth, HealthCounts, HealthResponse
from .schemas.integration import (
    MyUDLaunchRequest,
    MyUDLaunchResponse,
    MyUDPlanSummaryResponse,
)
from .schemas.job_match import JobMatchRequest, JobMatchResponse
from .schemas.plan import PlanRequest, PlanResponse
from .schemas.storyboard import StoryboardRequest, StoryboardResponse

catalog_store: CatalogStore | None = None
catalog_retriever = None
startup_error: str | None = None
LOGGER = logging.getLogger(__name__)


class RoleRequestMapBody(BaseModel):
    mapped_role_id: str
    note: str | None = None


class RoleRequestCreateRoleBody(BaseModel):
    draft_id: str | None = None


class DraftRoleBody(BaseModel):
    role_id: str | None = None
    title: str | None = None
    market: str | None = None
    market_grounding: str | None = None
    summary: str | None = None
    source_occupation_codes: list[dict] = Field(default_factory=list)
    required_skills: list[dict] = Field(default_factory=list)
    evidence_sources: list[str] = Field(default_factory=list)
    department_owner: str | None = None
    country_scope: str | None = None
    demo_tier: str | None = None
    reality_complete: bool | None = None
    project_coverage_complete: bool | None = None


class CatalogCourseResponse(BaseModel):
    """Course details for catalog/course Q&A (description, source link)."""

    course_id: str
    title: str
    description: str
    source_url: str


@asynccontextmanager
async def lifespan(_: FastAPI):
    global catalog_store
    global catalog_retriever
    global startup_error

    try:
        init_ops_db()
        catalog_store = load_catalog_store()
        catalog_retriever = get_retriever_for_store(catalog_store, create_if_missing=True)
        startup_error = None
    except (DataValidationError, FileNotFoundError, OSError) as exc:
        catalog_store = None
        catalog_retriever = None
        startup_error = str(exc)
    yield


app = FastAPI(
    title="Sanjaya AI Backend",
    version="0.1.0",
    description="Grounded advising backend for role-to-skill-to-course planning.",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    status = "ok" if catalog_store else "degraded"
    counts = (
        HealthCounts(
            courses=len(catalog_store.courses),
            roles=len(catalog_store.roles),
            skills=len(catalog_store.skills),
            sources=len(catalog_store.sources),
            role_skill_evidence_links=len(catalog_store.evidence_links),
        )
        if catalog_store
        else HealthCounts()
    )
    startup_entries = _startup_validation_entries(startup_error)
    startup_samples = startup_entries[:5]
    chroma_stats = catalog_retriever.get_store_stats() if catalog_retriever else {}
    chroma = ChromaHealth(
        enabled=bool(chroma_stats.get("enabled", False)),
        persist_dir=(
            str(chroma_stats.get("persist_dir")) if chroma_stats.get("persist_dir") else None
        ),
        roles_count=_to_optional_int(chroma_stats.get("roles_count")),
        evidence_count=_to_optional_int(chroma_stats.get("evidence_count")),
    )
    return HealthResponse(
        status=status,
        data_version=catalog_store.data_version if catalog_store else None,
        counts=counts,
        chroma=chroma,
        startup_validation_errors=len(startup_entries),
        startup_validation_samples=startup_samples,
    )


@app.get("/roles")
def roles() -> list[dict]:
    if not catalog_store:
        raise HTTPException(status_code=503, detail=startup_error or "Data store unavailable")
    fusion_role_ids = {profile.role_id for profile in catalog_store.fusion_role_profiles}
    return [
        {
            "role_id": role.role_id,
            "title": role.title,
            "market_grounding": role.market_grounding,
            "fusion_available": role.role_id in fusion_role_ids,
            "department_owner": role.department_owner,
            "demo_tier": role.demo_tier,
        }
        for role in catalog_store.roles
    ]


@app.get("/catalog/course/{course_id}", response_model=CatalogCourseResponse)
def get_catalog_course(course_id: str) -> CatalogCourseResponse:
    """Return course details (title, description, source_url) for Course Q&A dialog."""
    if not catalog_store:
        raise HTTPException(status_code=503, detail=startup_error or "Data store unavailable")
    course = catalog_store.courses_by_id.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return CatalogCourseResponse(
        course_id=course.course_id,
        title=course.title,
        description=course.description or "",
        source_url=str(course.source_url),
    )


@app.post("/plan", response_model=PlanResponse)
def plan(request: PlanRequest) -> PlanResponse:
    if not catalog_store:
        raise HTTPException(status_code=503, detail=startup_error or "Data store unavailable")
    return run_plan_workflow(request, catalog_store)


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    if not catalog_store:
        raise HTTPException(status_code=503, detail=startup_error or "Data store unavailable")
    return run_chat_workflow(request, catalog_store)


@app.post("/advisor/ask", response_model=AdvisorResponse)
def advisor_ask(request: AdvisorRequest) -> AdvisorResponse:
    if not catalog_store:
        raise HTTPException(status_code=503, detail=startup_error or "Data store unavailable")
    if request.plan_id:
        resolved_plan = get_plan_store().get(request.plan_id)
        if resolved_plan is None:
            raise HTTPException(status_code=404, detail="Unknown plan_id")
        response = answer_advisor_question(
            request,
            catalog_store,
            resolved_plan=resolved_plan,
            resolved_plan_id=request.plan_id,
        )
        _log_advisor_event(request=request, response=response)
        return response

    if request.plan is None:
        raise HTTPException(status_code=422, detail="Either plan_id or plan must be provided")
    response = answer_advisor_question(
        request,
        catalog_store,
        resolved_plan=request.plan,
        resolved_plan_id=request.plan.plan_id,
    )
    _log_advisor_event(request=request, response=response)
    return response


@app.post("/plan/storyboard", response_model=StoryboardResponse)
def plan_storyboard(request: StoryboardRequest) -> StoryboardResponse:
    if not catalog_store:
        raise HTTPException(status_code=503, detail=startup_error or "Data store unavailable")
    resolved_plan = get_plan_store().get(request.plan_id)
    if resolved_plan is None:
        raise HTTPException(status_code=404, detail="Unknown plan_id")
    return build_storyboard(
        request=request,
        plan=resolved_plan,
        store=catalog_store,
    )


@app.post("/job/match", response_model=JobMatchResponse)
def job_match(request: JobMatchRequest) -> JobMatchResponse:
    if not catalog_store:
        raise HTTPException(status_code=503, detail=startup_error or "Data store unavailable")

    resolved_plan = None
    if request.plan_id:
        resolved_plan = get_plan_store().get(request.plan_id)
        if resolved_plan is None:
            raise HTTPException(status_code=404, detail="Unknown plan_id")

    extracted, llm_status, llm_error = extract_job_skills(
        request.text,
        store=catalog_store,
    )
    mapped, unmapped, mapping_summary = match_extracted_to_skills(
        extracted,
        catalog_store,
    )
    return build_job_match_response(
        extracted=extracted,
        mapped_skills=mapped,
        unmapped_terms=unmapped,
        mapping_summary=mapping_summary,
        store=catalog_store,
        plan=resolved_plan,
        llm_status=llm_status,
        llm_error=llm_error,
    )


@app.get("/admin/insights/summary")
def admin_insights_summary(
    window: str = "30d",
    _: str = Depends(require_admin),
) -> dict:
    return insights_summary(window=window)


@app.get("/admin/role-requests")
def admin_role_requests(
    status: str | None = "open",
    min_count: int | None = None,
    show_all: bool = False,
    _: str = Depends(require_admin),
) -> dict:
    items = list_role_requests(status=status, min_count=min_count, show_all=show_all)
    return {"items": items}


@app.get("/admin/role-requests/{role_request_id}")
def admin_role_request(
    role_request_id: str,
    _: str = Depends(require_admin),
) -> dict:
    item = get_role_request(role_request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="role_request_id not found")
    return item


@app.post("/admin/role-requests/{role_request_id}/ignore")
def admin_role_request_ignore(
    role_request_id: str,
    _: str = Depends(require_admin),
    username: str = Depends(admin_username),
) -> dict:
    updated = set_role_request_status(role_request_id, status="ignored")
    if updated is None:
        raise HTTPException(status_code=404, detail="role_request_id not found")
    insert_audit_log(
        user=username,
        action="role_request_ignore",
        entity="role_requests",
        meta={"role_request_id": role_request_id},
    )
    return updated


@app.post("/admin/role-requests/{role_request_id}/map")
def admin_role_request_map(
    role_request_id: str,
    body: RoleRequestMapBody,
    _: str = Depends(require_admin),
    username: str = Depends(admin_username),
) -> dict:
    updated = set_role_request_status(
        role_request_id,
        status="mapped",
        mapped_role_id=body.mapped_role_id,
        note=body.note,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="role_request_id not found")
    insert_audit_log(
        user=username,
        action="role_request_map",
        entity="role_requests",
        meta={"role_request_id": role_request_id, "mapped_role_id": body.mapped_role_id},
    )
    return updated


@app.post("/admin/role-requests/{role_request_id}/create-role")
def admin_role_request_create_role(
    role_request_id: str,
    body: RoleRequestCreateRoleBody,
    _: str = Depends(require_admin),
    username: str = Depends(admin_username),
) -> dict:
    global catalog_store
    global catalog_retriever
    if catalog_store is None:
        raise HTTPException(status_code=503, detail="Data store unavailable")
    item = get_role_request(role_request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="role_request_id not found")
    query = str(item.get("examples", [""])[0] or item.get("role_query_norm") or "").strip()
    if not query:
        query = str(item.get("role_query_norm") or "")
    try:
        draft_id, new_role_id = create_role_stub_from_request(
            role_query=query,
            username=username,
            store=catalog_store,
            draft_id=body.draft_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    set_role_request_status(
        role_request_id,
        status="created_role",
        new_role_id=new_role_id,
        note=f"Draft {draft_id}",
    )
    insert_audit_log(
        user=username,
        action="role_request_create_role",
        entity="role_requests",
        draft_id=draft_id,
        meta={"role_request_id": role_request_id, "new_role_id": new_role_id},
    )
    return {"draft_id": draft_id, "new_role_id": new_role_id}


@app.post("/admin/drafts")
def admin_create_draft(
    _: str = Depends(require_admin),
    username: str = Depends(admin_username),
) -> dict:
    draft_id = create_draft(created_by=username)
    return {"draft_id": draft_id}


@app.get("/admin/drafts/{draft_id}/roles")
def admin_list_draft_roles(
    draft_id: str,
    q: str | None = None,
    department_owner: str | None = None,
    page: int = 1,
    _: str = Depends(require_admin),
) -> dict:
    try:
        return list_draft_roles(draft_id, query=q, department_owner=department_owner, page=page)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/admin/drafts/{draft_id}/roles/readiness")
def admin_draft_role_readiness(
    draft_id: str,
    department_owner: str | None = None,
    _: str = Depends(require_admin),
) -> dict:
    try:
        rows = get_draft_role_readiness_status(draft_id, department_owner=department_owner)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"items": rows}


@app.post("/admin/drafts/{draft_id}/roles")
def admin_create_draft_role(
    draft_id: str,
    body: DraftRoleBody,
    _: str = Depends(require_admin),
    username: str = Depends(admin_username),
) -> dict:
    if catalog_store is None:
        raise HTTPException(status_code=503, detail="Data store unavailable")
    try:
        role = create_role_in_draft(
            draft_id=draft_id,
            payload=body.model_dump(exclude_none=True),
            username=username,
            store=catalog_store,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return role


@app.put("/admin/drafts/{draft_id}/roles/{role_id}")
def admin_update_draft_role(
    draft_id: str,
    role_id: str,
    body: DraftRoleBody,
    _: str = Depends(require_admin),
    username: str = Depends(admin_username),
) -> dict:
    if catalog_store is None:
        raise HTTPException(status_code=503, detail="Data store unavailable")
    try:
        role = update_role_in_draft(
            draft_id=draft_id,
            role_id=role_id,
            payload=body.model_dump(exclude_none=True),
            username=username,
            store=catalog_store,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"role_id not found: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return role


@app.delete("/admin/drafts/{draft_id}/roles/{role_id}")
def admin_delete_draft_role(
    draft_id: str,
    role_id: str,
    _: str = Depends(require_admin),
    username: str = Depends(admin_username),
) -> dict:
    try:
        delete_role_in_draft(draft_id, role_id, username=username)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"role_id not found: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"deleted": True, "role_id": role_id}


@app.post("/admin/drafts/{draft_id}/publish")
def admin_publish_draft(
    draft_id: str,
    _: str = Depends(require_admin),
    username: str = Depends(admin_username),
) -> dict:
    global catalog_store
    global catalog_retriever
    if not is_central_reviewer(username):
        raise HTTPException(
            status_code=403,
            detail="Only central reviewer can publish drafts.",
        )
    try:
        result = publish_draft_roles(draft_id, reviewer=username)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # refresh runtime state atomically for subsequent requests
    catalog_store = load_catalog_store()
    catalog_retriever = get_retriever_for_store(catalog_store, create_if_missing=True)
    reset_plan_cache()
    reset_plan_store()
    result["data_version"] = catalog_store.data_version
    return result


@app.post("/integration/myud/launch", response_model=MyUDLaunchResponse)
def integration_myud_launch(
    request: MyUDLaunchRequest,
    x_myud_signature: str | None = None,
) -> MyUDLaunchResponse:
    if not catalog_store:
        raise HTTPException(status_code=503, detail=startup_error or "Data store unavailable")
    if not validate_myud_signature(payload=request, signature=x_myud_signature):
        raise HTTPException(status_code=401, detail="Invalid My UD signature")
    plan_request = build_plan_request_from_myud(request)
    plan = run_plan_workflow(plan_request, catalog_store)
    return build_myud_launch_response(plan)


@app.get("/integration/myud/plan/{plan_id}/summary", response_model=MyUDPlanSummaryResponse)
def integration_myud_plan_summary(plan_id: str) -> MyUDPlanSummaryResponse:
    plan = get_plan_store().get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Unknown plan_id")
    return build_myud_summary_response(plan)


def _startup_validation_entries(error: str | None) -> list[str]:
    if not error:
        return []
    if "\n- " not in error:
        return [error]
    lines = [line.strip() for line in error.splitlines() if line.strip().startswith("- ")]
    return [line[2:].strip() for line in lines]


def _to_optional_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _log_advisor_event(*, request: AdvisorRequest, response: AdvisorResponse) -> None:
    try:
        data_version = request.plan.data_version if request.plan else (
            catalog_store.data_version if catalog_store else None
        )
        log_advisor_question(
            plan_id=response.plan_id or None,
            data_version=data_version,
            request_id=response.request_id or None,
            intent=response.intent or None,
            question=request.question,
        )
    except Exception:
        LOGGER.exception("advisor analytics logging failed")
