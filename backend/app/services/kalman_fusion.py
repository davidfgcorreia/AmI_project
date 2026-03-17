"""
IMU / PDR + Kalman Filter Sensor Fusion
───────────────────────────────────────
Fuses BLE-derived absolute position with IMU-based Pedestrian Dead Reckoning
(PDR) to achieve smooth, sub-metre tracking in noisy retail environments.

State vector: [x, y, vx, vy]
"""
import math
import logging
import numpy as np
from ..core.config import KALMAN_PROCESS_NOISE, KALMAN_MEASUREMENT_NOISE, BLE_TX_POWER

logger = logging.getLogger("kalman")

# Average human step length (m)
STEP_LENGTH = 0.65


class KalmanTracker:
    """
    Extended Kalman-style tracker.

    • Predict step uses IMU heading + step count (PDR).
    • Update step corrects with BLE trilateration.
    """

    def __init__(self):
        # State: [x, y, vx, vy]
        self.x = np.zeros(4)
        # Covariance
        self.P = np.eye(4) * 10.0
        # Process noise
        q = KALMAN_PROCESS_NOISE
        self.Q = np.diag([q, q, q * 2, q * 2])
        # Measurement noise (BLE is noisy)
        r = KALMAN_MEASUREMENT_NOISE
        self.R = np.diag([r, r])
        # Observation matrix: we only measure [x, y]
        self.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
        ], dtype=float)
        self._initialised = False

    def predict_pdr(self, heading_deg: float, steps: int, dt: float = 0.1):
        """
        Predict new position using PDR (heading from gyroscope + step count).
        heading_deg: compass heading (0=North, 90=East).
        """
        if steps <= 0:
            return

        rad = math.radians(heading_deg)
        dx = STEP_LENGTH * steps * math.sin(rad)
        dy = STEP_LENGTH * steps * math.cos(rad)
        vx = dx / max(dt, 0.01)
        vy = dy / max(dt, 0.01)

        # State transition (constant-velocity)
        F = np.eye(4)
        F[0, 2] = dt
        F[1, 3] = dt

        # Update velocity component with PDR estimate
        self.x[2] = vx
        self.x[3] = vy

        self.x = F @ self.x
        self.P = F @ self.P @ F.T + self.Q
        logger.debug("[KALMAN] PDR predict  heading=%.1f°  steps=%d  dx=%.2f dy=%.2f → (%.2f, %.2f)",
                     heading_deg, steps, dx, dy, self.x[0], self.x[1])

    def update_ble(self, ble_x: float, ble_y: float, best_rssi: float | None = None):
        """
        Correction step using BLE trilateration measurement.

        best_rssi: strongest (least negative) RSSI seen in this scan.
            Used to scale measurement noise — a strong reading means we're
            definitely close to an ESP so BLE is reliable; a weak reading
            means we may be far or obstructed so we trust BLE less.
        """
        if not self._initialised:
            self.x[0] = ble_x
            self.x[1] = ble_y
            self._initialised = True
            logger.info("[KALMAN] 🆕 Initialised at (%.2f, %.2f)", ble_x, ble_y)
            return

        # Dynamic R: scales with signal strength.
        # At best_rssi == BLE_TX_POWER (-70 dBm, i.e. 1 m) → r = base noise.
        # At best_rssi == -45 dBm (very close) → r ≈ 0.18 × base (trust BLE a lot).
        # At best_rssi == -90 dBm (far / blocked) → r ≈ 3.2 × base (trust BLE less).
        if best_rssi is not None:
            r = KALMAN_MEASUREMENT_NOISE * 10 ** ((BLE_TX_POWER - best_rssi) / 20)
            r = max(0.15, min(4.0, r))
        else:
            r = KALMAN_MEASUREMENT_NOISE
        R = np.diag([r, r])

        z = np.array([ble_x, ble_y])
        y = z - self.H @ self.x                 # innovation
        S = self.H @ self.P @ self.H.T + R      # innovation covariance
        K = self.P @ self.H.T @ np.linalg.inv(S)  # Kalman gain

        self.x = self.x + K @ y
        I = np.eye(4)
        self.P = (I - K @ self.H) @ self.P
        logger.info("[KALMAN] BLE update  meas=(%.2f, %.2f)  innov=(%.2f, %.2f) → fused=(%.2f, %.2f)  r=%.2f  acc=%.2fm",
                    ble_x, ble_y, float(y[0]), float(y[1]), self.x[0], self.x[1], r, self.accuracy)

    @property
    def position(self) -> tuple[float, float]:
        return float(self.x[0]), float(self.x[1])

    @property
    def accuracy(self) -> float:
        """Estimated accuracy from covariance."""
        return float(math.sqrt(self.P[0, 0] + self.P[1, 1]))


# ── Session management ──
_trackers: dict[str, KalmanTracker] = {}


def get_tracker(session_id: str) -> KalmanTracker:
    if session_id not in _trackers:
        _trackers[session_id] = KalmanTracker()
        logger.info("[KALMAN] ➕ New tracker for session=%s  (total=%d)", session_id, len(_trackers))
    return _trackers[session_id]


def remove_tracker(session_id: str):
    removed = _trackers.pop(session_id, None)
    if removed:
        logger.info("[KALMAN] ➖ Removed tracker for session=%s  (remaining=%d)", session_id, len(_trackers))
