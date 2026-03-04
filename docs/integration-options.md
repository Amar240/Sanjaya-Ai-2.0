# Sanjaya AI — University Integration Options

This document describes how Sanjaya AI could plug into a university portal such as MyUD.

---

## Integration Models

### A. Tile / Link

The simplest integration: add a tile on the student dashboard (e.g. MyUD) that links to the Sanjaya app.

**What the university provides:**
- A tile slot on their portal.
- (Optional) SSO redirect so the student is authenticated when they land.

**What Sanjaya needs:**
- A publicly accessible deployment (e.g. `sanjaya.udel.edu`).
- (Optional) SSO integration (SAML/OIDC) to identify the student.

**Effort:** Low. No data exchange.

### B. "I want to…" Search API

Sanjaya exposes an API that the portal calls when a student types a career question (e.g. "I want to become a data scientist").

**What the university provides:**
- A search bar or "I want to…" widget in their portal.
- Forwards the query to Sanjaya's API.

**What Sanjaya needs:**
- A `/search` or `/quick-match` endpoint that returns: matched role, top-3 skills, and a link to the full plan.
- Authentication token from the portal.

**Effort:** Medium. Requires a new endpoint and API key management.

### C. Pre-fill from Student Information System (UDSIS / Stellic)

The portal sends the student's completed courses, major, and level to Sanjaya so the intake is pre-filled.

**What the university provides:**
- An API or data feed with: completed course IDs, declared major, program level, current semester.
- Example sources: UDSIS (student information system), Stellic (degree planning tool).

**What Sanjaya needs:**
- Map incoming course IDs to the Sanjaya catalog (`courses.json`).
- Accept a `completed_courses` array in the `PlanRequest` payload (already supported).
- Accept `level` and optional `major` from the pre-fill.

**Effort:** Medium-High. Requires data mapping and API authentication.

### D. Embed in Stellic

Sanjaya's plan output is displayed inline within Stellic's degree planning interface.

**What the university provides:**
- An iframe or widget slot in Stellic.
- Student context (courses, major) passed via URL params or postMessage.

**What Sanjaya needs:**
- An embeddable mode (e.g. `/embed?plan_id=...`) that renders the Brain Picture without the full app shell.
- CORS configuration to allow the Stellic domain.

**Effort:** High. Requires embed mode, CORS, and Stellic coordination.

---

## Data the university would provide

| Data | Source | Used for |
|------|--------|----------|
| Completed courses | UDSIS / Stellic | Pre-fill intake, skip already-taken courses |
| Declared major | UDSIS | Auto-set department context, suggest roles |
| Program level | UDSIS | Auto-set UG/GR |
| Current semester | UDSIS | Auto-set semester index |
| Student ID (hashed) | SSO | Session tracking (no PII stored) |

## What Sanjaya already supports

- `PlanRequest.student_profile.completed_courses` accepts an array of course IDs.
- `PlanRequest.student_profile.level` accepts `"UG"` or `"GR"`.
- The backend validates incoming course IDs against the loaded catalog.
- No student data is persisted — the app is stateless.

---

## Recommended first step

**Model A (Tile/Link)** for the competition and initial adoption. Minimal effort, demonstrates value. Follow with **Model C (Pre-fill)** once the university agrees to share course data.
