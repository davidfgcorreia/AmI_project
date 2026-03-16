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
    "esp32_A": (2.0, 3.5),
    "esp32_B": (3.0, 3.5),
    "esp32_C": (3, 5),
}

# ── Trilateration tuning ──
BLE_TX_POWER = -59          # RSSI at 1 m (dBm) - calibrate per beacon
BLE_PATH_LOSS_EXP = 2.7    # n - indoor path-loss exponent

# ── Kalman filter process / measurement noise ──
KALMAN_PROCESS_NOISE = 0.05
KALMAN_MEASUREMENT_NOISE = 2.0

# ── Navigation ──
STORE_WIDTH = 12.0        # metres  (must match FloorMap.jsx STORE_W)
STORE_HEIGHT = 10.0       # metres  (must match FloorMap.jsx STORE_H)
GRID_RESOLUTION = 0.25      # metres per grid cell


# ── Database ──
DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR / 'store.db'}"
