#!/usr/bin/env bash
# start-android.sh - starts the backend and builds the Android app.
#
# Usage:
#   ./start-android.sh                 # auto-detects LAN IP
#   ./start-android.sh 192.168.1.42   # use specific IP
#   ./start-android.sh emulator        # for Android Studio emulator
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND="$SCRIPT_DIR/frontend"
BACKEND="$SCRIPT_DIR/backend"

# ── Resolve backend IP ───────────────────────────────────────────────────────
TARGET=${1:-""}

if [ "$TARGET" = "emulator" ]; then
  BACKEND_IP="10.0.2.2"
  echo "Mode: Android emulator (host = $BACKEND_IP)"
elif [ -n "$TARGET" ]; then
  BACKEND_IP="$TARGET"
else
  SUGGESTED=$(hostname -I 2>/dev/null | awk '{print $1}')
  read -rp "Your machine's LAN IP [${SUGGESTED}]: " INPUT
  BACKEND_IP="${INPUT:-$SUGGESTED}"
fi

BACKEND_URL="http://${BACKEND_IP}:8000"

echo ""
echo "═══════════════════════════════════════════════"
echo "  Store Navigator - Android Dev Launcher"
echo "═══════════════════════════════════════════════"
echo "  Backend URL : $BACKEND_URL"
echo ""

# ── 1. Start backend ─────────────────────────────────────────────────────────
echo "▸ Setting up Python backend …"
cd "$BACKEND"

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt

echo "▸ Starting backend on 0.0.0.0:8000 …"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd "$SCRIPT_DIR"

# Give backend a moment to start
sleep 2

# ── 2. Write env for Vite build ──────────────────────────────────────────────
cat > "$FRONTEND/.env.production" <<EOF
VITE_BACKEND_URL=$BACKEND_URL
EOF

# ── 3. Install frontend deps ─────────────────────────────────────────────────
echo ""
echo "▸ Installing frontend dependencies …"
cd "$FRONTEND"
npm install --silent

# ── 4. Init Capacitor + Android platform (first run only) ───────────────────
if [ ! -d "$FRONTEND/android" ]; then
  echo ""
  echo "▸ Initialising Capacitor (first time only) …"
  npx cap init "Store Navigator" "com.ire.storenavigator" --web-dir dist
  npx cap add android
fi

# ── 5. Build web app ─────────────────────────────────────────────────────────
echo ""
echo "▸ Building web app …"
npm run build

# ── 6. Sync into Android project ─────────────────────────────────────────────
echo ""
echo "▸ Syncing into Android project …"
npx cap sync android

cd "$SCRIPT_DIR"

# ── 7. Print instructions ────────────────────────────────────────────────────
WIN_PATH=$(wslpath -w "$FRONTEND/android" 2>/dev/null || echo "frontend/android")

echo ""
echo "════════════════════════════════════════════════"
echo "  Backend running  →  http://${BACKEND_IP}:8000"
echo ""
echo "  Open in Android Studio (Windows):"
echo "  $WIN_PATH"
echo ""
echo "  Then press ▶ to run on emulator or phone."
echo ""
echo "  Press Ctrl+C to stop the backend."
echo "════════════════════════════════════════════════"

trap "echo ''; echo 'Stopping backend…'; kill $BACKEND_PID 2>/dev/null; exit 0" INT TERM
wait $BACKEND_PID
