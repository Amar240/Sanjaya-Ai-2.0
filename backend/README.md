# Sanjaya AI Backend (Phase 1)

FastAPI backend with:
- strict Pydantic schemas
- market-grounded dataset loading
- startup integrity checks
- `/health`, `/roles`, `/plan`, `/chat`, and `/advisor/ask` endpoint
- prerequisite-aware semester scheduling
- credit-rule verification and plan warnings
- explicit `course_skills.json` mapping for skill-to-course matching
- optional strict curated override layer via `course_skills_curated.json`
- LangGraph workflow (`Intake -> Role Retrieval -> Planner -> Verifier`)
- RAG evidence attachment with Chroma (fallback lexical retrieval if unavailable)

## Run

Requirements:
- Python 3.10+
- Dependencies from `requirements.txt`

```powershell
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Quick checks

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/roles
```
puch
```powershell
curl -X POST http://127.0.0.1:8000/plan `
  -H "Content-Type: application/json" `
  -d "{""student_profile"":{""level"":""UG"",""mode"":""CORE"",""current_semester"":2,""start_term"":""Fall"",""include_optional_terms"":false,""completed_courses"":[""CISC-108""],""min_credits"":12,""target_credits"":15,""max_credits"":17,""interests"":[""ai"",""data""]},""preferred_role_id"":""ROLE_AI_ENGINEER""}"
```

```powershell
curl -X POST http://127.0.0.1:8000/chat `
  -H "Content-Type: application/json" `
  -d "{""message"":""I am an undergraduate interested in finance and analytics.""}"
```

```powershell
curl -X POST http://127.0.0.1:8000/advisor/ask `
  -H "Content-Type: application/json" `
  -d "{""question"":""Why this role for me?"",""tone"":""friendly"",""plan"":{...plan response json...}}"
```

## LLM (Groq)

Set environment variables before starting backend if you want LLM-powered conversational extraction:

```powershell
$env:GROQ_API_KEY="your_key_here"
$env:GROQ_MODEL="llama-3.3-70b-versatile"
```

Optional model split (recommended for reliability):

```powershell
$env:GROQ_MODEL_CHAT="llama-3.3-70b-versatile"
$env:GROQ_MODEL_ADVISOR="llama-3.1-8b-instant"
```

If these are not set, both chat and advisor use `GROQ_MODEL`.

## Optional LLM (OpenAI)

You can switch provider without code changes:

```powershell
$env:LLM_PROVIDER="openai"
$env:OPENAI_API_KEY="your_openai_key_here"
$env:OPENAI_MODEL="gpt-4.1"
```

Optional split by task:

```powershell
$env:OPENAI_MODEL_CHAT="gpt-4o-mini"
$env:OPENAI_MODEL_ADVISOR="gpt-4o-mini"
```

Provider selection behavior:
- `LLM_PROVIDER=openai` -> use OpenAI key/models
- `LLM_PROVIDER=groq` -> use Groq key/models
- `LLM_PROVIDER=gemini` -> use Gemini key/models (OpenAI-compatible endpoint)
- `LLM_PROVIDER=auto` (default) -> OpenAI if configured, else Groq

## Optional LLM (Gemini)

```powershell
$env:LLM_PROVIDER="gemini"
$env:GEMINI_API_KEY="your_gemini_api_key_here"
$env:GEMINI_MODEL="gemini-2.0-flash"
```

Optional split by task:

```powershell
$env:GEMINI_MODEL_CHAT="gemini-2.0-flash"
$env:GEMINI_MODEL_ADVISOR="gemini-2.0-flash"
$env:GEMINI_MODEL_STORYBOARD="gemini-2.0-flash"
```

## Tests

From this directory:

```powershell
cd backend
python -m pip install -r requirements.txt
pytest
```

The test suite covers plan validation, evidence integrity, job‑match behavior, and advisor workflows.

## Data files used

- `data/processed/courses.json`
- `data/processed/course_skills.json`
- `data/processed/course_skills_curated.json` (optional; strict override when role-skill rows exist)
- `data/processed/fusion_roles.json` (optional; enables Fusion mode readiness outputs)
- `data/processed/skills_market.json`
- `data/processed/roles_market.json`
- `data/processed/roles_market_calibrated.json` (optional; auto-used if present)
- `data/processed/role_skill_evidence.json`
- `data/processed/market_sources.json`

## Notes

- `/plan` uses hybrid mapping:
  - curated role-skill-course mappings first (strict per skill where provided)
  - heuristic `course_skills.json` fallback for uncovered role-skill pairs
- `/plan` Fusion mode:
  - uses `student_profile.mode="FUSION"`
  - returns `fusion_summary` (domain/tech coverage, unlock skills, readiness percentages)
  - role retrieval is constrained to configured fusion roles when available
- `/plan` now runs through a multi-agent workflow and enriches output with:
  - `evidence_panel`
  - `course_purpose_cards`
  - `agent_trace`
- `/plan` is term-aware:
  - if `offered_terms` exists, courses are scheduled only in those terms
  - if `offered_terms` is missing, course can still be scheduled with warning: `offering term not yet decided by department`
  - `include_optional_terms=false` (default) keeps UG plans on Fall/Spring only
  - set `include_optional_terms=true` to allow Summer/Winter scheduling
- role file selection:
  - uses `roles_market_calibrated.json` if available
  - otherwise falls back to `roles_market.json`
- `/plan` notes explicitly report when curated mappings are used.
- `/chat` uses LangGraph chat workflow with session memory:
  - if `GROQ_API_KEY` is set: uses Groq for profile extraction and response text
  - if not set: deterministic heuristic fallback still works
- `/advisor/ask` is plan-aware advisor Q&A:
  - answers with defended reasoning points + citations
  - intents include role-defense, course-defense, feasibility, and alternatives
  - optional Groq polishing when configured, but constrained to provided plan context
