# Sanjaya AI Handoff (Single Context for New Chat)

Use this file as the context handoff to continue work in a new conversation.

## 1) Project Goal and Scope

Build Sanjaya AI as a grounded advising platform:
- role -> skills -> courses -> semester plan
- explainable outputs with evidence
- university truth layer from UD catalog (`https://catalog.udel.edu/`)

Current backend is rule-based and runnable via FastAPI.

## 2) What Has Been Completed

### A. UD Course Data Pipeline

Implemented:
- `scripts/scrape_udel_catalog.py`
- `scripts/normalize_courses.py`
- `scripts/validate_courses.py`
- `scripts/generate_course_skills.py`
- `scripts/validate_course_skills.py`
- `scripts/calibrate_role_importance.py`
- `scripts/report_missing_prereqs.py`
- `scripts/fetch_missing_courses.py`
- `scripts/requirements-scraper.txt`
- `docs/udel_data_pipeline.md`

Generated datasets:
- `data/raw/courses_raw.json` (UG scrape)
- `data/raw/courses_raw_grad.json` (GR scrape)
- `data/raw/courses_raw_combined.json` (merged raw)
- `data/processed/courses.json` (normalized)
- `data/processed/course_skills.json` (explicit course->skill mappings)
- `data/processed/course_skills_curated.json` (strict curated role-skill-course overrides)

Quality fixes already done:
- Removed catalog UI noise from processed text (`Print-Friendly Page`, `Facebook this Page`, `Tweet this Page`, `Back to Top`, `HELP YYYY-YYYY Catalog`).
- Revalidated dataset after cleanup.
- Added richer requirement parsing in normalization:
  - `prerequisites` / `prerequisites_text`
  - `corequisites` / `corequisites_text`
  - `antirequisites` / `antirequisites_text`
  - `offered_terms`

Current normalized coverage:
- total courses: `768`
- departments: `ACCT`, `BINF`, `BISC`, `BUAD`, `CHEM`, `CISC`, `ECON`, `FINC`, `MATH`, `MISY`, `STAT`

Exports:
- `data/processed/courses_coverage.csv`
- `data/processed/courses_department_summary.csv`

### B. Skills/Roles Layer

Baseline curated files:
- `data/processed/skills.json`
- `data/processed/roles.json` (includes `ROLE_AI_ENGINEER`)

Market-grounded layer (kept separate; baseline not deleted):
- `data/processed/market_sources.json`
- `data/processed/skills_market.json`
- `data/processed/roles_market.json`
- `data/processed/role_skill_evidence.json`
- `data/processed/roles_market_calibrated.json` (generated from evidence)
- `data/processed/role_importance_calibration_report.json`
- `data/processed/fusion_roles.json` (fusion mode profiles)
- `docs/market_grounding.md`

Market layer stats:
- roles: `31`
- skills: `51`
- role-skill evidence links: `136`
- sources: `36`

### C. Backend (FastAPI)

Scaffold and working endpoints:
- `GET /health`
- `GET /roles`
- `POST /plan`
- `POST /chat`
- `POST /advisor/ask`

Implemented backend files:
- `backend/requirements.txt`
- `backend/README.md`
- `backend/app/main.py`
- `backend/app/data_loader.py`
- `backend/app/schemas/catalog.py`
- `backend/app/schemas/chat.py`
- `backend/app/schemas/advisor.py`
- `backend/app/schemas/plan.py`
- `backend/app/agents/chat_workflow.py`
- `backend/app/agents/advisor_agent.py`
- `backend/app/agents/planner.py`
- `backend/app/agents/workflow.py`
- `backend/app/validators/plan_verifier.py`
- `backend/app/rag/evidence_retriever.py`

Recent backend quality updates:
- strict evidence retrieval for selected role only (no adjacent-role fallback)
- strict curated role-skill-course priority in planner when curated rows exist
- verifier now reports level mapping constraints:
  - `Skill-level mapping constraint (UG-only): ...`
  - `Skill-level mapping constraint (GR-only): ...`
  - plus planning impact notes by student level
- conversational intake endpoint added:
  - `POST /chat` with session memory
  - LangGraph chat workflow + deterministic fallback
  - optional Groq LLM extraction/response when `GROQ_API_KEY` is set
- advisor-defense endpoint added:
  - `POST /advisor/ask`
  - plan-aware defended answers with reasoning points and citations
  - intents: role-defense, course-defense, feasibility, alternatives

### D. Frontend (Next.js)

Implemented frontend files:
- `frontend/package.json`
- `frontend/app/layout.tsx`
- `frontend/app/page.tsx`
- `frontend/app/globals.css`
- `frontend/app/api/roles/route.ts`
- `frontend/app/api/plan/route.ts`
- `frontend/app/api/chat/route.ts`
- `frontend/app/api/advisor/route.ts`
- `frontend/components/ChatAssistantPanel.tsx`
- `frontend/components/AdvisorQAPanel.tsx`
- `frontend/components/IntakeForm.tsx`
- `frontend/components/PlanDashboard.tsx`
- `frontend/lib/types.ts`
- `frontend/lib/api.ts`
- `frontend/README.md`

Frontend behavior:
- conversational intake panel (session chat -> extracted plan draft)
- advisor Q&A panel (defended answers + citations) on top of generated plan
- chat-style structured intake
- role loading from backend (`/api/roles` proxy)
- plan generation (`/api/plan` proxy), chat (`/api/chat`), advisor (`/api/advisor`)
- roadmap timeline, skill coverage, notes/errors
- course purpose cards with evidence
- evidence panel and agent trace

