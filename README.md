# Intelligent Retail Ecosystem (IRE)
### Ambient Intelligence — In-Store Navigation & Product Finder

> AmI project — Alameda G11
> David Correia · Gonçalo Oliveira · Pedro Duarte

---

## Overview

A full-stack **Ambient Intelligence** prototype for in-store navigation and product finding. Users are located via BLE trilateration (3× ESP32 gateways) fused with phone IMU data using a Kalman filter, and guided to products via A* pathfinding on a 2D floor map.

### Key Features

| Feature | Description |
|---------|-------------|
| **BLE Trilateration** | Fuses RSSI from 3× ESP32 gateways to compute user position via weighted least-squares |
| **IMU/PDR Kalman Fusion** | Combines step detection + heading for sub-metre tracking between BLE updates |
| **A\* Pathfinding** | Real-time obstacle-aware routes on a 2D grid with Douglas-Peucker simplification |
| **Multi-Product Routing** | Nearest-neighbour TSP + 2-opt optimisation for shopping lists |
| **TTS Turn-by-Turn Navigation** | Voice-guided directions at each waypoint with arrival announcements |
| **Native Voice Search** | Android speech recognition with Web Speech API fallback |
| **Admin Panel** | Non-technical staff can manage shelves, products, and store layout |
| **YOLO Shelf Detection** | CV-powered product identification & visual highlighting |

---

## Architecture

```
┌─────────────┐     BLE RSSI      ┌──────────────┐
│  ESP32 × 3  │ ────── MQTT ────→ │              │
│  Gateways   │                    │   FastAPI    │
└─────────────┘                    │   Backend    │
                                   │              │
┌─────────────┐    WebSocket       │  • Trilat.   │
│  Android    │ ←──────────────→   │  • Kalman    │
│  App        │    IMU + Position  │  • A* Path   │
│  (WebView)  │                    │  • SQLite DB │
│             │    REST API        │              │
│  • Floor Map│ ←──────────────→   └──────────────┘
│  • TTS Nav  │
│  • Voice    │
│  • Admin    │
└─────────────┘
```

### Data Flow

1. **ESP32 gateways** scan for BLE advertisements with `IRE-` prefix, publish RSSI to MQTT topic `ire/ble/rssi`
2. **MQTT client** receives readings into an in-memory buffer keyed by `session_id`, with EMA smoothing
3. **Android app** sends IMU data (heading, steps) via WebSocket `/ws/track/{session_id}`
4. **Tracking handler** on each IMU message: Kalman predict (PDR), then update with BLE trilateration when ≥3 fresh gateway readings are available
5. **Frontend** renders fused position on canvas with turn-by-turn TTS navigation

---

## Quick Start

### Option A: Local Development

