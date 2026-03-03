"""
Core configuration – environment variables and constants.
"""
from pathlib import Path

# ── Paths ──
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "app" / "static"
SHELF_IMG_DIR = STATIC_DIR / "shelf_images"

# ── MQTT ──
MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883
MQTT_TOPIC_BLE = "ire/ble/rssi"          # ESP32 publishes here

# ── BLE gateway positions (x, y) in metres from store origin ──
# Adjust to real deployment positions
GATEWAY_POSITIONS = {
    "esp32_A": (0.0, 0.0),
    "esp32_B": (10.0, 0.0),
    "esp32_C": (5.0, 8.0),
}

# ── Trilateration tuning ──
BLE_TX_POWER = -59          # RSSI at 1 m (dBm) – calibrate per beacon
BLE_PATH_LOSS_EXP = 2.7    # n – indoor path-loss exponent

# ── Kalman filter process / measurement noise ──
KALMAN_PROCESS_NOISE = 0.05
KALMAN_MEASUREMENT_NOISE = 2.0

# ── Navigation ──
STORE_WIDTH = 12.0          # metres
STORE_HEIGHT = 10.0         # metres
GRID_RESOLUTION = 0.25      # metres per grid cell

# ── YOLO ──
YOLO_MODEL_PATH = str(BASE_DIR / "yolov8n.pt")   # will auto-download
YOLO_CONFIDENCE = 0.35

# ── Database ──
DATABASE_URL = f"sqlite+aiosqlite:///{BASE_DIR / 'store.db'}"
