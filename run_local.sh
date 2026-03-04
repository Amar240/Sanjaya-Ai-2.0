#!/usr/bin/env bash
set -e

echo "Starting Sanjaya AI backend and frontend (Unix)..."

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$ROOT_DIR/backend"
if [ "$NO_INSTALL" != "1" ]; then
  echo "Installing backend dependencies..."
  python3 -m pip install -r requirements.txt
fi
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  cp .env.example .env
fi
gnome-terminal -- bash -lc "cd \"$ROOT_DIR/backend\" && uvicorn app.main:app --reload --port 8000; exec bash" 2>/dev/null || \
osascript -e "tell app \"Terminal\" to do script \"cd '$ROOT_DIR/backend' && uvicorn app.main:app --reload --port 8000\"" 2>/dev/null || \
echo "Please run: cd backend && uvicorn app.main:app --reload --port 8000"

sleep 3

cd "$ROOT_DIR/frontend"
if [ "$NO_INSTALL" != "1" ]; then
  echo "Installing frontend dependencies..."
  npm install
fi
if [ ! -f ".env.local" ] && [ -f ".env.local.example" ]; then
  cp .env.local.example .env.local
fi
gnome-terminal -- bash -lc "cd \"$ROOT_DIR/frontend\" && npm run dev; exec bash" 2>/dev/null || \
osascript -e "tell app \"Terminal\" to do script \"cd '$ROOT_DIR/frontend' && npm run dev\"" 2>/dev/null || \
echo "Please run: cd frontend && npm run dev"

echo "Backend on http://127.0.0.1:8000 and frontend on http://127.0.0.1:3000"

