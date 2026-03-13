"""
Runtime gateway manager — holds mutable gateway positions and
manages WebSocket subscribers so the server can push updates
to connected frontends.
"""
import asyncio
import logging
from typing import Dict, Set, Any

from fastapi import WebSocket

from ..core import config

logger = logging.getLogger("gateway_manager")

# In-memory positions (mutable)
_positions: Dict[str, tuple[float, float]] = {k: (float(v[0]), float(v[1])) for k, v in config.GATEWAY_POSITIONS.items()}

# Active WebSocket connections subscribed to gateway updates
_subs: Set[WebSocket] = set()


def get_positions() -> list[Dict[str, Any]]:
    return [{"id": k, "x": float(v[0]), "y": float(v[1])} for k, v in _positions.items()]


def set_positions(new: Dict[str, tuple[float, float]]):
    """Replace positions and schedule a broadcast to subscribers."""
    global _positions
    _positions = {k: (float(v[0]), float(v[1])) for k, v in new.items()}
    logger.info("[GM] Gateway positions updated: %s", _positions)
    # schedule broadcast
    asyncio.create_task(broadcast_positions())


async def register(ws: WebSocket):
    await ws.accept()
    _subs.add(ws)
    logger.info("[GM] WS subscriber added (total=%d)", len(_subs))
    # send initial positions
    await ws.send_json({"type": "gateways", "items": get_positions()})


async def unregister(ws: WebSocket):
    _subs.discard(ws)
    try:
        await ws.close()
    except Exception:
        pass
    logger.info("[GM] WS subscriber removed (total=%d)", len(_subs))


async def broadcast_positions():
    """Send current positions to all subscribed websockets.

    Remove dead connections automatically.
    """
    if not _subs:
        return
    items = get_positions()
    payload = {"type": "gateways", "items": items}
    to_remove = []
    for ws in list(_subs):
        try:
            await ws.send_json(payload)
        except Exception as exc:
            logger.warning("[GM] Failed to send to subscriber, removing: %s", exc)
            to_remove.append(ws)
    for ws in to_remove:
        _subs.discard(ws)
