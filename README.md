# Intelligent Retail Ecosystem (IRE)
### Ambient Intelligence – In-Store Navigation & Product Finder

> AmI project – Alameda G11  
> David Correia · Gonçalo Oliveira · Pedro Duarte

---

## Overview

A full-stack **Ambient Intelligence** prototype that bridges the gap between digital inventory and physical navigation in large retail environments (e.g. IKEA, supermarkets).

### Key Features

| Feature | Description |
|---------|-------------|
| **BLE Trilateration** | Fuses RSSI from 3× ESP32 gateways to compute user position |
| **IMU/PDR Kalman Fusion** | Combines phone accelerometer + gyroscope for sub-metre tracking |
| **A\* Pathfinding** | Real-time optimised routes on a 2D floor map |
| **Multi-Product Routing** | Nearest-neighbour TSP heuristic for shopping lists |
| **Voice Search** | Hands-free product lookup via Web Speech API |
| **YOLO Shelf Detection** | CV-powered product identification & visual highlighting |
| **Staff Shelf Scanner** | Photo-based inventory auto-registration |
| **Progressive Web App** | Mobile-first, installable, works offline |

---

## Architecture

```
┌─────────────┐     BLE RSSI      ┌──────────────┐
│  ESP32 × 3  │ ────── MQTT ────→ │              │
│  Gateways   │                    │   FastAPI    │
└─────────────┘                    │   Backend    │
                                   │              │
┌─────────────┐    WebSocket       │  • Trilat.   │
│  React PWA  │ ←──────────────→   │  • Kalman    │
│  (Phone)    │    IMU + Position  │  • A* Path   │
│             │                    │  • YOLO CV   │
│  • Floor Map│    REST API        │  • SQLite DB │
│  • Voice    │ ←──────────────→   │              │
│  • Shelf    │                    └──────────────┘
└─────────────┘
```

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

### Access

| Service | URL |
|---------|-----|
| Frontend (PWA) | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |

---

## Project Structure

```
AmI_project/
├── backend/
│   ├── app/
│   │   ├── core/           # Config, DB session
│   │   ├── models/         # SQLAlchemy + Pydantic schemas
│   │   ├── routers/        # API endpoints
│   │   │   ├── products.py     # CRUD products & shelves
│   │   │   ├── navigation.py   # Path computation
│   │   │   └── tracking.py     # WebSocket real-time position
│   │   ├── services/       # Business logic
│   │   │   ├── ble_trilateration.py  # RSSI → (x,y)
│   │   │   ├── kalman_fusion.py      # BLE + IMU fusion
│   │   │   ├── pathfinding.py        # A* + multi-route
│   │   │   └── mqtt_client.py        # ESP32 MQTT listener
│   │   └── main.py         # FastAPI app + lifespan
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/     # React components
│   │   │   ├── FloorMap.jsx       # 2D canvas map
│   │   │   ├── SearchBar.jsx      # Text + voice search
│   │   │   ├── ProductList.jsx    # Product cards
│   │   │   ├── ShelfView.jsx      # Micro-navigation view
│   │   │   ├── ScanUpload.jsx     # Staff scan tool
│   │   │   └── StatusBar.jsx      # Connection badge
│   │   ├── hooks/
│   │   │   ├── useIMU.js          # Device motion streaming
│   │   │   └── useVoiceSearch.js  # Web Speech API
│   │   ├── services/
│   │   │   ├── api.js             # REST client
│   │   │   └── websocket.js       # WS tracking client
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
├── esp32_gateway/
│   └── esp32_gateway.ino    # Arduino sketch for BLE scanning
├── docker-compose.yml
├── mosquitto.conf
└── start-dev.sh
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/products?q=` | Search products |
| POST | `/api/products` | Create product |
| GET | `/api/shelves` | List shelves |
| POST | `/api/shelves` | Create shelf |
| POST | `/api/navigate` | Compute navigation path |
| POST | `/api/shelves/{id}/scan` | Upload shelf photo → YOLO |
| WS | `/ws/track/{session_id}` | Real-time position tracking |
| GET | `/health` | Health check |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, SQLAlchemy, SQLite |
| Localisation | BLE trilateration, Kalman filter, PDR |
| Pathfinding | A\* with Douglas-Peucker simplification |
| Computer Vision | YOLOv8 (Ultralytics), OpenCV |
| Communication | MQTT (Mosquitto), WebSockets |
| Frontend | React 18, Vite, Canvas API |
| Voice | Web Speech API |
| IoT | ESP32-WROOM (Arduino), BLE 4.0+ |
| Deployment | Docker Compose, PWA |

---

## ESP32 Setup

1. Open `esp32_gateway/esp32_gateway.ino` in Arduino IDE
2. Install **PubSubClient** library
3. Set `GATEWAY_ID`, WiFi credentials, and MQTT broker IP
4. Flash to each of the 3 ESP32 boards (change `GATEWAY_ID` for each)

---

## Demo Data

The backend auto-seeds:
- **9 shelves** across 4 aisles + 1 end-cap
- **18 products** (IKEA-style: KALLAX, BILLY, MALM, POÄNG, etc.)

---

## Milestones

- [x] **M1 – Basic**: ESP32 pipeline, 2D map, raw BLE tracking
- [x] **M2 – Intermediate**: Hybrid BLE+IMU fusion, shelf view
- [x] **M3 – Advanced**: YOLO detection, voice search, multi-product routing