```bash
# 1. Start everything
./start-dev.sh

# Or manually:

# Backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

### Option B: Docker Compose

```bash
docker-compose up --build
```

### Option C: Simulator (no hardware needed)

```bash
cd simulator
python simulator.py              # HTTP mode
python simulator.py --mqtt       # MQTT mode (requires mosquitto)
# Options: --speed 0.5, --session my-phone, --loop, --quiet
```

### Access

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |

---

## Project Structure

```
AmI_project/
├── android/                      # Native Android app (Kotlin)
│   └── app/src/main/java/com/example/amishopengine/
│       ├── MainActivity.kt           # WebView host + permissions
│       ├── BleAdvertiser.kt          # BLE advertising (IRE-xxx)
│       ├── ImuManager.kt             # Step detection + heading
│       ├── NativeBridge.kt           # JS ↔ Kotlin interface
│       ├── SpeechHelper.kt           # Native speech recognition
│       └── SessionManager.kt         # Session ID management
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py             # All tuneable constants
│   │   │   └── database.py           # Async SQLAlchemy engine
│   │   ├── models/
│   │   │   ├── database.py           # ORM: Product, Shelf
│   │   │   └── schemas.py            # Pydantic schemas
│   │   ├── routers/
│   │   │   ├── products.py           # CRUD + fuzzy search
│   │   │   ├── navigation.py         # A* pathfinding + multi-route
│   │   │   ├── tracking.py           # WebSocket tracking + BLE REST
│   │   │   └── gateways.py           # Gateway status WebSocket
│   │   ├── services/
│   │   │   ├── ble_trilateration.py  # RSSI → (x, y) least-squares
│   │   │   ├── kalman_fusion.py      # Kalman filter [x, y, vx, vy]
│   │   │   ├── pathfinding.py        # A* + Douglas-Peucker + TSP
│   │   │   ├── mqtt_client.py        # MQTT subscriber + EMA buffer
│   │   │   ├── session_manager.py    # Active session tracking
│   │   │   └── csv_logger.py         # Per-session position logs
│   │   └── main.py                   # FastAPI app + lifespan
│   ├── scripts/
│   │   ├── mqtt_rssi_listener.py     # Debug: live RSSI monitor
│   │   └── mqtt_xy_position_listener.py  # Debug: position monitor
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── FloorMap.jsx          # 2D canvas map (rotated portrait)
│   │   │   ├── SearchBar.jsx         # Text + voice search
│   │   │   ├── NavQueue.jsx          # Shopping list / route queue
│   │   │   ├── AdminPanel.jsx        # Shelf & product management
│   │   │   ├── VoiceMenu.jsx         # TTS toggle + voice controls
│   │   │   └── StatusBar.jsx         # Connection status badge
│   │   ├── hooks/
│   │   │   ├── useIMU.js             # Device motion → WebSocket
│   │   │   ├── useNavigation.js      # TTS turn-by-turn engine
│   │   │   └── useVoiceSearch.js     # Native + Web Speech API
│   │   ├── services/
│   │   │   ├── api.js                # REST client
│   │   │   ├── websocket.js          # WS with auto-reconnect + ping
│   │   │   ├── sound.js              # TTS speech synthesis
│   │   │   └── ble.js                # BLE advertising bridge
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
├── esp32_gateway/
│   └── esp32_gateway.ino             # BLE scan → MQTT (IRE- filter)
├── simulator/
│   └── simulator.py                  # Hardware-free testing
├── docker-compose.yml
├── mosquitto.conf
└── start-dev.sh
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/products?q=` | Fuzzy search products |
| GET | `/api/products` | List all products |
| POST | `/api/products` | Create product |
| PUT | `/api/products/{id}` | Update product |
| DELETE | `/api/products/{id}` | Delete product |
| GET | `/api/shelves` | List shelves |
| POST | `/api/shelves` | Create shelf (circle/rect) |
| PUT | `/api/shelves/{id}` | Update shelf |
| DELETE | `/api/shelves/{id}` | Delete shelf |
| POST | `/api/navigate` | Compute A* navigation path |
| WS | `/ws/track/{session_id}` | Real-time position tracking |
| WS | `/ws/gateways` | Live gateway status |
| GET | `/health` | Health check |

---

## Configuration

All tuneable constants are in `backend/app/core/config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `STORE_WIDTH` | 10 m | Store floor width |
| `STORE_HEIGHT` | 5 m | Store floor length |
| `GRID_RESOLUTION` | 0.25 m | A* pathfinding grid cell size |
| `BLE_TX_POWER` | -68.1 dBm | RSSI at 1 m reference distance |
| `KALMAN_PROCESS_NOISE` | 0.3 | Kalman Q base (per second) |
| `KALMAN_MEASUREMENT_NOISE` | 1.5 | Kalman R base |
| `HEADING_OFFSET` | 0.0 rad | Calibrate per demo room |

Gateway positions are configured per deployment in the same file.

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Mobile App | Kotlin, Android WebView, BLE Advertiser |
| Backend | Python 3.11, FastAPI, SQLAlchemy, SQLite |
| Localisation | BLE trilateration (least-squares), Kalman filter, PDR |
| Pathfinding | A\* with Douglas-Peucker simplification, 2-opt TSP |
| Communication | MQTT (Mosquitto), WebSockets |
| Frontend | React 18, Vite, Canvas 2D |
| Voice | Android SpeechRecognizer, Web Speech API, SpeechSynthesis TTS |
| IoT | ESP32-WROOM (Arduino), BLE 4.0+ |
| Deployment | Docker Compose |

---

## ESP32 Setup

1. Open `esp32_gateway/esp32_gateway.ino` in Arduino IDE
2. Install **PubSubClient** library
3. Set `GATEWAY_ID` (`esp32_A`, `esp32_B`, `esp32_C`), WiFi credentials, and MQTT broker IP
4. Flash each of the 3 ESP32 boards with a unique `GATEWAY_ID`

The gateways filter BLE advertisements by the `IRE-` name prefix — only your app's signals are forwarded to MQTT.

---

## Android App

The Android app wraps the React frontend in a WebView and provides native access to:
- **BLE advertising** — broadcasts `IRE-{sessionId}` for ESP32 gateways to detect
- **IMU sensors** — `TYPE_STEP_DETECTOR` + `TYPE_ROTATION_VECTOR` at ~10 Hz
- **Speech recognition** — native `SpeechRecognizer` for voice product search

Set `FRONTEND_URL` in `MainActivity.kt` to your backend server's LAN IP before building.

```bash
cd android
./gradlew assembleDebug
# APK at: app/build/outputs/apk/debug/app-debug.apk
```

---

## Demo Data

The backend auto-seeds on first run:
- **9 shelves** with configurable shapes (circle/rectangle)
- **18 products** across shelves with shelf level indicators (bottom → top)
