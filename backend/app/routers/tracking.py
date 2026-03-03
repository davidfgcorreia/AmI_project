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
    logger.info("WS connected: %s", session_id)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "imu")

            if msg_type == "imu":
                heading = data.get("heading", 0.0)
                steps = data.get("steps", 0)
                tracker.predict_pdr(heading, steps, dt=0.2)

            # Also check the BLE buffer (populated by MQTT listener)
            ble_readings = get_ble_buffer().get(session_id)
            if ble_readings and len(ble_readings) >= 3:
                ble_pos = trilaterate(ble_readings)
                if ble_pos:
                    tracker.update_ble(*ble_pos)

            # Send fused position back
            x, y = tracker.position
            await ws.send_json({
                "type": "position",
                "x": round(x, 2),
                "y": round(y, 2),
                "accuracy": round(tracker.accuracy, 2),
            })

    except WebSocketDisconnect:
        logger.info("WS disconnected: %s", session_id)
    except Exception as exc:
        logger.error("WS error %s: %s", session_id, exc)
    finally:
        _connections.pop(session_id, None)
        remove_tracker(session_id)
