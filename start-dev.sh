#!/usr/bin/env bash
# ── Quick-start script for local development ──
set -e

echo "═══════════════════════════════════════════════"
echo "  Intelligent Retail Ecosystem – Dev Launcher"
echo "═══════════════════════════════════════════════"

# 1. Backend
echo ""
echo "▸ Setting up Python backend …"
cd backend

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt

echo "▸ Starting backend on :8000 …"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# 2. Frontend
echo ""
echo "▸ Setting up React frontend …"
cd frontend
npm install --silent
echo "▸ Starting frontend on :3000 …"
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "════════════════════════════════════════════════"
echo "  Backend  → http://localhost:8000"
echo "  Frontend → http://localhost:3000"
echo "  API docs → http://localhost:8000/docs"
echo "════════════════════════════════════════════════"
echo "Press Ctrl+C to stop all services."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
