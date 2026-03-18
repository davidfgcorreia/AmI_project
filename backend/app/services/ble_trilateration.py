"""
BLE Trilateration Service
─────────────────────────
Converts RSSI readings from 3+ ESP32 gateways into (x, y) coordinates.

Uses a fast analytical Weighted Linear Least-Squares (WLLS) approach
instead of iterative optimisation: linearises the circle equations by
pairwise subtraction, then solves the resulting overdetermined system
with numpy.linalg.lstsq.  Typically 100-200× faster than scipy.
"""
import math
import logging
import numpy as np
from ..core.config import (
    GATEWAY_POSITIONS, BLE_TX_POWER, BLE_PATH_LOSS_EXP,
    BLE_NEAR_RSSI, BLE_NEAR_DIST_AT_REF, BLE_FAR_DBM_PER_M,
)

logger = logging.getLogger("ble")


def rssi_to_distance(rssi: float) -> float:
    """
    Two-segment model calibrated from measurements:
      Near field (RSSI > BLE_NEAR_RSSI, i.e. < 1 m):
        Linear: -50 dBm → 0.5 m,  -70 dBm → 1.0 m
      Far field  (RSSI ≤ BLE_NEAR_RSSI, i.e. ≥ 1 m):
        Linear: d = 1 + (BLE_TX_POWER − rssi) / BLE_FAR_DBM_PER_M
    """
    if rssi >= 0:
        return 0.1
    if rssi > BLE_NEAR_RSSI:
        slope = (BLE_NEAR_DIST_AT_REF - 1.0) / (-50 - BLE_NEAR_RSSI)
        return max(0.1, 1.0 + (rssi - BLE_NEAR_RSSI) * slope)
    return 1.0 + (BLE_TX_POWER - rssi) / BLE_FAR_DBM_PER_M


def trilaterate(readings: dict[str, float]) -> tuple[float, float] | None:
    """
    Trilaterate user position from BLE RSSI readings (≥ 3 gateways).

    Algorithm — Weighted Linear Least Squares:
      Subtracting gateway-1's circle equation from gateway-i's yields a
      linear equation in (x, y).  Weighting each equation by signal
      strength makes closer gateways dominate the fit (they have smaller
      RSSI variance because the signal can only be attenuated, not
      amplified).

    Returns (x, y) in metres, or None if insufficient data.
    """
    gateways: list[tuple[float, float]] = []
    distances: list[float] = []
    weights: list[float] = []

    for gw_id, rssi in readings.items():
        pos = GATEWAY_POSITIONS.get(gw_id)
        if pos is None:
            continue
        gateways.append(pos)
        distances.append(rssi_to_distance(rssi))
        # Amplitude ratio relative to 1-m reference — strong signal → high weight
        weights.append(max(0.05, 10 ** ((rssi - BLE_TX_POWER) / 20)))

    if len(gateways) < 3:
        logger.warning("[BLE-TRI] Only %d known gateways (need ≥3)", len(gateways))
        return None

    # Build linear system by subtracting the first circle equation from each other.
    # (x−x1)²+(y−y1)²=r1²  minus  (x−xi)²+(y−yi)²=ri²  →
    #   2(xi−x1)·x + 2(yi−y1)·y = r1²−ri² + xi²−x1² + yi²−y1²
    x1, y1 = gateways[0]
    r1      = distances[0]
    w1      = weights[0]

    A_rows, b_rows = [], []
    for i in range(1, len(gateways)):
        xi, yi = gateways[i]
        ri, wi = distances[i], weights[i]
        w_row = math.sqrt(w1 * wi)           # geometric-mean weight for this pair
        A_rows.append([2 * w_row * (xi - x1),
                        2 * w_row * (yi - y1)])
        b_rows.append(w_row * (r1**2 - ri**2 + xi**2 - x1**2 + yi**2 - y1**2))

    A = np.array(A_rows, dtype=float)
    b = np.array(b_rows, dtype=float)

    result, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
    x_out, y_out = float(result[0]), float(result[1])

    logger.debug("[BLE-TRI] → (%.2f, %.2f)  weights=%s",
                 x_out, y_out, [f"{w:.2f}" for w in weights])
    return x_out, y_out
