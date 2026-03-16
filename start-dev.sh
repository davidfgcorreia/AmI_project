#!/usr/bin/env bash
# ── Quick-start script for local development ──
set -e

echo "═══════════════════════════════════════════════"
echo "  Intelligent Retail Ecosystem - Dev Launcher"
echo "═══════════════════════════════════════════════"

# ── Detect local network IP ──
get_local_ip() {
  # Try hostname -I first (Linux/WSL), fall back to ip route, then ifconfig
  local ip
  ip=$(hostname -I 2>/dev/null | awk '{print $1}')
  if [ -z "$ip" ]; then
    ip=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}')
  fi
  if [ -z "$ip" ]; then
    ip=$(ifconfig 2>/dev/null | grep 'inet ' | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
  fi
  echo "$ip"
}

LOCAL_IP=$(get_local_ip)

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

# 2. Frontend (--host exposes to all network interfaces)
echo ""
echo "▸ Setting up React frontend …"
cd frontend
npm install --silent
echo "▸ Starting frontend on :3000 (network-accessible) …"
npm run dev -- --host 0.0.0.0 &
FRONTEND_PID=$!
cd ..

# Give Vite a moment to bind
sleep 2

echo ""
echo "════════════════════════════════════════════════"
echo "  LOCAL"
echo "    Frontend → http://localhost:3000"
echo "    Backend  → http://localhost:8000"
echo "    API docs → http://localhost:8000/docs"
if [ -n "$LOCAL_IP" ]; then
echo ""
echo "  PHONE / TABLET  (same Wi-Fi)"
echo "    Frontend → http://$LOCAL_IP:3000   <-- open this on your phone"
echo "    Backend  → http://$LOCAL_IP:8000"
fi
echo "════════════════════════════════════════════════"
echo "Press Ctrl+C to stop all services."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM EXIT
wait
