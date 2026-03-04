# Sanjaya AI — Ops Runbook

## Running the app

### Backend

```bash
cd SanjayaAi/backend
python -m venv .venv312
.venv312\Scripts\activate      # Windows
# source .venv312/bin/activate  # macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Verify: `GET http://localhost:8000/health` should return `{"status": "ok"}`.

### Frontend

```bash
cd SanjayaAi/frontend
npm install
npm run dev
```

Verify: `http://localhost:3000` should load the landing page.

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `GROQ_API_KEY` | (none) | API key for Groq LLM (chat, advisor, storyboard) |
| `OPENAI_API_KEY` | (none) | Optional: OpenAI fallback for storyboard/advisor |
| `STORYBOARD_LLM_ENABLED` | `false` | Enable LLM rewrite for storyboard (set to `true` for best quality) |
| `ADVISOR_LLM_ENABLED` | `false` | Enable LLM rewrite for advisor answers |
| `JOB_EXTRACTOR_LLM_ENABLED` | `false` | Enable LLM-based job extraction |
| `BEST_LLM_PROVIDER` | (none) | Preferred provider for storyboard/advisor: `groq`, `openai`, `anthropic` |
| `BACKEND_URL` | `http://localhost:8000` | Backend URL used by frontend API routes |

## Common issues

### "No roles loaded" in frontend
- Backend is not running or `/roles` endpoint failed.
- Check backend logs for data loading errors.
- Verify `data/processed/roles_market.json` exists and is valid JSON.

### Plan generation takes too long
- LLM calls add latency. If the demo is time-sensitive, ensure `STORYBOARD_LLM_ENABLED=false` — deterministic storyboard is instant.
- Check Groq API status if using Groq.

### Advisor returns "fallback"
- The LLM provider is unavailable. The deterministic advisor logic answered instead.
- This is by design — the app never fails silently. Check `llm_error` in the response for details.

### CORS errors
- Backend must allow `http://localhost:3000` (or wherever the frontend is hosted).
- Check `app/main.py` for CORS middleware configuration.

## Logs

- Backend logs go to stdout (uvicorn default).
- All LLM calls log: prompt (truncated), response latency, success/failure.
- No PII is logged. Student profile data is not persisted.

## Health checks

- Backend: `GET /health` → `{"status": "ok"}`
- Frontend: Load `http://localhost:3000` → Hero should render
- Roles: `GET /roles` → Should return a JSON array of role objects
