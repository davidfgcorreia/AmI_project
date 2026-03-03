"""
IMU / PDR + Kalman Filter Sensor Fusion
───────────────────────────────────────
Fuses BLE-derived absolute position with IMU-based Pedestrian Dead Reckoning
(PDR) to achieve smooth, sub-metre tracking in noisy retail environments.

State vector: [x, y, vx, vy]
"""
import math
import numpy as np
from ..core.config import KALMAN_PROCESS_NOISE, KALMAN_MEASUREMENT_NOISE

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

    def update_ble(self, ble_x: float, ble_y: float):
        """Correction step using BLE trilateration measurement."""
        if not self._initialised:
            self.x[0] = ble_x
            self.x[1] = ble_y
            self._initialised = True
            return

        z = np.array([ble_x, ble_y])
        y = z - self.H @ self.x                   # innovation
        S = self.H @ self.P @ self.H.T + self.R   # innovation covariance
        K = self.P @ self.H.T @ np.linalg.inv(S)  # Kalman gain

        self.x = self.x + K @ y
        I = np.eye(4)
        self.P = (I - K @ self.H) @ self.P

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
    return _trackers[session_id]


def remove_tracker(session_id: str):
    _trackers.pop(session_id, None)
