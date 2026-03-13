"""Gateways router — WebSocket for live pushes and admin REST update."""
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Body

from ..services.gateway_manager import register as gm_register, unregister as gm_unregister, set_positions as gm_set_positions
from ..services.gateway_manager import get_positions as gm_get_positions

logger = logging.getLogger("gateways")

router = APIRouter()


@router.websocket("/ws/gateways")
async def gateways_ws(ws: WebSocket):
    """WebSocket endpoint clients subscribe to for gateway updates."""
    await gm_register(ws)
    try:
        while True:
            # keep the connection open; clients shouldn't need to send data
            data = await ws.receive_text()
            # optionally support simple pings
            if data.strip().lower() in ("ping", "hello"):
                await ws.send_text("pong")
    except WebSocketDisconnect:
        await gm_unregister(ws)
    except Exception as exc:
        logger.error("[WS] Error in gateways_ws: %s", exc)
        await gm_unregister(ws)


@router.post("/api/gateways")
async def update_gateways(payload: dict = Body(...)):
    """Admin endpoint to update gateway positions and broadcast changes.

    Expected payload format:
    { "esp32_A": [0.0, 0.0], "esp32_B": [10.0, 0.0], ... }
    """
    try:
        gm_set_positions(payload)
        return {"status": "ok"}
    except Exception as exc:
        logger.error("Failed to update gateways: %s", exc)
        return {"status": "error", "message": str(exc)}
