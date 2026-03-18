"""
Persistent BLE RSSI Logger
──────────────────────────
Appends every complete set of gateway readings to  logs/ble_rssi.csv
regardless of whether a WebSocket session is active.

Exposes read_recent() so the REST API can return data for graph display.
"""
import csv
import logging
from datetime import datetime
from pathlib import Path
from threading import Lock

logger = logging.getLogger("ble_log")

LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

BLE_LOG_PATH = LOGS_DIR / "ble_rssi.csv"

GATEWAYS = ["esp32_A", "esp32_B", "esp32_C"]
COLUMNS = ["timestamp", "session_id"] + [f"rssi_{gw}" for gw in GATEWAYS]

_lock = Lock()


def _ensure_header():
    if not BLE_LOG_PATH.exists():
        with open(BLE_LOG_PATH, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=COLUMNS).writeheader()
        logger.info("[BLE-LOG] Created %s", BLE_LOG_PATH)


def log_ble_reading(session_id: str, readings: dict[str, float]):
    """Append one timestamped row of RSSI values to the persistent log."""
    _ensure_header()
    row: dict[str, object] = {
        "timestamp": datetime.now().isoformat(timespec="milliseconds"),
        "session_id": session_id,
    }
    for gw in GATEWAYS:
        row[f"rssi_{gw}"] = round(readings[gw], 1) if gw in readings else ""

    with _lock:
        with open(BLE_LOG_PATH, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=COLUMNS).writerow(row)


def read_recent(n: int = 500) -> list[dict]:
    """Return the last *n* rows as a list of dicts (most recent last)."""
    if not BLE_LOG_PATH.exists():
        return []
    with _lock:
        with open(BLE_LOG_PATH, "r", newline="") as f:
            rows = list(csv.DictReader(f))
    # Convert RSSI strings to float where present
    result = []
    for r in rows[-n:]:
        row: dict[str, object] = {
            "timestamp": r["timestamp"],
            "session_id": r["session_id"],
        }
        for gw in GATEWAYS:
            val = r.get(f"rssi_{gw}", "")
            row[f"rssi_{gw}"] = float(val) if val != "" else None
        result.append(row)
    return result
