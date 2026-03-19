"""
IMU / PDR + Kalman Filter Sensor Fusion
----------------------------------------
Fuses BLE-derived absolute position with IMU-based Pedestrian Dead Reckoning
(PDR) to achieve smooth, sub-metre tracking in noisy retail environments.

State vector: [x, y, vx, vy]

Predict: set velocity from PDR, propagate state with F, grow P by Q*dt.
Update:  BLE trilateration corrects position; R scaled by signal strength.
"""
import math
import logging
import numpy as np
from ..core.config import (
    KALMAN_PROCESS_NOISE, KALMAN_MEASUREMENT_NOISE, BLE_TX_POWER,
    STORE_WIDTH, STORE_HEIGHT, HEADING_OFFSET,
)

logger = logging.getLogger("kalman")

STEP_LENGTH = 0.65  # average human step length (m)

# Caps to prevent covariance explosion when BLE is absent for a long time
_P_POS_MAX = 8.0
_P_VEL_MAX = 4.0


class KalmanTracker:
    def __init__(self):
        self.x = np.zeros(4)           # [x, y, vx, vy]
        self.P = np.eye(4) * 10.0      # large — shrinks on first BLE update

        q = KALMAN_PROCESS_NOISE
        self.Q_base = np.diag([q, q, q * 4, q * 4])

        self.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
        ], dtype=float)

        self._initialised = False

    # -- predict ---------------------------------------------------------------

    def predict_pdr(self, heading_deg: float, steps: int, dt: float = 0.1):
        """
        Predict using PDR: set velocity from step displacement, then propagate
        with constant-velocity transition F.  F @ x gives x += vx*dt.
        """
        dt = max(dt, 0.01)

        F = np.eye(4)
        F[0, 2] = dt
        F[1, 3] = dt

        dx, dy = 0.0, 0.0
        if steps > 0:
            rad = math.radians(heading_deg + HEADING_OFFSET)
            dx = STEP_LENGTH * steps * math.sin(rad)
            dy = STEP_LENGTH * steps * math.cos(rad)
            self.x[2] = dx / dt
            self.x[3] = dy / dt
        else:
            self.x[2] *= 0.8
            self.x[3] *= 0.8

        # Propagate state and covariance consistently through F
        self.x = F @ self.x
        self.P = F @ self.P @ F.T + self.Q_base * dt
        self._cap_and_clamp()

        logger.debug("[KALMAN] PDR  h=%.0f steps=%d dx=%.2f dy=%.2f -> (%.2f,%.2f) P=%.2f",
                     heading_deg, steps, dx, dy, self.x[0], self.x[1], self.P[0, 0])

    # -- update ----------------------------------------------------------------

    def update_ble(self, ble_x: float, ble_y: float, best_rssi: float | None = None):
        """
        Correction step using BLE trilateration.
        Dynamic R: strong signal -> low noise (trust BLE); weak -> high noise (trust PDR).
        """
        if not self._initialised:
            self.x[0] = ble_x
            self.x[1] = ble_y
            # Reasonable initial uncertainty (not 10.0 which causes P explosion)
            self.P = np.diag([1.0, 1.0, 1.0, 1.0])
            self._initialised = True
            logger.info("[KALMAN] Init at (%.2f, %.2f)", ble_x, ble_y)
            return

        if best_rssi is not None:
            r = KALMAN_MEASUREMENT_NOISE * 10 ** ((BLE_TX_POWER - best_rssi) / 20)
            r = max(0.3, min(6.0, r))
        else:
            r = KALMAN_MEASUREMENT_NOISE
        R = np.diag([r, r])

        z = np.array([ble_x, ble_y])
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + R
        K = self.P @ self.H.T @ np.linalg.inv(S)

        self.x = self.x + K @ y
        self.P = (np.eye(4) - K @ self.H) @ self.P
        self._cap_and_clamp()

        logger.info("[KALMAN] BLE  meas=(%.2f,%.2f) innov=(%.2f,%.2f) K=%.2f -> (%.2f,%.2f) r=%.2f acc=%.2fm",
                    ble_x, ble_y, float(y[0]), float(y[1]),
                    float(K[0, 0]), self.x[0], self.x[1], r, self.accuracy)

    # -- helpers ---------------------------------------------------------------

    def _cap_and_clamp(self):
        """Clamp position to store, cap covariance to prevent explosion."""
        self.x[0] = max(0, min(STORE_WIDTH, self.x[0]))
        self.x[1] = max(0, min(STORE_HEIGHT, self.x[1]))
        self.P[0, 0] = min(self.P[0, 0], _P_POS_MAX)
        self.P[1, 1] = min(self.P[1, 1], _P_POS_MAX)
        self.P[2, 2] = min(self.P[2, 2], _P_VEL_MAX)
        self.P[3, 3] = min(self.P[3, 3], _P_VEL_MAX)

    @property
    def position(self) -> tuple[float, float]:
        return float(self.x[0]), float(self.x[1])

    @property
    def accuracy(self) -> float:
        return float(math.sqrt(self.P[0, 0] + self.P[1, 1]))


# -- session management -------------------------------------------------------
_trackers: dict[str, KalmanTracker] = {}


def get_tracker(session_id: str) -> KalmanTracker:
    if session_id not in _trackers:
        _trackers[session_id] = KalmanTracker()
        logger.info("[KALMAN] New tracker session=%s (total=%d)", session_id, len(_trackers))
    return _trackers[session_id]


def remove_tracker(session_id: str):
    removed = _trackers.pop(session_id, None)
    if removed:
        logger.info("[KALMAN] Removed tracker session=%s (remaining=%d)", session_id, len(_trackers))
