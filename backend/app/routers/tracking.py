"""
WebSocket endpoint for real-time position tracking.

Architecture:
  • recv_loop  — processes IMU messages as they arrive (PDR predict)
  • push_loop  — runs at 10 Hz regardless of IMU; reads fresh BLE data,
                 trilaterates, updates Kalman, and pushes position to client
  This decoupling means position updates are never gated on IMU ticks,
  eliminating the ~30 s startup delay caused by waiting for all gateways
  to appear in the buffer before the first IMU message arrives.
"""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.ble_trilateration import trilaterate
from ..services.kalman_fusion import get_tracker, remove_tracker
from ..services.mqtt_client import get_ble_buffer, get_fresh_readings, update_ble_reading
from ..services.csv_logger import get_csv_logger, close_csv_logger
from ..services.ble_logger import log_ble_reading, read_recent
from ..services import session_manager
from ..models.schemas import BLEReading

router = APIRouter()
logger = logging.getLogger("ws")

_connections: dict[str, WebSocket] = {}

PUSH_INTERVAL = 0.1   # seconds — position pushed to client at up to 10 Hz


def get_connections():
    return _connections


@router.websocket("/ws/track/{session_id}")
async def tracking_ws(ws: WebSocket, session_id: str):
    await ws.accept()
    _connections[session_id] = ws
    session_manager.create_or_update(session_id)
    tracker = get_tracker(session_id)
    csv_log = get_csv_logger(session_id)
    logger.info("[WS] Connected: session=%s", session_id)

    async def recv_loop():
        """Feed IMU messages into the PDR predictor."""
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if data.get("type") == "imu":
                heading = float(data.get("heading", 0.0))
                steps   = int(data.get("steps", 0))
                tracker.predict_pdr(heading, steps, dt=0.2)
                csv_log.record_imu(heading, steps)

    async def push_loop():
        """At 10 Hz: grab fresh BLE readings, trilaterate, update Kalman, push."""
        while True:
            await asyncio.sleep(PUSH_INTERVAL)

            readings = get_fresh_readings(session_id)
            if readings:
                csv_log.record_ble(readings)
                log_ble_reading(session_id, readings)
                pos = trilaterate(readings)
                if pos:
                    csv_log.record_trilateration(*pos)
                    tracker.update_ble(*pos, best_rssi=max(readings.values()))
                else:
                    csv_log.record_trilateration(None, None)

            x, y    = tracker.position
            accuracy = round(tracker.accuracy, 2)
            csv_log.record_fused(x, y, accuracy)
            await ws.send_json({
                "type": "position",
                "x": round(x, 2),
                "y": round(y, 2),
                "accuracy": accuracy,
            })

    recv_task = asyncio.create_task(recv_loop())
    push_task = asyncio.create_task(push_loop())
    try:
        done, pending = await asyncio.wait(
            {recv_task, push_task},
            return_when=asyncio.FIRST_EXCEPTION,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        # Propagate the first real exception (WebSocketDisconnect is normal)
        for task in done:
            exc = task.exception()
            if exc and not isinstance(exc, WebSocketDisconnect):
                logger.error("[WS] Error session=%s: %s", session_id, exc)
    except Exception as exc:
        logger.error("[WS] Outer error session=%s: %s", session_id, exc)
    finally:
        recv_task.cancel()
        push_task.cancel()
        _connections.pop(session_id, None)
        close_csv_logger(session_id, instance=csv_log)
        remove_tracker(session_id)
        logger.info("[WS] Disconnected: session=%s", session_id)


# ── REST endpoints ──────────────────────────────────────────────────────────────

@router.get("/api/sessions")
async def get_sessions():
    return session_manager.get_all()


@router.get("/api/ble/buffer")
async def get_ble_buffer_debug():
    return get_ble_buffer()


@router.get("/api/ble/log")
async def get_ble_log(n: int = 500):
    """Last *n* BLE RSSI readings — suitable for time-series graphs."""
    return read_recent(n)


@router.post("/api/ble/reading")
async def post_ble_reading(reading: BLEReading):
    """Accept a BLE RSSI reading via HTTP (simulator / ESP32 HTTP fallback)."""
    update_ble_reading(reading.session_id, reading.gateway_id, reading.rssi)
    logger.info("[BLE] gw=%s  session=%s  rssi=%+.1f dBm",
                reading.gateway_id, reading.session_id, reading.rssi)

    # If 3 fresh readings exist and a WebSocket is open, push immediately
    # (supplements the push_loop for very fast ESP32 HTTP posting)
    readings = get_fresh_readings(reading.session_id)
    if readings:
        log_ble_reading(reading.session_id, readings)
        ws = _connections.get(reading.session_id)
        if ws:
            pos = trilaterate(readings)
            if pos:
                tracker = get_tracker(reading.session_id)
                tracker.update_ble(*pos, best_rssi=max(readings.values()))
                try:
                    await ws.send_json({
                        "type": "position",
                        "x": round(tracker.position[0], 2),
                        "y": round(tracker.position[1], 2),
                        "accuracy": round(tracker.accuracy, 2),
                    })
                except Exception:
                    pass

    return {"status": "ok"}
