# Sanjaya AI Frontend

Next.js UI for:
- chat-style intake
- role selection from backend
- conversational intake chat (session-based)
- roadmap timeline
- skill coverage
- course purpose cards
- evidence panel and agent trace
- Fusion mode panel (domain/tech readiness + unlock skills)
- advisor Q&A panel (defended answers with citations)

## Prerequisites

- Node.js 18+ (Node.js 20 recommended)
- Backend running at `http://127.0.0.1:8000`

## Setup

```powershell
cd frontend
copy .env.local.example .env.local
npm install
```

## Run

```powershell
npm run dev
```

Open:

- Frontend: `http://127.0.0.1:3000`
- Backend docs: `http://127.0.0.1:8000/docs`

## Env

- `SANJAYA_BACKEND_URL` (default: `http://127.0.0.1:8000`)

## Notes

- Frontend calls local Next API routes (`/api/roles`, `/api/plan`) which proxy to backend.
- Frontend calls local Next API routes (`/api/roles`, `/api/plan`, `/api/chat`, `/api/advisor`) which proxy to backend.
- This avoids browser CORS issues during local development.
