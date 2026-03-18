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
    return np.array([
        w * (math.sqrt((x - gx)**2 + (y - gy)**2) - d)
        for (gx, gy), d, w in zip(gateways, distances, weights)
    ])


_AGE_DECAY_TAU = 2.5  # seconds; weight halves ~every 1.7 s of staleness


def trilaterate(
    readings: dict[str, float],
    ages: dict[str, float] | None = None,
) -> tuple[float, float, float] | None:
    """
    Trilaterate user position from BLE RSSI readings (≥ 3 gateways).

    ages: optional {gateway_id: seconds_since_last_reading}.
          Fresher readings get higher weight via exponential decay.

    Returns (x, y, accuracy_m) clamped to store bounds, or None on failure.
    accuracy_m is the RMS of unweighted distance residuals — a rough estimate
    of how well the circles intersect at the solution point.
    """
    gateways, distances, weights = [], [], []

    for gw_id, rssi in readings.items():
        pos = GATEWAY_POSITIONS.get(gw_id)
        if pos is None:
            continue
        gateways.append(pos)
        distances.append(rssi_to_distance(rssi))
        # Amplitude ratio: stronger signal → higher weight.
        signal_w = max(0.05, 10 ** ((rssi - BLE_TX_POWER) / 20))
        # Time decay: penalise stale readings exponentially.
        age = ages.get(gw_id, 0.0) if ages else 0.0
        time_w = math.exp(-age / _AGE_DECAY_TAU)
        weights.append(signal_w * time_w)

    if len(gateways) < 3:
        return None

    x0 = np.mean([g[0] for g in gateways])
    y0 = np.mean([g[1] for g in gateways])

    try:
        result = least_squares(
            _residuals, x0=[x0, y0],
            args=(gateways, distances, weights),
            loss="soft_l1",
            bounds=([0, 0], [STORE_WIDTH, STORE_HEIGHT]),
        )
    except Exception as e:
        logger.warning("[BLE-TRI] least_squares failed: %s", e)
        return None

    x_out, y_out = float(result.x[0]), float(result.x[1])

    if not math.isfinite(x_out) or not math.isfinite(y_out):
        logger.warning("[BLE-TRI] Non-finite result, discarding")
        return None

    # Unweighted RMS residual: average circle-fit error in metres
    raw_residuals = [
        math.sqrt((x_out - gx)**2 + (y_out - gy)**2) - d
        for (gx, gy), d in zip(gateways, distances)
    ]
    accuracy_m = round(math.sqrt(sum(r**2 for r in raw_residuals) / len(raw_residuals)), 2)

    logger.debug("[BLE-TRI] → (%.2f, %.2f)  accuracy=%.2fm", x_out, y_out, accuracy_m)
    return x_out, y_out, accuracy_m