### E. `/plan` Behavior (Current)

Flow:
1. Intake agent normalizes profile (`start_term`, credits, mode, interests)
2. Role Retrieval agent selects candidate roles (`preferred_role_id` or interest-based retrieval)
   - in `FUSION` mode, candidate retrieval is constrained to `fusion_roles.json` role IDs when available
3. Planner agent builds roadmap:
   - filter courses by student level
   - match role skills to courses using hybrid priority:
     - strict curated mapping from `course_skills_curated.json` (when role-skill rows exist)
     - fallback mapping from `course_skills.json` for uncovered role-skill pairs
   - pick target courses + prerequisite closure
   - schedule term-aware semesters under credit policy
   - uses `student_profile.start_term` (default `Fall`)
   - `student_profile.include_optional_terms` controls Summer/Winter usage for UG (`false` by default)
   - respects `offered_terms` when available
   - if a course has no `offered_terms`, planner keeps it and adds warning: `offering term not yet decided by department`
4. Verifier agent checks structure and may retry once with optional terms enabled
5. Evidence agent attaches:
   - role-skill market evidence snippets
   - per-course purpose cards (`why this course`, covered skills, evidence links)

Output includes:
- selected role
- skill coverage
- semester roadmap
- validation errors
- notes/warnings
- evidence panel
- course purpose cards
- fusion summary (`fusion_summary`) when mode is `FUSION`
- agent trace

Recent validation sample (UG profile):
- `ROLE_OPERATIONS_RESEARCH_ANALYST`: coverage `8/8`
- `ROLE_CLOUD_ENGINEER`: curated mappings used for `8/8` required skills

Recent prerequisite-gap recovery:
- global catalog-wide external prerequisite references reduced from `80+` to `18`
- plan-specific external prerequisite references for target roles:
  - `ROLE_ML_ENGINEER`: `0`
  - `ROLE_AI_ENGINEER`: `0`
  - `ROLE_QUANT_RISK_ANALYST`: `0`

## 3) Run Instructions

```powershell
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Check:
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/roles`
- `http://127.0.0.1:8000/docs`

Frontend:

```powershell
cd frontend
copy .env.local.example .env.local
npm install
npm run dev
```

Open:
- `http://127.0.0.1:3000`

## 4) Known Limitations (Important)

1. `course_skills_curated.json` is now broad (all role-skill pairs), but many rows are auto-curated seeds and still need human review for perfect academic realism.
2. Two unavoidable level-specific skill gaps exist due source mapping availability:
   - `ROLE_BIOINFORMATICS_SCIENTIST` + `SK_BIO_STATS` currently GR-only
   - `ROLE_WEB_APPLICATION_ENGINEER` + `SK_FRONTEND_DEV` currently UG-only
3. `offered_terms` is enforced when present; unknown offerings are retained with explicit warnings.
4. `coreq`/`antireq` logic is not implemented.
5. LangGraph is optional at runtime; if missing, backend uses deterministic fallback workflow.
6. Chroma retrieval currently uses local hash embeddings (offline, deterministic) and can be upgraded to richer embeddings later.
7. Fusion mode is implemented with `fusion_roles.json` profiles and rule-based readiness; still needs deeper curriculum/domain curation and additional fusion profiles.
8. Frontend is implemented, but no auth/persistence/deployment hardening yet.
9. Groq is optional at runtime; if key/model are not configured or network is blocked, `/chat` falls back to deterministic extraction/response.

## 5) Agreed Next Steps

1. Human-review and tighten auto-curated mapping rows by role priority.
2. Expand and human-review `fusion_roles.json` profiles (domains, weights, unlock reasons, and evidence linkage).
3. Add richer RAG retrieval (external embedding provider + citation ranking) for stronger evidence quality.
4. Add frontend improvements:
   - fusion-specific controls/output
   - role comparison mode
   - export/share plan JSON or PDF

## 6) Paste-Ready Prompt for New Chat

```text
Continue development of Sanjaya AI from existing repo state.

Current status:
- UD courses scraped and normalized to data/processed/courses.json (768 courses).
- Market-grounded role/skill/evidence files exist:
  data/processed/skills_market.json
  data/processed/roles_market.json
  data/processed/role_skill_evidence.json
  data/processed/market_sources.json
  data/processed/roles_market_calibrated.json
- Explicit course->skill mapping exists:
  data/processed/course_skills.json
  data/processed/course_skills_curated.json
- FastAPI backend implemented with /health, /roles, /plan.
- /plan now runs agent workflow (LangGraph when installed; fallback otherwise) and outputs evidence_panel/course_purpose_cards/agent_trace.
- /chat endpoint implemented with session memory and optional Groq LLM extraction (`GROQ_API_KEY`).
- /plan uses strict curated mapping priority + selected-role-only evidence retrieval.
- Verifier reports skill level constraints (UG-only/GR-only) when present.
- Next.js frontend implemented with intake + roadmap + evidence surfaces.
- Key backend files:
  backend/app/main.py
  backend/app/data_loader.py
  backend/app/agents/planner.py
  backend/app/agents/workflow.py
  backend/app/rag/evidence_retriever.py
  backend/app/validators/plan_verifier.py
  backend/app/schemas/catalog.py
  backend/app/schemas/plan.py

Next required tasks:
1) Human-curate high-impact role-skill-course rows to replace auto-curated seeds.
2) Expand and refine Fusion mode profiles and add richer fusion evidence linkage.
3) Add role comparison + export features in frontend.

Do not delete baseline files. Keep market-grounded files as primary for roles/skills.
```
