# ESP32 BLE Gateway – MQTT Integration Guide

> **Status: TO BE IMPLEMENTED**
> This document describes how the ESP32 gateways will connect to the backend via MQTT to enable real-time indoor positioning. It serves as the implementation plan for the physical hardware deployment phase.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Network Setup — ESP32 to Desktop via WiFi](#network-setup--esp32-to-desktop-via-wifi)
3. [Data Flow](#data-flow)
4. [MQTT Topic & Payload Format](#mqtt-topic--payload-format)
5. [Hardware Requirements](#hardware-requirements)
6. [ESP32 Firmware Setup](#esp32-firmware-setup)
7. [Mosquitto Broker Setup](#mosquitto-broker-setup)
8. [Backend MQTT Listener](#backend-mqtt-listener)
9. [Gateway Placement & Configuration](#gateway-placement--configuration)
10. [Calibration](#calibration)
11. [Testing with the Simulator](#testing-with-the-simulator)
12. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
┌──────────┐  BLE adverts   ┌───────────┐  MQTT publish   ┌───────────┐
│  Phone   │ ─────────────► │  ESP32 A  │ ──────────────► │           │
│  (PWA)   │                └───────────┘                 │           │
│          │  BLE adverts   ┌───────────┐  MQTT publish   │ Mosquitto │
│ broadcasts ────────────► │  ESP32 B  │ ──────────────► │  Broker   │
│  UUID    │                └───────────┘                 │ port 1883 │
│          │  BLE adverts   ┌───────────┐  MQTT publish   │           │
│          │ ─────────────► │  ESP32 C  │ ──────────────► │           │
└──────────┘                └───────────┘                 └─────┬─────┘
     │                                                          │
     │  WebSocket (IMU data)                     MQTT subscribe │
     │                                                          │
     ▼                                                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend (:8000)                      │
│                                                                     │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────────────────┐  │
│  │ MQTT Client │───►│  BLE Buffer  │───►│ BLE Trilateration      │  │
│  │ (aiomqtt)   │    │ {session_id: │    │ RSSI → distance → (x,y)│  │
│  └─────────────┘    │  {gw: rssi}} │    └───────────┬────────────┘  │
│                     └──────────────┘                │               │
│  ┌─────────────┐                                    ▼               │
│  │ WebSocket   │──► IMU heading + steps ──► ┌──────────────┐       │
│  │ /ws/track/  │                             │ Kalman Filter │       │
│  │  {session}  │◄── fused (x, y, accuracy)◄─│ PDR + BLE    │       │
│  └─────────────┘                             └──────────────┘       │
└─────────────────────────────────────────────────────────────────────┘
```

**Key idea:** Each ESP32 acts as a **BLE gateway/anchor** at a known position. When a user's phone walks nearby, each ESP32 picks up the phone's BLE advertisement and measures the **RSSI** (signal strength). The ESP32 publishes this RSSI to an MQTT broker. The backend subscribes to the MQTT topic, collects readings from ≥3 gateways, and trilaterates the user's position.

---

## Network Setup — ESP32 to Desktop via WiFi

The ESP32 boards communicate with the Mosquitto MQTT broker (running on your desktop/laptop) over **WiFi**. All devices must be on the **same local network**.

### Network Diagram

```
                           WiFi Router
                          ┌───────────┐
               WiFi       │           │       WiFi / Ethernet
   ESP32 A  ◄───────────►│  192.168  │◄──────────────►  Your Desktop
   ESP32 B  ◄───────────►│   .1.x    │                  (Backend server +
   ESP32 C  ◄───────────►│  network  │                   Mosquitto broker)
                          └───────────┘                  e.g. 192.168.1.100
```

### Step-by-step

#### 1. Find your desktop's LAN IP

```bash
# Linux
hostname -I | awk '{print $1}'

# macOS
ipconfig getifaddr en0

# Windows (PowerShell)
(Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "Wi-Fi").IPAddress
```

This returns something like `192.168.1.100` — this is the address the ESP32s will connect to.

#### 2. Configure Mosquitto to listen on all interfaces

By default, Mosquitto 2.x only listens on `127.0.0.1` (localhost). The ESP32s need it to listen on `0.0.0.0` (all network interfaces):

Edit `/etc/mosquitto/conf.d/local.conf`:

```
listener 1883 0.0.0.0
allow_anonymous true
```

Then restart:

```bash
sudo systemctl restart mosquitto
```

#### 3. Open the firewall (if needed)

```bash
# UFW (Ubuntu)
sudo ufw allow 1883/tcp

# firewalld (Fedora/RHEL)
sudo firewall-cmd --add-port=1883/tcp --permanent && sudo firewall-cmd --reload

# Windows — open port 1883 in Windows Defender Firewall
```

#### 4. Set the desktop IP in the ESP32 firmware

In `esp32_gateway/esp32_gateway.ino`, update:

```cpp
#define WIFI_SSID    "YourWiFiName"         // ← Same network as desktop
#define WIFI_PASS    "YourWiFiPassword"
#define MQTT_HOST    "192.168.1.100"        // ← Your desktop's LAN IP from step 1
#define MQTT_PORT    1883
```

#### 5. Verify connectivity from ESP32

After flashing and powering on, the ESP32 Serial Monitor should show:

```
Connecting to WiFi... connected!
192.168.1.42                          ← ESP32's own IP
MQTT connecting… connected!           ← Successfully reached your desktop
Scan complete – 2 devices found
Published: {"gateway_id":"esp32_A","session_id":"phone-123","rssi":-68}
```

#### 6. Verify on the desktop

```bash
mosquitto_sub -t "ire/ble/rssi" -v
```

You should see messages arriving from the ESP32s over WiFi:

```
ire/ble/rssi {"gateway_id":"esp32_A","session_id":"phone-123","rssi":-68}
```

### Important Notes

- **Static IP recommended**: If your desktop's IP changes (DHCP), the ESP32s will lose connection. Either assign a static IP to your desktop or use mDNS (`.local` hostnames).
- **Same subnet**: The ESP32s and desktop must be on the same subnet (e.g. both on `192.168.1.x`). Guest networks or AP isolation will block the connection.
- **Latency**: WiFi MQTT communication adds ~1–5 ms latency, which is negligible for our use case (human walking speed).

---

## Data Flow

1. **Phone** broadcasts BLE advertisements with a known service UUID.
2. **ESP32 gateways** (≥3, at known positions) scan for that UUID and measure RSSI.
3. Each ESP32 **publishes** a JSON message to the MQTT broker on topic `ire/ble/rssi`.
4. The **backend MQTT listener** receives the message and stores RSSI in an in-memory buffer keyed by `session_id`.
5. When the phone sends an **IMU message via WebSocket**, the backend checks the BLE buffer:
   - If ≥3 gateway readings exist → **trilateration** (log-distance path-loss model + least-squares).
   - The result is fused with IMU/PDR data via a **Kalman filter**.
6. The **fused position** `(x, y, accuracy)` is sent back to the phone over the WebSocket.

---

## MQTT Topic & Payload Format

| Field | Value |
|-------|-------|
| **Broker** | `localhost:1883` (or your server IP) |
| **Topic** | `ire/ble/rssi` |
| **QoS** | 0 (fire-and-forget, low latency) |
| **Payload** | JSON (see below) |

### JSON Payload

```json
{
  "gateway_id": "esp32_A",
  "session_id": "phone-uuid-xyz",
  "rssi": -67
}
```

| Key | Type | Description |
|-----|------|-------------|
| `gateway_id` | `string` | Unique identifier for this ESP32 (e.g. `esp32_A`, `esp32_B`, `esp32_C`). Must match the keys in the backend's `GATEWAY_POSITIONS` config. |
| `session_id` | `string` | Identifies the user's phone. Extracted from the BLE device name or manufacturer data. Must be consistent across all gateways for the same user. |
| `rssi` | `number` | Received Signal Strength Indicator in dBm (e.g. `-67`). Negative integer, typically between `-30` (very close) and `-100` (far away). |

---

## Hardware Requirements

| Item | Qty | Notes |
|------|-----|-------|
| ESP32 dev board (e.g. ESP32-WROOM-32) | ≥ 3 | One per anchor point |
| Micro-USB cable | ≥ 3 | For power (and initial flashing) |
| USB power adapter (5V/1A) | ≥ 3 | For deployment |
| WiFi network | 1 | ESP32s and backend must be on the same network |
| Mosquitto MQTT broker | 1 | Runs on the backend server |

---

## ESP32 Firmware Setup

### 1. Install Arduino IDE & Board Support

1. Install [Arduino IDE](https://www.arduino.cc/en/software) (2.x recommended).
2. Go to **File → Preferences → Additional Board Manager URLs** and add:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. Go to **Tools → Board → Board Manager**, search for **esp32**, and install **esp32 by Espressif Systems**.

### 2. Install PubSubClient Library

1. Go to **Sketch → Include Library → Manage Libraries**.
2. Search for **PubSubClient** (by Nick O'Leary) and install it.

### 3. Flash the Firmware

The firmware is in `esp32_gateway/esp32_gateway.ino`. Before flashing, **edit the configuration block** at the top of the file:

```cpp
// ── CONFIGURATION ───────────────────────────────────
#define GATEWAY_ID   "esp32_A"          // ← Change per board: esp32_A, esp32_B, esp32_C
#define WIFI_SSID    "STORE_WIFI"       // ← Your WiFi network name
#define WIFI_PASS    "store_password"   // ← Your WiFi password
#define MQTT_HOST    "192.168.1.100"    // ← IP of the machine running the backend
#define MQTT_PORT    1883
#define MQTT_TOPIC   "ire/ble/rssi"
#define SCAN_TIME    2                  // BLE scan window in seconds
```

**Flash each ESP32 with a different `GATEWAY_ID`:**

| Board | `GATEWAY_ID` | Physical Position |
|-------|-------------|-------------------|
| Board 1 | `"esp32_A"` | Store origin (0, 0) m |
| Board 2 | `"esp32_B"` | (10, 0) m |
| Board 3 | `"esp32_C"` | (5, 8) m |

### 4. How the Firmware Works

```
loop():
  1. Connect/reconnect to WiFi and MQTT broker
  2. Start BLE scan for SCAN_TIME seconds
  3. For each discovered BLE device:
     a. Check if it advertises TARGET_SERVICE_UUID
     b. If yes → read RSSI and device name (used as session_id)
     c. Build JSON payload: {"gateway_id":"esp32_A","session_id":"...","rssi":-67}
     d. Publish to MQTT topic "ire/ble/rssi"
  4. Clear scan results, short delay, repeat
```

The phone's PWA needs to broadcast a BLE advertisement with the service UUID `12345678-1234-1234-1234-123456789abc` (defined in `TARGET_SERVICE_UUID`). The device name or manufacturer data should encode the user's `session_id`.

---

## Mosquitto Broker Setup

### Install (Ubuntu/Debian)

```bash
sudo apt-get install -y mosquitto mosquitto-clients
```

### Configure for Anonymous Local Access

Create `/etc/mosquitto/conf.d/local.conf`:

```
listener 1883
allow_anonymous true
```

Restart:

```bash
sudo systemctl restart mosquitto
```

### Verify

```bash
# Terminal 1 – subscribe
mosquitto_sub -t "ire/ble/rssi" -v

# Terminal 2 – publish a test message
mosquitto_pub -t "ire/ble/rssi" -m '{"gateway_id":"esp32_A","session_id":"test-phone","rssi":-65}'
```

You should see the message appear in Terminal 1.

### Remote Access (for ESP32s on the network)

If the ESP32s are on a different machine than the broker, ensure:
- Port **1883** is open in the firewall.
- The `MQTT_HOST` in the ESP32 firmware points to the broker's LAN IP.

---

## Backend MQTT Listener

The backend automatically subscribes to `ire/ble/rssi` on startup. The relevant code:

### Configuration (`backend/app/core/config.py`)

```python
MQTT_BROKER_HOST = "localhost"    # Change if broker is on another machine
MQTT_BROKER_PORT = 1883
MQTT_TOPIC_BLE   = "ire/ble/rssi"

# Gateway positions (x, y) in metres – MUST match GATEWAY_ID values
GATEWAY_POSITIONS = {
    "esp32_A": (0.0, 0.0),
    "esp32_B": (10.0, 0.0),
    "esp32_C": (5.0, 8.0),
}
```

### MQTT Listener (`backend/app/services/mqtt_client.py`)

- Runs as a **background asyncio task** started during FastAPI lifespan.
- Subscribes to `ire/ble/rssi`.
- Parses each JSON message and stores it in an **in-memory buffer**: `{ session_id: { gateway_id: rssi } }`.
- Auto-reconnects if the broker goes down (5-second retry loop).

### Trilateration (`backend/app/services/ble_trilateration.py`)

When a WebSocket message arrives and ≥3 gateway readings exist in the BLE buffer for that session:

1. **RSSI → distance** using the log-distance path-loss model:
   ```
   distance = 10 ^ ((TX_POWER - RSSI) / (10 × n))
   ```
   where `TX_POWER = -59 dBm` and `n = 2.7` (indoor path-loss exponent).

2. **Trilateration** via `scipy.optimize.least_squares` with `soft_l1` loss (robust to outliers).

3. Result is passed to the **Kalman filter** for fusion with IMU/PDR data.

---

## Gateway Placement & Configuration

### Minimum Requirements

- **≥3 gateways** are needed for 2D trilateration.
- Gateways should **not** be collinear (avoid placing all on one wall).

### Recommended Layout

```
  (0,10)──────────────────────────(12,10)
  │                                    │
  │          C (5, 8)                  │
  │            ▲                       │
  │           / \                      │
  │          /   \                     │
  │         /     \                    │
  │        /       \                   │
  │       /   STORE  \                 │
  │      /             \               │
  │     /               \              │
  │    ▼                 ▼             │
  │  A (0, 0)      B (10, 0)          │
  (0,0)────────────────────────(12,0)
```

### Adding More Gateways

To add a 4th (or more) gateway:

1. Flash a new ESP32 with a unique `GATEWAY_ID` (e.g. `"esp32_D"`).
2. Add its position to `backend/app/core/config.py`:
   ```python
   GATEWAY_POSITIONS = {
       "esp32_A": (0.0, 0.0),
       "esp32_B": (10.0, 0.0),
       "esp32_C": (5.0, 8.0),
       "esp32_D": (12.0, 5.0),   # ← new gateway
   }
   ```
3. Restart the backend. No other code changes needed — trilateration automatically uses all available gateways.

---

## Calibration

The accuracy of positioning depends on two parameters in `config.py`:

| Parameter | Default | Description | How to Calibrate |
|-----------|---------|-------------|------------------|
| `BLE_TX_POWER` | `-59` | Expected RSSI (dBm) at 1 metre distance | Place phone exactly 1 m from an ESP32, record average RSSI over 30 s |
| `BLE_PATH_LOSS_EXP` | `2.7` | Indoor path-loss exponent (n) | Measure RSSI at known distances (1m, 3m, 5m, 8m), fit the log-distance model |

### Quick Calibration Procedure

1. Place the phone at exactly **1 metre** from one ESP32.
2. Subscribe to MQTT and collect ~30 readings:
   ```bash
   mosquitto_sub -t "ire/ble/rssi" -C 30 | jq '.rssi'
   ```
3. Average those RSSI values → that's your `BLE_TX_POWER`.
4. Repeat at 3 m, 5 m, and 8 m.
5. Fit the model: `RSSI = TX_POWER - 10 * n * log10(distance)` → solve for `n`.

Typical values:
- **Open space:** n ≈ 2.0–2.5
- **Indoor with shelves:** n ≈ 2.5–3.5
- **Heavy obstacles:** n ≈ 3.5–4.5

---

## Testing with the Simulator

You don't need physical ESP32s to test the full pipeline. The simulator can run in **MQTT mode**, publishing RSSI messages to the broker just like real ESP32s:

```bash
# Start the MQTT broker (if not already running)
sudo systemctl start mosquitto

# Start the backend
cd backend && source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# In another terminal – run the simulator in MQTT mode
cd /path/to/AmI_project
source backend/venv/bin/activate
python simulator/simulator.py --mqtt --speed 0.5
```

What happens:
- The simulator publishes RSSI to `ire/ble/rssi` via MQTT (simulates 3 ESP32s).
- The simulator also opens a WebSocket to `/ws/track/{session_id}` (simulates the phone sending IMU).
- The backend receives RSSI from MQTT, IMU from WebSocket, trilaterates, fuses, and returns the position.
- A CSV log is saved to `backend/logs/tracking_<session>_<timestamp>.csv`.

### Monitor MQTT Traffic

```bash
# Watch all messages on the BLE topic
mosquitto_sub -t "ire/ble/rssi" -v
```

Example output:
```
ire/ble/rssi {"gateway_id": "esp32_A", "session_id": "sim-1234", "rssi": -72}
ire/ble/rssi {"gateway_id": "esp32_B", "session_id": "sim-1234", "rssi": -81}
ire/ble/rssi {"gateway_id": "esp32_C", "session_id": "sim-1234", "rssi": -65}
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Backend log: `MQTT connection lost ([Errno 111] Connection refused)` | Mosquitto broker not running | `sudo systemctl start mosquitto` |
| ESP32 Serial: `MQTT connecting… failed (rc=-2)` | Wrong `MQTT_HOST` IP or broker not reachable | Check IP, ensure port 1883 is open |
| ESP32 Serial: `Scan complete – 0 devices found` | Phone not advertising BLE, or wrong UUID | Verify phone BLE is on; check `TARGET_SERVICE_UUID` matches |
| Trilateration returns `None` | Fewer than 3 gateways reporting for the session | Ensure all 3 ESP32s are running and the `session_id` is consistent |
| Position accuracy > 3 m | Poor calibration or gateway placement | Re-calibrate `BLE_TX_POWER` and `BLE_PATH_LOSS_EXP`; improve gateway geometry |
| CSV log missing RSSI columns | MQTT messages arriving after IMU processed | This is normal for the first 1–2 steps; RSSI appears once buffer fills |

### Useful Commands

```bash
# Check if Mosquitto is running
sudo systemctl status mosquitto

# View Mosquitto logs
sudo tail -f /var/log/mosquitto/mosquitto.log

# Test publish/subscribe
mosquitto_sub -t "ire/ble/rssi" -v &
mosquitto_pub -t "ire/ble/rssi" -m '{"gateway_id":"esp32_A","session_id":"test","rssi":-70}'

# Check backend BLE buffer (via API docs)
open http://localhost:8000/docs
```
