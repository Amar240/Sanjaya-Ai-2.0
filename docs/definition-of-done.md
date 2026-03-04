# Sanjaya AI — Definition of Done (Submission Checklist)

## Phase 1 — Foundation
- [x] `frontend/lib/copy.ts` created with all user-facing strings
- [x] `docs/phase1-ia-and-convince.md` created with IA and convince checklist
- [x] Design tokens added to `frontend/app/globals.css`
- [x] Core UI components created in `frontend/components/ui/` (Button, Card, Chip, SectionHeader, ProgressStepper, Tabs, EmptyState, Alert)
- [x] Copy wired into page.tsx, IntakeForm, PlanDashboard, PlanSummaryBar, AdvisorQAPanel

## Phase 2 — Flows and UX
- [x] Landing page: hero, 3-step visual, differentiator cards, primary CTA
- [x] IntakeForm: copy updated, fusion domain helper text
- [x] PlanDashboard: Brain Picture is the main story, plan hero line added
- [x] Fusion tab: only visible when fusion data exists, hidden note when not
- [x] Advisor: suggested question chips, copy from `copy.ts`
- [x] Plan Metadata and readiness moved to collapsed "Technical details"

## Phase 3 — Polish and Reliability
- [x] Loading/error handling: copy-based error messages, retry-friendly
- [x] Accessibility: focus-visible on all interactive elements, ARIA on tabs
- [x] Responsiveness: mobile breakpoints for grid, tabs, summary bar
- [x] `backend/docs/prompts.md`: prompt documentation for all LLM flows
- [x] LLM config: documented env vars for provider routing and fallbacks

## Phase 4 — Convince and Ship
- [x] `docs/demo-script.md`: 3-minute demo script with exact seed and talking points
- [x] `docs/submission-writeup-outline.md`: 2-page outline ready to expand
- [x] `docs/integration-options.md`: four integration models (Tile → Embed)
- [x] `docs/data-requirements.md`: current data inventory and integration needs
- [x] `docs/ops-runbook.md`: run instructions, env vars, common issues
- [x] `docs/definition-of-done.md`: this file

## Build verification
- [ ] `npm run build` passes in `frontend/` (no TypeScript or build errors)
- [ ] Backend starts: `uvicorn app.main:app` loads without errors
- [ ] Demo flow: intake → plan → Brain Picture steps → advisor — all render
- [ ] Fusion demo: UG, Fusion mode, domain "finance", fusion role → Step 3 populated
- [ ] Storyboard: Generate Storyboard → sections render (deterministic fallback if no LLM)
- [ ] Job Match: Load preset → Extract & Match → coverage buckets render

## Repo hygiene
- [ ] No `.env` files committed
- [ ] No API keys in source
- [ ] README has run instructions and demo URL
- [ ] `docs/` folder has all deliverables listed above
