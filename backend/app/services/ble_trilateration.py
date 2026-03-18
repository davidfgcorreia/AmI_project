"""
BLE Trilateration Service
─────────────────────────
Converts RSSI readings from 3+ ESP32 gateways into (x, y) coordinates
using a weighted nonlinear least-squares fit of the circle equations.

The nonlinear formulation (vs a linearised one) is essential here because
the three gateway positions are near-collinear, making the linearised
system ill-conditioned.  scipy soft_l1 loss also handles RSSI outliers.
"""
import math
import logging
import numpy as np
from scipy.optimize import least_squares
from ..core.config import (
    GATEWAY_POSITIONS, BLE_TX_POWER,
    BLE_NEAR_RSSI, BLE_NEAR_DIST_AT_REF, BLE_FAR_DBM_PER_M,
    STORE_WIDTH, STORE_HEIGHT,
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
        slope = (BLE_NEAR_DIST_AT_REF - 1.0) / (-50.0 - BLE_NEAR_RSSI)
        return max(0.1, 1.0 + (rssi - BLE_NEAR_RSSI) * slope)
    return 1.0 + (BLE_TX_POWER - rssi) / BLE_FAR_DBM_PER_M


def _residuals(point, gateways, distances, weights):
    x, y = point
    return [
        w * (math.sqrt((x - gx)**2 + (y - gy)**2) - d)
        for (gx, gy), d, w in zip(gateways, distances, weights)
    ]


def trilaterate(readings: dict[str, float]) -> tuple[float, float] | None:
    """
    Trilaterate user position from BLE RSSI readings (≥ 3 gateways).
    Returns (x, y) clamped to store bounds, or None on failure.
    """
    gateways, distances, weights = [], [], []

    for gw_id, rssi in readings.items():
        pos = GATEWAY_POSITIONS.get(gw_id)
        if pos is None:
            continue
        gateways.append(pos)
        distances.append(rssi_to_distance(rssi))
        # Strong signal → high weight (signal can only be attenuated, not amplified)
        weights.append(max(0.05, 10 ** ((rssi - BLE_TX_POWER) / 20)))

    if len(gateways) < 3:
        return None

    x0 = np.mean([g[0] for g in gateways])
    y0 = np.mean([g[1] for g in gateways])

    try:
        result = least_squares(
            _residuals, x0=[x0, y0],
            args=(gateways, distances, weights),
            loss="soft_l1",
            bounds=([0, 0], [STORE_WIDTH, STORE_HEIGHT]),  # clamp to room
        )
    except Exception as e:
        logger.warning("[BLE-TRI] least_squares failed: %s", e)
        return None

    x_out, y_out = float(result.x[0]), float(result.x[1])

    if not math.isfinite(x_out) or not math.isfinite(y_out):
        logger.warning("[BLE-TRI] Non-finite result, discarding")
        return None

    logger.debug("[BLE-TRI] → (%.2f, %.2f)  cost=%.4f", x_out, y_out, result.cost)
    return x_out, y_out
