# Sanjaya AI — Data Requirements

## Current data used by the app

All data files live in `data/processed/` and are loaded at backend startup by `data_loader.py`.

| File | Records | Purpose |
|------|---------|---------|
| `courses.json` | ~2,400 | UD course catalog (ID, title, credits, prereqs, terms, department) |
| `roles_market.json` | ~25 | Market-grounded role profiles (title, required skills, department, fusion flag) |
| `skills_market.json` | ~200 | Skill definitions (ID, name, category) |
| `role_skill_evidence.json` | ~500 | Evidence linking roles to skills (provider, URL, snippet, confidence) |
| `market_sources.json` | ~30 | Source metadata for evidence (provider name, URL, type) |
| `role_reality_usa.json` | ~15 | USA job profiles (tasks, salary ranges, citations) |
| `fusion_roles.json` | ~10 | Fusion role profiles (domain + tech skill sets) |
| `fusion_packs_usa.json` | ~5 | Curated fusion packs (target roles, starter projects, domain/tech splits) |
| `project_templates.json` | ~30 | Self-study project templates (title, level, hours, skills addressed) |

## Data needed for university integration

| Data | Source | Maps to |
|------|--------|---------|
| Completed courses | UDSIS / Stellic | `PlanRequest.student_profile.completed_courses` |
| Declared major | UDSIS | Could auto-set `department_context` or filter roles |
| Program level (UG/GR) | UDSIS | `PlanRequest.student_profile.level` |
| Current semester | UDSIS | `PlanRequest.student_profile.current_semester` |
| Term offerings | Registrar / Stellic | Could improve term-offering warnings in planner |

## Adding a new university

To support a university other than UD:

1. **Replace `courses.json`** with the new catalog (same schema: id, title, credits, prerequisites, terms, department).
2. **Keep market data as-is** — roles, skills, and evidence are industry-standard and not university-specific.
3. **Optional:** Add university-specific `role_reality` or `fusion_packs` if they have regional job data.
4. **Update prereq rules** if the new university uses a different prerequisite format.
5. **Test** with a sample plan request to ensure the planner resolves courses correctly.

The pipeline is designed to be catalog-agnostic: swap the catalog, keep the agents.
