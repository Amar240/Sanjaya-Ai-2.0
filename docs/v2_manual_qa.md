# SanjayaAi v2.0 Manual QA

## Preconditions
- Backend running on `http://127.0.0.1:8000`
- Frontend running on `http://localhost:3000`
- `data/processed/role_reality_usa.json` and `data/processed/project_templates.json` present

## 1) Plan Includes Reality + Gap
1. Open `http://localhost:3000`.
2. Fill intake and generate a plan.
3. Verify plan metadata shows `plan_id`.
4. Open `Brain Picture` panel:
   - `Reality View` tab shows role tasks, salary ranges, and source IDs.
   - `Skills Gap` tab shows missing skills and project templates.

## 2) Storyboard Flow
1. In `Brain Picture`, open `Storyboard` tab.
2. Click `Generate Storyboard`.
3. Verify sections are returned with citations (`source_id` and/or `evidence_id`).
4. Confirm `llm_status` is `disabled` by default unless `SANJAYA_ENABLE_LLM_STORYBOARD=1`.

## 3) Grounding / Safety
1. Confirm salary text reads as ranges (not guarantees).
2. Confirm source links are shown when source metadata exists in plan evidence.
3. Confirm advisor still works by `plan_id` (no full plan payload required).
