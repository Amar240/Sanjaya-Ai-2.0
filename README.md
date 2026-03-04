# Sanjaya AI 2.0

Verified roadmaps from courses -> skills -> real jobs (USA).

Sanjaya AI combines a deterministic planner, deterministic verifier, and evidence-grounded retrieval to build prerequisite-safe, credit-aware semester plans. Language-model features are optional and constrained to explanation and narrative only.

## Problem

Students often choose courses without a reliable view of how those courses map to job skills and role readiness. The result is delayed gap discovery during internships and recruiting. Advisors need a transparent, auditable system that scales role mapping and recommendation quality.

## What this system delivers

- Verified semester roadmap with prerequisite and credit validation.
- Skill coverage map from course selections to target-role requirements.
- Evidence-linked explanation for recommendations and alternatives.
- Advisor governance workflow for draft, readiness checks, and publish.

## Architecture

- Frontend: Next.js (App Router), TypeScript, React.
- Backend: FastAPI + Pydantic schemas.
- Core pipeline: intake -> role retrieval -> planner -> verifier -> enrichment.
- Retrieval: evidence attachment with lexical/hybrid retrieval and optional vector index.
- Data: curated processed JSON under `data/processed/`.

Design boundary:

- Deterministic logic decides correctness and constraints.
- Retrieval attaches evidence for traceability.
- LLMs are optional for phrasing and cannot override verified decisions.

## Repository structure

```txt
SanjayaAi/
  backend/
  frontend/
  data/
    processed/
    raw/
  docs/
  scripts/
  docker-compose.yml
  run_local.ps1
  run_local.sh
```

## Quickstart (local)

### 1) Backend

```powershell
cd backend
python -m pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

Open:

- Health: <http://127.0.0.1:8000/health>
- API docs: <http://127.0.0.1:8000/docs>

### 2) Frontend

Open a new terminal:

```powershell
cd frontend
copy .env.local.example .env.local
npm install
npm run dev
```

Open:

- UI: <http://127.0.0.1:3000>

If needed, set explicit backend URL in `frontend/.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

### 3) Optional Docker

```bash
docker compose up --build
```

## Environment variables

Backend (`backend/.env`):

```env
LLM_PROVIDER=auto
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash

SANJAYA_ENABLE_LLM_STORYBOARD=0
SANJAYA_ENABLE_LLM_ADVISOR=0
SANJAYA_ENABLE_LLM_JOB_EXTRACTOR=0
```

Frontend (`frontend/.env.local`):

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

Recommended for judging: keep `SANJAYA_ENABLE_LLM_*` set to `0` to demonstrate deterministic behavior without external providers.

## API overview

Core:

- `GET /health`
- `GET /roles`
- `GET /catalog/course/{course_id}`
- `POST /plan`
- `POST /chat`
- `POST /advisor/ask`
- `POST /plan/storyboard`
- `POST /job/match`

Admin:

- `GET /admin/insights/summary`
- `GET /admin/role-requests`
- `GET /admin/role-requests/{role_request_id}`
- `POST /admin/role-requests/{role_request_id}/ignore`
- `POST /admin/role-requests/{role_request_id}/map`
- `POST /admin/role-requests/{role_request_id}/create-role`
- `POST /admin/drafts`
- `GET /admin/drafts/{draft_id}/roles`
- `GET /admin/drafts/{draft_id}/roles/readiness`
- `POST /admin/drafts/{draft_id}/roles`
- `PUT /admin/drafts/{draft_id}/roles/{role_id}`
- `DELETE /admin/drafts/{draft_id}/roles/{role_id}`
- `POST /admin/drafts/{draft_id}/publish`

Integration:

- `POST /integration/myud/launch`
- `GET /integration/myud/plan/{plan_id}/summary`

## 90-second judge demo

1. Check health:
   - `GET http://127.0.0.1:8000/health`
2. Generate a plan via `POST /plan` using UG + AI/Data interests.
3. Confirm response includes:
   - `plan_id`, `data_version`, `semesters`, `skill_coverage`, `validation_errors`.
4. Trigger an invalid scenario (credit/prereq mismatch) and confirm structured validation errors.
5. Call `POST /advisor/ask` and confirm plan-grounded reasoning with citations where available.

## Data and truth sources

Primary datasets are under `data/processed/`:

- `courses.json`
- `roles_market.json`
- `roles_market_calibrated.json`
- `skills_market.json`
- `course_skills.json`
- `course_skills_curated.json`
- `role_skill_evidence.json`
- `market_sources.json`
- `role_reality_usa.json`
- `project_templates.json`
- `fusion_roles.json`, `fusion_packs_usa.json`

Raw scraped catalogs and pipeline assets are under `data/raw/` and `scripts/`.

## Excluded large/local artifacts

The following are intentionally excluded from version control:

- `data/chroma/` (local vector index)
- `data/ops/*.db` (local sqlite stores)
- `data/analytics/*.jsonl` (runtime analytics logs)
- local env files (`backend/.env`, `frontend/.env.local`)

To regenerate:

- Build normalized datasets with scripts in `scripts/` (see `docs/udel_data_pipeline.md`).
- Start backend once to initialize local ops DB and retrieval caches.
- Run planner flows to repopulate runtime analytics logs.

## Tests

```powershell
cd backend
pytest -q
```


## Additional docs

- `docs/demo-script.md`
- `docs/v2_manual_qa.md`
- `docs/ops-runbook.md`
- `docs/submission.md`
