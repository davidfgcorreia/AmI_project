"""
CSV Data Logger
───────────────
Writes every tracking data point (RSSI, IMU, trilateration, fused position)
to a CSV file for offline analysis.

Files are saved to  backend/logs/tracking_<session>_<timestamp>.csv
"""
import csv
import logging
import os
from datetime import datetime
from pathlib import Path
from threading import Lock

logger = logging.getLogger("csv_log")

LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Column order
COLUMNS = [
    "timestamp",
    "session_id",
    "step",
    # RSSI (one column per gateway)
    "rssi_esp32_A",
    "rssi_esp32_B",
    "rssi_esp32_C",
    # IMU
    "imu_heading_deg",
    "imu_steps",
    # Trilateration result
    "trilat_x",
    "trilat_y",
    "trilat_cost",
    # Kalman fused position
    "fused_x",
    "fused_y",
    "fused_accuracy",
]


class SessionCSVLogger:
    """Manages one CSV file per tracking session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filepath = LOGS_DIR / f"tracking_{session_id}_{ts}.csv"
        self._lock = Lock()
        self._file = open(self.filepath, "w", newline="")
        self._writer = csv.DictWriter(self._file, fieldnames=COLUMNS)
        self._writer.writeheader()
        self._file.flush()
        self._step = 0
        # Accumulate partial data until a full row is ready
        self._pending: dict[str, object] = {}
        logger.info("[CSV] 📄 Opened log file: %s", self.filepath)

    def record_ble(self, readings: dict[str, float]):
        """Store latest RSSI readings (will be merged into next row)."""
        for gw_id, rssi in readings.items():
            col = f"rssi_{gw_id}"
            if col in COLUMNS:
                self._pending[col] = round(rssi, 1)

    def record_imu(self, heading: float, steps: int):
        """Store IMU data (will be merged into next row)."""
        self._pending["imu_heading_deg"] = round(heading, 1)
        self._pending["imu_steps"] = steps

    def record_trilateration(self, x: float | None, y: float | None,
                             cost: float | None = None):
        """Store trilateration result."""
        self._pending["trilat_x"] = round(x, 3) if x is not None else ""
        self._pending["trilat_y"] = round(y, 3) if y is not None else ""
        self._pending["trilat_cost"] = round(cost, 4) if cost is not None else ""

    def record_fused(self, x: float, y: float, accuracy: float):
        """Store Kalman fused position and flush the row."""
        self._step += 1
        row: dict[str, object] = {
            "timestamp": datetime.now().isoformat(timespec="milliseconds"),
            "session_id": self.session_id,
            "step": self._step,
        }
        # Merge accumulated partial data
        for col in COLUMNS:
            if col not in row:
                row[col] = self._pending.get(col, "")

        row["fused_x"] = round(x, 3)
        row["fused_y"] = round(y, 3)
        row["fused_accuracy"] = round(accuracy, 3)

        with self._lock:
            self._writer.writerow(row)
            self._file.flush()

        # Reset pending for next step
        self._pending.clear()

    def close(self):
        with self._lock:
            self._file.close()
        logger.info("[CSV] 📄 Closed log (%d rows): %s", self._step, self.filepath)


# ── Session management ──
_loggers: dict[str, SessionCSVLogger] = {}


def get_csv_logger(session_id: str) -> SessionCSVLogger:
    if session_id not in _loggers:
        _loggers[session_id] = SessionCSVLogger(session_id)
    return _loggers[session_id]


def close_csv_logger(session_id: str):
    csv_log = _loggers.pop(session_id, None)
    if csv_log:
        csv_log.close()
