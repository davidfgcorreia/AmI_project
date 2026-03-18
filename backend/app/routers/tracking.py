"""
WebSocket endpoint for real-time position tracking.

BLE-only mode: position = EMA-smoothed trilateration, no Kalman / IMU.

Two-task architecture with a shared stop_event:
  recv_loop  — drains incoming frames so the WS stays healthy; sets stop_event on disconnect.
  push_loop  — at 10 Hz pulls fresh BLE data, trilaterates, smooths, pushes position.

Critically: recv_loop is NEVER cancelled mid-flight.  Cancelling
ws.receive_text() via asyncio.wait_for corrupts Starlette's internal WS
state and causes the connection to silently die.
"""
import asyncio
import json
import logging
import math
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.ble_trilateration import trilaterate
from ..services.mqtt_client import get_ble_buffer, get_fresh_readings, update_ble_reading
from ..services.csv_logger import get_csv_logger, close_csv_logger
from ..services.ble_logger import log_ble_reading, read_recent
from ..services import session_manager
from ..models.schemas import BLEReading

router = APIRouter()
logger = logging.getLogger("ws")

_connections: dict[str, WebSocket] = {}

PUSH_INTERVAL    = 0.1   # seconds  →  10 Hz push rate
POS_ALPHA        = 0.6   # EMA factor: 1=instant/noisy  0=never moves
HEARTBEAT_EVERY  = 5.0   # seconds between keepalive pings when no position


def get_connections():
    return _connections


@router.websocket("/ws/track/{session_id}")
async def tracking_ws(ws: WebSocket, session_id: str):
    await ws.accept()
    _connections[session_id] = ws
    session_manager.create_or_update(session_id)
    csv_log  = get_csv_logger(session_id)
    logger.info("[WS] Connected  session=%s", session_id)

    # Smoothed position + last known accuracy (EMA, BLE-only)
    pos_x:    float | None = None
    pos_y:    float | None = None
    accuracy: float        = 1.5   # metres; updated from trilateration residuals

    stop_event = asyncio.Event()

    # ── recv loop: keep connection healthy, detect client disconnect ──────────
    async def recv_loop():
        nonlocal pos_x, pos_y
        try:
            async for raw in ws.iter_text():
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                # Accept IMU data if the phone ever starts sending it
                if data.get("type") == "imu":
                    csv_log.record_imu(
                        float(data.get("heading", 0.0)),
                        int(data.get("steps", 0)),
                    )
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.debug("[WS] recv_loop exception session=%s: %s", session_id, exc)
        finally:
            stop_event.set()

    # ── push loop: trilaterate + smooth + push at 10 Hz ──────────────────────
    async def push_loop():
        nonlocal pos_x, pos_y
        last_heartbeat = time.monotonic()
        accuracy = 1.5
        try:
            while not stop_event.is_set():
                await asyncio.sleep(PUSH_INTERVAL)
                if stop_event.is_set():
                    break

                fresh = get_fresh_readings(session_id)
                if fresh:
                    readings, ages = fresh
                    csv_log.record_ble(readings)
                    log_ble_reading(session_id, readings)
                    result = trilaterate(readings, ages)
                    if result:
                        new_x, new_y, accuracy = result
                        csv_log.record_trilateration(new_x, new_y)
                        if pos_x is None:
                            pos_x, pos_y = new_x, new_y
                        else:
                            pos_x = POS_ALPHA * new_x + (1 - POS_ALPHA) * pos_x
                            pos_y = POS_ALPHA * new_y + (1 - POS_ALPHA) * pos_y

                if pos_x is None:
                    # No position yet — send heartbeat to keep connection alive
                    now = time.monotonic()
                    if now - last_heartbeat >= HEARTBEAT_EVERY:
                        await ws.send_json({"type": "heartbeat"})
                        last_heartbeat = now
                    continue

                csv_log.record_fused(pos_x, pos_y, accuracy)
                await ws.send_json({
                    "type":     "position",
                    "x":        round(pos_x, 2),
                    "y":        round(pos_y, 2),
                    "accuracy": accuracy,
                })
                last_heartbeat = time.monotonic()
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.debug("[WS] push_loop exception session=%s: %s", session_id, exc)
        finally:
            stop_event.set()

    recv_task = asyncio.create_task(recv_loop())
    push_task = asyncio.create_task(push_loop())

    # Wait until either task signals stop (disconnect or send error)
    await stop_event.wait()

    recv_task.cancel()
    push_task.cancel()
    await asyncio.gather(recv_task, push_task, return_exceptions=True)

    _connections.pop(session_id, None)
    close_csv_logger(session_id, instance=csv_log)
    logger.info("[WS] Cleaned up  session=%s", session_id)


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

    # Immediately push updated position to any connected WebSocket
    fresh = get_fresh_readings(reading.session_id)
    if fresh:
        readings, ages = fresh
        log_ble_reading(reading.session_id, readings)
        ws = _connections.get(reading.session_id)
        if ws:
            result = trilaterate(readings, ages)
            if result:
                rx, ry, racc = result
                try:
                    await ws.send_json({
                        "type":     "position",
                        "x":        round(rx, 2),
                        "y":        round(ry, 2),
                        "accuracy": racc,
                    })
                except Exception:
                    pass

    return {"status": "ok"}
