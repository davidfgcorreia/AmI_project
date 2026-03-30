"""
Core configuration - environment variables and constants.
"""
import os
from pathlib import Path

# ── Paths ──
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "app" / "static"
PROJECT_ROOT = BASE_DIR.parent.parent
SUPERMARKET_JSON = PROJECT_ROOT / "supermarket.json"

# ── MQTT ──
MQTT_BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = 1883
MQTT_TOPIC_BLE = "ire/ble/rssi"          # ESP32 publishes here

# ── BLE gateway positions (x, y) in metres from store origin ──
# Adjust to real deployment positions
GATEWAY_POSITIONS = {
    "esp32_A": (8, 2.5),   # centre-bottom
    "esp32_B": (4.5, 2),  # top-right
    "esp32_C": (0.5, 2.5),   # top-left
    # NOTE: B and C share y=4.5 — Y-resolution near the top wall is reduced.
    # If placement can be adjusted, move one gateway to a different Y for a
    # better-conditioned triangle.
}

# Measured: -50 dBm at ~0.5 m, -70 dBm at 1 m, then ~5 dBm/m beyond 1 m
BLE_TX_POWER = -75         # RSSI at 1 m (dBm)
BLE_PATH_LOSS_EXP = 2.9    # kept for fallback; not used by primary model
BLE_NEAR_RSSI = -75     # RSSI threshold between near/far field (= RSSI at 1 m)
BLE_NEAR_DIST_AT_REF = 0.3  # measured distance (m) at RSSI = -50 dBm
BLE_FAR_DBM_PER_M = 8.0    # measured: ~5 dBm loss per metre beyond 1 m

# ── Kalman filter process / measurement noise ──
# Process noise *per second* (scaled by dt in predict).
# Controls how fast uncertainty grows between BLE corrections.
# Lower = trust PDR longer; higher = trust BLE sooner.
KALMAN_PROCESS_NOISE = 0.2
# Base BLE measurement noise (variance in metres^2).
# Dynamically scaled by signal strength in kalman_fusion.py.
# Higher = smoother but slower to correct; lower = more reactive but jumpier.
KALMAN_MEASUREMENT_NOISE = 1.5

# Degrees added to compass heading to align with store Y-axis.
# Calibrate: walk along +Y (away from entrance), read compass heading, set offset
# so that heading + offset = 0.  E.g. if walking +Y reads 90 on compass, set -90.
HEADING_OFFSET = -286

# ── Navigation ──
STORE_WIDTH = 10        # metres  (must match FloorMap.jsx STORE_W)
STORE_HEIGHT = 5        # metres  (must match FloorMap.jsx STORE_H)
GRID_RESOLUTION = 0.5      # metres per grid cell


# ── Database ──
DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR / 'store.db'}"
