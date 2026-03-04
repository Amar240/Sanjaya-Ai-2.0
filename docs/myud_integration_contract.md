# My UD Integration Contract (Mock / API-Ready)

## Purpose
Define contract-only integration for launching SanjayaAI from a My UD tile during competition demo.

## Launch Endpoint
- `POST /integration/myud/launch`
- Request body:
  - `student_id_hash: str`
  - `major: str`
  - `class_year: int`
  - `current_term: "Fall" | "Spring" | "Summer" | "Winter"`
  - `completed_courses?: list[str]`
  - `level?: "UG" | "GR"`
  - `mode?: "CORE" | "FUSION"`
  - `interests?: list[str]`
  - `preferred_role_id?: str`
- Optional header:
  - `x_myud_signature`: HMAC SHA256 of `student_id_hash|major|class_year|current_term`
  - Enabled only when `SANJAYA_MYUD_SHARED_SECRET` is configured.

## Launch Response
- `plan_id`
- `selected_role`
- `selected_role_id`
- `coverage_pct`
- `missing_skills`
- `next_actions`
- `deep_links` (contract placeholders):
  - `course_registration`
  - `degree_planning`
  - `learning_platform`

## Summary Endpoint
- `GET /integration/myud/plan/{plan_id}/summary`
- Returns safe summary artifact:
  - `plan_id`
  - `selected_role`
  - `selected_role_id`
  - `coverage_pct`
  - `missing_skills`
  - `next_actions`

## Privacy Notes
- No raw student PII required by this contract.
- Analytics logging should not include raw personal identifiers.
