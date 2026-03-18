"""
Session manager – tracks BLE-discovered device sessions.

A session is created automatically the first time the backend receives
a BLE RSSI reading (via MQTT from an ESP32 gateway) for a given session_id.
Sessions are in-memory only and do not persist across restarts.
"""
import time
from typing import Optional

# session_id -> {created_at: float, last_seen: float}
_sessions: dict[str, dict] = {}


def create_or_update(session_id: str) -> None:
    """Register a session or update its last-seen timestamp."""
    now = time.time()
    if session_id not in _sessions:
        _sessions[session_id] = {"created_at": now, "last_seen": now}
    else:
        _sessions[session_id]["last_seen"] = now


def get_all() -> dict[str, dict]:
    return _sessions


def get_most_recent() -> Optional[str]:
    """Return the session ID seen most recently, or None if no sessions exist."""
    if not _sessions:
        return None
    return max(_sessions, key=lambda sid: _sessions[sid]["last_seen"])
