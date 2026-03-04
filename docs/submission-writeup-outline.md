# Sanjaya AI — 2-Page Ignite Submission Outline

Expand each bullet below into 1–3 sentences for the final PDF.

---

## 1. Problem

- Students choose courses blindly. There is no clear link between what they take and the jobs they will apply for, the skills those jobs require, and the salary they can expect.
- This disconnect means graduates are often shocked by the job market — they lack critical skills, have no portfolio evidence, and have no way to verify if their path was realistic.
- No existing university tool shows students the full chain: role → required skills → courses → semester plan → gaps → next steps.

## 2. Approach

- Sanjaya AI is an LLM + RAG application that generates personalized, verified course-to-career roadmaps.
- It grounds every recommendation in real data: the university course catalog, market role–skill evidence, US salary ranges, and prerequisite rules.
- The system uses a multi-agent pipeline: a planner agent selects roles and courses, a verifier agent checks prerequisite safety and credit limits, an evidence agent links skills to market sources, and an advisor agent answers student questions with citations.
- For interdisciplinary students, a Fusion mode combines two domains (e.g. Finance + CS) using curated skill packs and project templates.

## 3. Datasets

| Dataset | Source | Size | Purpose |
|---------|--------|------|---------|
| UD Course Catalog | `courses.json` | ~2,400 courses | Course IDs, titles, credits, prereqs, terms |
| Market Roles | `roles_market.json` | ~25 roles | Role titles, required skills, departments |
| Skills & Evidence | `skills_market.json`, `role_skill_evidence.json` | ~200 skills, ~500 evidence items | Skill definitions, evidence sources, confidence |
| Role Reality (USA) | `role_reality_usa.json` | ~15 profiles | Job tasks, salary ranges, citations |
| Fusion Packs | `fusion_packs_usa.json` | ~5 packs | Interdisciplinary skill bundles, starter projects |
| Project Templates | `project_templates.json` | ~30 templates | Self-study projects for gap-filling |

## 4. Safety and Explainability

- **No hallucinated courses.** The planner only selects courses from the loaded catalog. The verifier rejects unknown course IDs.
- **Prerequisite safety.** Every semester plan is checked for prerequisite chains and credit limits. Violations appear as warnings.
- **Explainable.** Every skill, course, and recommendation is linked to evidence with provider, URL, and snippet. The advisor cites only IDs in the plan.
- **Safety limits.** The advisor refuses to guarantee outcomes, redirect to external content, or answer questions outside the plan context.
- **Disclaimers.** Salary ranges are labeled as market estimates. The app clearly states it provides guidance, not guarantees.

## 5. Demo Access

- **Live URL:** [to be filled — e.g. https://sanjaya-demo.vercel.app or localhost instructions]
- **Video:** [optional — link to a 3-minute recorded demo]
- **Code:** [GitHub repo link — confirm public or provide access]

## 6. Technical Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, React, CSS design system |
| Backend | Python FastAPI, multi-agent pipeline |
| LLM | Groq (default), optional OpenAI/Anthropic fallback |
| Data | Static JSON files (catalog, evidence, roles) |
| Hosting | Local or Vercel (frontend) + Render/Railway (backend) |

## 7. Impact

- **Primary audience:** UG freshmen who don't know how courses connect to jobs.
- **Fusion:** Helps interdisciplinary students find roles that combine their passions (e.g. Finance + CS → FinTech).
- **Integration path:** Designed to embed in university portals (e.g. MyUD) as a tile or widget, pre-filling from student information systems.
- **Scalable:** Adding new universities requires only a new course catalog and role mapping. The pipeline is catalog-agnostic.
