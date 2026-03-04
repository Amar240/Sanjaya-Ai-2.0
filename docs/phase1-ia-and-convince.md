# Phase 1 — Information Architecture & Convince Checklist

## Information Architecture (Section Order)

Every student-facing screen follows this order from top to bottom:

1. **Landing** — Hero (eyebrow + headline + support), 3-step visual, three differentiator cards, primary CTA ("Build my roadmap").
2. **Intake** — Stepper (About you → Interests & role → Review & generate), fields grouped by step, one primary CTA at the end ("Generate my roadmap").
3. **Plan Summary** — "Your path to {role}" hero line + muted support line + summary bar (readiness, coverage, warnings, disclaimer).
4. **Brain Picture** — "Your plan in 5 steps" with ordered tabs:
   - Step 1: Target Reality
   - Step 2: Skill Gaps
   - Step 3: Fusion Opportunities (only when fusion data exists)
   - Step 4: Career Storyboard
   - Step 5: Reality Check (Job Posting)
5. **Timeline** — Semester cards (Career Path Map / visual flow).
6. **Evidence / Course Cards** — Evidence panel and course purpose cards (optional detail section).
7. **Advisor** — Always reachable; title + helper + quick-question chips + Q&A thread.
8. **Technical Details** — Collapsed by default (plan ID, cache status, request ID, node timings, readiness factors).

## Convince Checklist (Per Screen)

### Landing
- [ ] One headline that states the problem or benefit.
- [ ] One primary CTA visible above the fold.
- [ ] At least one trust element ("Grounded in real data" or catalog/evidence mention).
- [ ] 3-step visual that previews the flow.

### Intake
- [ ] One primary CTA ("Generate my roadmap").
- [ ] Progress is visible (stepper or numbered steps).
- [ ] No more than one focus per step.
- [ ] Fusion domain helper text shown when FUSION mode is selected.

### Plan (Brain Picture)
- [ ] "Your path to {role}" is the first thing the user sees after plan loads.
- [ ] Brain Picture is the main content block (not buried after metadata).
- [ ] One primary action per step (e.g. Generate Storyboard, Paste job posting).
- [ ] Fusion tab hidden when no fusion data exists; short note explains when it appears.

### Advisor
- [ ] Citations are visible in every answer.
- [ ] At least one suggested question chip is shown.
- [ ] Reasoning bullets are rendered when present.

### Technical Details
- [ ] Collapsed by default.
- [ ] Only expanded on user action.
- [ ] Does not compete with primary content.
