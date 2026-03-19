"""
WebSocket endpoint for real-time position tracking.

Kalman-fused mode: BLE trilateration corrects, IMU/PDR predicts between corrections.

Two-task architecture with a shared stop_event:
  recv_loop  — receives IMU frames, runs Kalman predict (PDR); sets stop_event on disconnect.
  push_loop  — at 10 Hz pulls fresh BLE data, runs Kalman update, pushes fused position.
"""
import asyncio
import json
import logging
import time

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

PUSH_INTERVAL    = 0.1   # seconds  ->  10 Hz push rate
HEARTBEAT_EVERY  = 5.0   # seconds between keepalive pings when no position


def get_connections():
    return _connections


@router.websocket("/ws/track/{session_id}")
async def tracking_ws(ws: WebSocket, session_id: str):
    await ws.accept()
    _connections[session_id] = ws
    session_manager.create_or_update(session_id)
    csv_log = get_csv_logger(session_id)
    tracker = get_tracker(session_id)
    logger.info("[WS] Connected  session=%s", session_id)

    stop_event = asyncio.Event()

    # -- recv loop: receive IMU data, run Kalman predict (PDR) ----------------
    async def recv_loop():
        try:
            async for raw in ws.iter_text():
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if data.get("type") == "imu":
                    heading = float(data.get("heading", 0.0))
                    steps = int(data.get("steps", 0))
                    dt = float(data.get("dt", 0.2))
                    csv_log.record_imu(heading, steps)

                    if tracker._initialised:
                        tracker.predict_pdr(heading, steps, dt)
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.debug("[WS] recv_loop exception session=%s: %s", session_id, exc)
        finally:
            stop_event.set()

    # -- push loop: BLE update + push fused position at 10 Hz -----------------
    async def push_loop():
        last_heartbeat = time.monotonic()
        try:
            while not stop_event.is_set():
                await asyncio.sleep(PUSH_INTERVAL)
                if stop_event.is_set():
                    break

                # Check for fresh BLE readings and run Kalman update
                fresh = get_fresh_readings(session_id)
                if fresh:
                    readings, ages = fresh
                    csv_log.record_ble(readings)
                    log_ble_reading(session_id, readings)
                    result = trilaterate(readings, ages)
                    if result:
                        ble_x, ble_y, ble_acc = result
                        csv_log.record_trilateration(ble_x, ble_y)
                        best_rssi = max(readings.values()) if readings else None
                        tracker.update_ble(ble_x, ble_y, best_rssi)

                # Push current Kalman state if initialised
                if tracker._initialised:
                    x, y = tracker.position
                    acc = round(tracker.accuracy, 2)
                    csv_log.record_fused(x, y, acc)
                    await ws.send_json({
                        "type":     "position",
                        "x":        round(x, 2),
                        "y":        round(y, 2),
                        "accuracy": acc,
                    })
                    last_heartbeat = time.monotonic()
                else:
                    now = time.monotonic()
                    if now - last_heartbeat >= HEARTBEAT_EVERY:
                        await ws.send_json({"type": "heartbeat"})
                        last_heartbeat = now

        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.debug("[WS] push_loop exception session=%s: %s", session_id, exc)
        finally:
            stop_event.set()

    recv_task = asyncio.create_task(recv_loop())
    push_task = asyncio.create_task(push_loop())

    await stop_event.wait()

    recv_task.cancel()
    push_task.cancel()
    await asyncio.gather(recv_task, push_task, return_exceptions=True)

    _connections.pop(session_id, None)
    remove_tracker(session_id)
    close_csv_logger(session_id, instance=csv_log)
    logger.info("[WS] Cleaned up  session=%s", session_id)


# -- REST endpoints -----------------------------------------------------------

@router.get("/api/sessions")
async def get_sessions():
    return session_manager.get_all()


@router.get("/api/ble/buffer")
async def get_ble_buffer_debug():
    return get_ble_buffer()


@router.get("/api/ble/log")
async def get_ble_log(n: int = 500):
    """Last *n* BLE RSSI readings -- suitable for time-series graphs."""
    return read_recent(n)


@router.post("/api/ble/reading")
async def post_ble_reading(reading: BLEReading):
    """Accept a BLE RSSI reading via HTTP (simulator / ESP32 HTTP fallback)."""
    update_ble_reading(reading.session_id, reading.gateway_id, reading.rssi)
    logger.info("[BLE] gw=%s  session=%s  rssi=%+.1f dBm",
                reading.gateway_id, reading.session_id, reading.rssi)

    # Immediately push updated position to any connected WebSocket
    fresh = get_fresh_readings(reading.session_id)
    if fresh:
        readings, ages = fresh
        log_ble_reading(reading.session_id, readings)
        ws = _connections.get(reading.session_id)
        if ws:
            result = trilaterate(readings, ages)
            if result:
                ble_x, ble_y, ble_acc = result
                tracker = get_tracker(reading.session_id)
                best_rssi = max(readings.values()) if readings else None
                tracker.update_ble(ble_x, ble_y, best_rssi)
                x, y = tracker.position
                try:
                    await ws.send_json({
                        "type":     "position",
                        "x":        round(x, 2),
                        "y":        round(y, 2),
                        "accuracy": round(tracker.accuracy, 2),
                    })
                except Exception:
                    pass

    return {"status": "ok"}
