## Sanjaya AI – Explainable Career Roadmaps from Course Plans

### 1. Project overview

**Problem and audience**

Students often choose courses without a clear view of how those choices lead to a **real job title**. Advisors and departments juggle degree rules, market data, and student interests in spreadsheets and static PDFs. There is no single place where a student can see:

- “If I take these courses, how close am I to being an **AI Engineer**?”
- “What skills am I missing, and what projects would close those gaps?”

**Solution**

Sanjaya AI turns a student’s course context into an **explainable roadmap** to a market‑grounded role:

- Matches the student to a role (e.g. **AI Engineer**) using interests plus a curated catalog.
- Builds a **semester‑by‑semester plan** respecting prerequisites and credit limits.
- Validates against **degree total credits** (for example, 128 credits for UG, 33 for GR) and raises structured warnings/errors.
- Surfaces a 5‑step “brain picture” of the path:
  1. Target Reality (tasks + salary band).
  2. Skill Gaps and project recommendations.
  3. Fusion Opportunities (optional “X + tech” paths).
  4. Career Storyboard in plain English.
  5. Job‑posting match against a real ad.
- Provides an **Advisor Q&A** and an **admin dashboard** for insights and role governance.

**Architecture and technologies**

- **Frontend**
  - Next.js 14 (App Router), React, TypeScript, CSS.
  - Main route `/` hosts the landing page, intake form, and plan dashboard.
  - Admin routes under `/admin` for insights, role requests, and draft roles.

- **Backend**
  - Python **FastAPI** service with Pydantic models and a planning/validation pipeline.
  - Deterministic planner:
    - selects roles using student interests and curated catalogs,
    - schedules semesters subject to min/target/max credits and `degree_total_credits`,
    - generates validation errors/warnings when rules are violated.

- **AI and data**
  - Optional **OpenAI GPT‑4.1** for narrative (storyboard) and advisor answers.
  - Curated **role + skill catalog** (e.g., AI Engineer, Data Scientist, Cybersecurity Analyst) with skill IDs.
  - US‑focused “role reality” data for tasks and salary bands.
  - Job‑posting text as input to a job‑match module that maps free‑text requirements to catalog skills.

**Key features**

- **Student‑facing roadmap** for a target role such as **AI Engineer**:
  - 5‑step “Your path” view: Target Reality → Skill Gaps → Fusion Opportunities → Career Storyboard → Reality Check (Job Posting).
  - Degree‑credit validation: the planner checks total credits against user‑provided degree totals and emits `TOTAL_CREDITS_OVER_DEGREE` / `TOTAL_CREDITS_UNDER_DEGREE` when plans are outside expected bounds.

- **Explainability and evidence**
  - Course purpose cards (“why this course”), skill coverage chips (“covered” vs “gap”), and an evidence panel linking back to sources.
  - Advisor Q&A with intent labels (e.g., `why_role`, `alternatives_compare`) and citations referencing skills, courses, or policy notes.

- **Admin/advisor surface**
  - Advisor Insights dashboard (`/admin/insights`): top roles, error codes, advisor intents, unknown role requests, and severity breakdown.
  - Role Requests inbox (`/admin/role-requests`): aggregates unknown role queries and lets staff map them to existing roles or create new drafts.
  - Draft Roles editor with **readiness gates**:
    - Gate 1: skills and evidence coverage.
    - Gate 2: role reality completeness.
    - Gate 3: project coverage for missing skills.

---

### 2. Methodology documentation

#### Data sources and prior work

- **Course catalog** – structured list of university courses with IDs, titles, credit values, and prerequisite relationships.
- **Role and skill catalogs** – curated JSON for roles (e.g., AI Engineer, Data Scientist, Cybersecurity Analyst) with associated skills and evidence sources.
- **Role reality data** – US‑centric occupation‑style data providing:
  - typical tasks,
  - salary bands (p25, median, p75),
  - references to external sources.
- **Job postings** – unstructured text from public job ads (used as input for job match, not stored with PII).

Sanjaya AI is conceptually related to tools like degree planners and O*NET occupation profiles. Its difference is that it connects **course plans → skills → roles → job postings** with explicit evidence and credit validation, and provides a **governed admin workflow** for role curation.

#### Planning and validation logic

1. **Student intake → PlanRequest**

   The frontend collects:

   - `level` (UG/GR), `mode` (Core vs Fusion), `degree_total_credits`, `current_semester`, credit bounds.
   - Interests and goal (select role, type role, or explore).
   - Optional `preferred_role_id` (e.g., AI Engineer).

   This is sent as a `PlanRequest` to the backend.

2. **Role selection**

   The backend ranks candidate roles using:

   - match between interests and role tags,
   - optional free‑text role query,
   - and a **preferred_role_id override** (if set, it is prioritized).

   The top role becomes `selected_role_id` and `selected_role_title` (e.g., “AI Engineer”).

