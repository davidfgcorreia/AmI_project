"""
Core configuration - environment variables and constants.
"""
import os
from pathlib import Path

# ── Paths ──
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "app" / "static"
SHELF_IMG_DIR = STATIC_DIR / "shelf_images"
PROJECT_ROOT = BASE_DIR.parent.parent
SUPERMARKET_JSON = PROJECT_ROOT / "supermarket.json"

# ── MQTT ──
MQTT_BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = 1883
MQTT_TOPIC_BLE = "ire/ble/rssi"          # ESP32 publishes here

# ── BLE gateway positions (x, y) in metres from store origin ──
# Adjust to real deployment positions
GATEWAY_POSITIONS = {
    "esp32_A": (5.5, 0.5),   # centre-bottom
    "esp32_B": (10.0, 4.5),  # top-right
    "esp32_C": (1.0, 3),   # top-left
    # NOTE: B and C share y=4.5 — Y-resolution near the top wall is reduced.
    # If placement can be adjusted, move one gateway to a different Y for a
    # better-conditioned triangle.
}

# ── Trilateration tuning ──
# Measured: -50 dBm at ~0.5 m, -70 dBm at 1 m, then ~5 dBm/m beyond 1 m
BLE_TX_POWER = -70          # RSSI at 1 m (dBm)
BLE_PATH_LOSS_EXP = 2.0    # kept for fallback; not used by primary model
BLE_NEAR_RSSI = -70         # RSSI threshold between near/far field (= RSSI at 1 m)
BLE_NEAR_DIST_AT_REF = 0.5  # measured distance (m) at RSSI = -50 dBm
BLE_FAR_DBM_PER_M = 5.0    # measured: ~5 dBm loss per metre beyond 1 m

# ── Kalman filter process / measurement noise ──
KALMAN_PROCESS_NOISE = 1.5   # high = P grows fast between updates → Kalman gain stays healthy
# Base BLE noise at 1 m reference; dynamically scaled by signal strength in kalman_fusion.py
KALMAN_MEASUREMENT_NOISE = 0.5

# ── Navigation ──
STORE_WIDTH = 12.0        # metres  (must match FloorMap.jsx STORE_W)
STORE_HEIGHT = 5.0        # metres  (must match FloorMap.jsx STORE_H)
GRID_RESOLUTION = 0.25      # metres per grid cell


# ── Database ──
DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR / 'store.db'}"
