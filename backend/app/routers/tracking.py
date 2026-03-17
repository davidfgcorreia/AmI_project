"""
WebSocket endpoint for real-time position tracking.

Client sends IMU data → server fuses with BLE from MQTT → broadcasts position.
"""
import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.ble_trilateration import trilaterate
from ..services.kalman_fusion import get_tracker, remove_tracker
from ..services.mqtt_client import get_ble_buffer
from ..services.csv_logger import get_csv_logger, close_csv_logger
from ..models.schemas import BLEReading

router = APIRouter()
logger = logging.getLogger("ws")

# Active WebSocket connections per session
_connections: dict[str, WebSocket] = {}


def get_connections():
    return _connections


@router.websocket("/ws/track/{session_id}")
async def tracking_ws(ws: WebSocket, session_id: str):
    """
    Real-time tracking WebSocket.

    Client → Server (JSON):
    {
        "type": "imu",
        "heading": 45.0,
        "steps": 2,
        "accel_x": 0.1, "accel_y": -0.3, "accel_z": 9.8,
        "gyro_alpha": 0.0, "gyro_beta": 0.0, "gyro_gamma": 0.0
    }

    Server → Client (JSON):
    {
        "type": "position",
        "x": 5.2,
        "y": 3.8,
        "accuracy": 0.9
    }
    """
    await ws.accept()
    _connections[session_id] = ws
    tracker = get_tracker(session_id)
    csv_log = get_csv_logger(session_id)
    logger.info("[WS] ✔ Connected: session=%s  (active sessions: %d)", session_id, len(_connections))

    msg_count = 0
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("[WS] ⚠ Bad JSON from %s: %s", session_id, raw[:80])
                continue

            msg_count += 1
            msg_type = data.get("type", "imu")

            if msg_type == "imu":
                heading = data.get("heading", 0.0)
                steps = data.get("steps", 0)
                tracker.predict_pdr(heading, steps, dt=0.2)
                csv_log.record_imu(heading, steps)
                if steps > 0:
                    logger.info("[WS] 📱 IMU  session=%s  heading=%.1f°  steps=%d", session_id, heading, steps)

            # Also check the BLE buffer (populated by MQTT listener or HTTP)
            ble_readings = get_ble_buffer().get(session_id)
            if ble_readings and len(ble_readings) >= 3:
                rssi_str = "  ".join(f"{gw}={rssi:+.0f}dBm" for gw, rssi in ble_readings.items())
                logger.info("[WS] 📡 BLE  session=%s  %s", session_id, rssi_str)
                csv_log.record_ble(ble_readings)

                ble_pos = trilaterate(ble_readings)
                if ble_pos:
                    logger.info("[WS] 📐 Trilateration → (%.2f, %.2f)", ble_pos[0], ble_pos[1])
                    csv_log.record_trilateration(ble_pos[0], ble_pos[1])
                    tracker.update_ble(*ble_pos)
                else:
                    logger.warning("[WS] ⚠ Trilateration failed for session=%s", session_id)
                    csv_log.record_trilateration(None, None)

            # Send fused position back
            x, y = tracker.position
            accuracy = round(tracker.accuracy, 2)
            csv_log.record_fused(x, y, accuracy)
            await ws.send_json({
                "type": "position",
                "x": round(x, 2),
                "y": round(y, 2),
                "accuracy": accuracy,
            })

            # Log fused position every 5 messages to avoid spam
            if msg_count % 5 == 0:
                logger.info("[WS] 📍 Fused position  session=%s  (%.2f, %.2f) ±%.2fm  [msg #%d]",
                            session_id, x, y, accuracy, msg_count)

    except WebSocketDisconnect:
        logger.info("[WS] ✖ Disconnected: session=%s  (processed %d messages)", session_id, msg_count)
    except Exception as exc:
        logger.error("[WS] ✖ Error session=%s: %s", session_id, exc)
    finally:
        _connections.pop(session_id, None)
        close_csv_logger(session_id, instance=csv_log)
        remove_tracker(session_id)


# ── REST endpoint for BLE readings (used by simulator / ESP32 HTTP fallback) ──

@router.get("/api/ble/buffer")
async def get_ble_buffer_debug():
    """Debug endpoint – shows current BLE buffer state."""
    return get_ble_buffer()


@router.post("/api/ble/reading")
async def post_ble_reading(reading: BLEReading):
    """
    Accept a BLE RSSI reading via HTTP.

    Used by the simulator in HTTP mode, or as a fallback when
    ESP32 gateways post directly instead of using MQTT.
    """
    buf = get_ble_buffer()
    is_new = reading.session_id not in buf
    if is_new:
        buf[reading.session_id] = {}
        logger.info("[BLE] 🆕 New session detected: %s", reading.session_id)
    buf[reading.session_id][reading.gateway_id] = reading.rssi
    logger.info("[BLE] 📡 Reading  gw=%s  session=%s  rssi=%+.1f dBm",
                reading.gateway_id, reading.session_id, reading.rssi)

    # Push updated position to active WebSocket connection (e.g. frontend on desktop)
    ble_readings = buf[reading.session_id]
    if len(ble_readings) >= 3:
        ws = _connections.get(reading.session_id)
        if ws:
            ble_pos = trilaterate(ble_readings)
            if ble_pos:
                tracker = get_tracker(reading.session_id)
                tracker.update_ble(*ble_pos)
                x, y = tracker.position
                try:
                    await ws.send_json({
                        "type": "position",
                        "x": round(x, 2),
                        "y": round(y, 2),
                        "accuracy": round(tracker.accuracy, 2),
                    })
                except Exception:
                    pass

    return {"status": "ok"}
