# Phase 7C Frontend Manual QA Checklist

## Preconditions
- Backend running and includes Phase 7A+ fields (`plan_id`, `candidate_roles`, evidence metadata, advisor `plan_id` support).
- Frontend running with `SANJAYA_BACKEND_URL` pointing to backend.

## Checklist
1. Generate a plan from Intake.
   - Confirm metadata block shows:
     - `plan_id`
     - `data_version`
     - `cache_status`
     - `request_id`
   - Confirm node timings are visible under collapsible details.

2. Verify validation issues grouping.
   - Confirm `validation_errors` render grouped by `code` and `severity`.
   - Confirm warnings/errors are visually distinguished.

3. Verify role alternatives.
   - Confirm selected role renders.
   - Confirm “Top Alternatives” renders with:
     - role title/id
     - score
     - reasons (bullet list)

4. Verify “Ask: Why not this role?” button.
   - Click button on an alternative role.
   - Confirm advisor question is auto-triggered and answer appears.
   - Confirm network request payload uses `plan_id` (not full `plan`).

5. Verify evidence panel enrichment.
   - Confirm each evidence row shows:
     - provider badge
     - retrieval method
     - rank score (when available)
     - snippet + source link
   - Toggle “Show only selected-plan skills” and verify filtering.

6. Verify citation navigation.
   - Ask advisor a question producing citations.
   - For citation with:
     - `evidence_id`: clicking “Jump to context” scrolls/highlights evidence row.
     - `course_id`: scrolls/highlights first matching course in semester roadmap.
     - `skill_id`: scrolls/highlights skill coverage row.

7. Verify safety posture.
   - Ask a job guarantee question.
   - Confirm answer remains bounded (no guarantees).