3. **Scheduling and degree‑total validation**

   The planning engine:

   - Schedules courses semester‑by‑semester while enforcing:
     - `min_credits`, `target_credits`, `max_credits` per semester.
     - prerequisite order and offering terms.
   - Accumulates a **total planned credits** value and compares it against `degree_total_credits`.
   - Emits structured `PlanError`s with codes such as:
     - `TOTAL_CREDITS_OVER_DEGREE` (plan total exceeds degree total — error).
     - `TOTAL_CREDITS_UNDER_DEGREE` (plan total is significantly below degree total — warning).
     - plus existing codes like `CREDIT_OVER_MAX`, `PREREQ_ORDER`, `LEVEL_MISMATCH`, etc.

   These codes drive the **Validation** tab in the UI, with tailored explanations (“Why it matters / What you can do”).

4. **Skill coverage and evidence**

   - Each role’s required skills are matched against courses to produce `SkillCoverage` objects (covered vs gap, matched courses).
   - `EvidencePanelItem`s capture snippets and URLs from role and skill sources; these power:
     - the **Evidence Panel** in the Skills tab,
     - and citations in the storyboard and advisor answers.

5. **Job match module**

   When a user pastes a job posting, the system:

   - Runs a text extractor to produce a `JobExtractResult`:
     - `required_skills`, `preferred_skills`, and `tools` as strings.
   - Matches those terms to catalog skills using name overlap, synonyms, and substrings.
   - Produces a `JobMatchResponse` with:
     - mapped vs unmapped terms,
     - `covered_skill_ids`, `missing_skill_ids`, `out_of_scope_skill_ids`,
     - `recommended_projects` for missing skills (project templates with hours and difficulty).

   This underpins the **Reality Check (Job Posting)** step in the UI.

#### Use of generative AI (GPT‑4.1) and prompts

Generative AI is not used to make hidden decisions about course eligibility; it is used for **narrative and explanation** on top of deterministic planning and validation.

- **Career Storyboard**

  The backend sends a structured plan + role reality to GPT‑4.1 with a prompt such as:

  > “You are an academic advisor. Given this structured JSON plan for an undergraduate targeting the role ‘AI Engineer’, and the role reality data (tasks, salary band, skills), write 3–5 short sections that explain the path in friendly language for a student. Refer to skills and semesters, but do not invent courses. Where you make a claim, reference the provided evidence IDs. Output as a list of sections with `title`, `body`, and `citations`.”

- **Advisor Q&A**

  For enabled flows, an advisor endpoint constructs a prompt like:

  > “Here is a structured plan response, including selected role, semesters, skills, and validation errors. The student asked: ‘Why did you recommend AI Engineer?’ Reply in a friendly tone, 2–3 short paragraphs, followed by 3 bullet points explaining the reasoning. Map each bullet to citations: skills, courses, or evidence IDs. If the plan has feasibility warnings, mention them clearly.”

  GPT‑4.1 returns an answer and suggested reasoning points. The system then attaches typed citations (`AdvisorCitation`) so the UI can show clearly **what part of the plan or evidence backs each statement**.

- **Guardrails**

  - Credit limits, degree total checks, and prerequisite enforcement are **hard‑coded validators**, not LLM outputs.
  - If the LLM is disabled or errors out, core planning and validation still function; narrative features degrade gracefully.
  - No private data or secrets are embedded in prompts; only structured plan data, role metadata, and job text that the user pasted.

---

### 3. Access for evaluation

#### Code and environment

- **Repository / archive**
  - Source code is provided via this repository.
  - Technologies: Next.js 14 + React + TypeScript (frontend); Python 3 + FastAPI (backend).

- **Backend run instructions** (from the project root):

  ```bash
  cd backend
  python -m pip install -r requirements.txt
  uvicorn app.main:app --reload --port 8000
  ```

  Environment variables are provided via `backend/.env.example`; judges can optionally set `OPENAI_API_KEY` (or other provider keys) to see LLM features like storyboard and advisor Q&A. Without a key, deterministic planning and validation still run.

- **Frontend run instructions** (from the project root):

  ```bash
  cd frontend
  cp .env.local.example .env.local   # or: copy .env.local.example .env.local on Windows
  npm install
  npm run dev
  ```

  This starts the UI at `http://localhost:3000/`. The main student experience is at `/`, and admin views are under `/admin`.

#### Demo and live access

- **Recommended demo scenario**
  - Build an **AI Engineer** roadmap for an undergraduate student.
  - Walk through:
    - the 5‑step “Your path” view (reality, gaps, fusion, storyboard, job match),
    - the validation tab (including degree‑total checks),
    - Advisor Q&A,
    - and the admin insights + publish gates.

- **Video walkthrough**
  - A 2–3 minute recorded demo can accompany this document, following the AI Engineer scenario above.

- **Live URL (optional)**
  - If deployed, a public or restricted URL can be provided alongside this repository link; the app is designed to run in a standard Node + Python environment or via Docker.

#### Operating environment

- Developed and tested on **Windows 10** with:
  - Node.js (Next.js/React for the frontend),
  - Python 3.x (FastAPI backend).
- The system runs locally with no special hardware requirements; GPU is **not required** because planning and validation are CPU‑bound, and optional LLM calls are made to remote APIs.

---

This markdown file is intended to fit within the competition’s **2‑page final submission** requirement when exported to PDF (Project Overview, Methodology documentation, and Access for evaluation). Judges can refer to the root `README.md` for a hands‑on quickstart and to this document for a concise overview of goals, methods, and evaluation steps.

