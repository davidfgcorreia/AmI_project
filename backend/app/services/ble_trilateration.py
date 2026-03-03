"""
BLE Trilateration Service
─────────────────────────
Converts RSSI readings from 3+ ESP32 gateways into (x, y) coordinates
using log-distance path-loss model + least-squares trilateration.
"""
import math
import numpy as np
from scipy.optimize import least_squares
from ..core.config import (
    GATEWAY_POSITIONS, BLE_TX_POWER, BLE_PATH_LOSS_EXP,
)


def rssi_to_distance(rssi: float, tx_power: float = BLE_TX_POWER,
                     n: float = BLE_PATH_LOSS_EXP) -> float:
    """Log-distance path-loss model: d = 10^((TxPower - RSSI) / (10·n))"""
    if rssi >= 0:
        return 0.1  # clamp invalid readings
    return 10 ** ((tx_power - rssi) / (10 * n))


def _residuals(point: np.ndarray,
               gateways: list[tuple[float, float]],
               distances: list[float]) -> np.ndarray:
    """Residual function for least-squares optimisation."""
    x, y = point
    res = []
    for (gx, gy), d in zip(gateways, distances):
        estimated = math.sqrt((x - gx) ** 2 + (y - gy) ** 2)
        res.append(estimated - d)
    return np.array(res)


def trilaterate(readings: dict[str, float]) -> tuple[float, float] | None:
    """
    Trilaterate user position from BLE RSSI readings.

    Parameters
    ----------
    readings : dict
        {gateway_id: rssi_value}  – requires ≥ 3 gateways.

    Returns
    -------
    (x, y) in metres or None if insufficient data.
    """
    gateways: list[tuple[float, float]] = []
    distances: list[float] = []

    for gw_id, rssi in readings.items():
        pos = GATEWAY_POSITIONS.get(gw_id)
        if pos is None:
            continue
        gateways.append(pos)
        distances.append(rssi_to_distance(rssi))

    if len(gateways) < 3:
        return None

    # Initial guess: centroid of gateways
    x0 = np.mean([g[0] for g in gateways])
    y0 = np.mean([g[1] for g in gateways])

    result = least_squares(
        _residuals, x0=np.array([x0, y0]),
        args=(gateways, distances),
        loss="soft_l1",        # robust to outlier readings
    )

    if result.success:
        return float(result.x[0]), float(result.x[1])
    return None
