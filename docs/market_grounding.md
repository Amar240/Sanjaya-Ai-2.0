# Market Grounding Layer

This layer keeps `skills` and `roles` tied to external labor-market sources, while preserving your existing baseline files.

## Added files

- `data/processed/market_sources.json`
- `data/processed/skills_market.json`
- `data/processed/roles_market.json`
- `data/processed/role_skill_evidence.json`

## Design

- `market_sources.json` is the canonical source registry with URL + retrieval date.
- `skills_market.json` defines market-grounded skills and references source IDs.
- `roles_market.json` defines role requirements and references source IDs.
- `role_skill_evidence.json` provides explainable links from role to skill with confidence and provenance.

## Grounding types

- `direct`: role maps directly to a published occupation profile.
- `composite`: role is synthesized from multiple trustworthy occupation profiles (common for titles like AI Engineer / ML Engineer / Data Engineer).

## Why this is safe

- Existing baseline files were not deleted:
  - `data/processed/skills.json`
  - `data/processed/roles.json`
- New market files can be tested first, then promoted after review.

## Promotion options

1. Keep both layers:
   - baseline for current demos
   - market layer for new explainable mode
2. Promote market layer:
   - replace `skills.json` with `skills_market.json`
   - replace `roles.json` with `roles_market.json`
3. Hybrid:
   - use market files for role/skill retrieval
   - keep baseline files as fallback
