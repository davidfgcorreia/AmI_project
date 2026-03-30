"""
MQTT listener - subscribes to ESP32 BLE RSSI data and feeds the
localisation pipeline.

This implementation prefers the system `mosquitto_sub` client (reads
JSON lines from stdout). If `mosquitto_sub` is not available it falls
back to `aiomqtt`.
"""
import asyncio
import json
import logging
import shutil
import time

logger = logging.getLogger("mqtt")

# In-memory store of latest smoothed RSSI per session + arrival timestamps
# { session_id: { gateway_id: rssi } }
_ble_buffer: dict[str, dict[str, float]] = {}
# { session_id: { gateway_id: monotonic_timestamp } }
_ble_timestamps: dict[str, dict[str, float]] = {}

# EMA smoothing factor: 0=never update, 1=no smoothing.
# 0.65 leans toward responsiveness; lower if the marker jitters too much.
_EMA_ALPHA = 0.62

# Readings older than this are ignored for trilateration.
_MAX_AGE_S = 4.0


def get_ble_buffer() -> dict[str, dict[str, float]]:
    return _ble_buffer


def update_ble_reading(session_id: str, gateway_id: str, rssi: float):
    """
    Record one RSSI reading with EMA smoothing and a fresh timestamp.
    Called by both the MQTT listener and the HTTP endpoint.
    """
    from ..services import session_manager

    if session_id not in _ble_buffer:
        _ble_buffer[session_id] = {}
        _ble_timestamps[session_id] = {}
        logger.info("[MQTT] New session: %s", session_id)

    old = _ble_buffer[session_id].get(gateway_id)
    smoothed = rssi if old is None else _EMA_ALPHA * rssi + (1 - _EMA_ALPHA) * old
    _ble_buffer[session_id][gateway_id] = smoothed
    _ble_timestamps[session_id][gateway_id] = time.monotonic()
    session_manager.create_or_update(session_id)


def get_fresh_readings(
    session_id: str, max_age: float = _MAX_AGE_S
) -> tuple[dict[str, float], dict[str, float]] | None:
    """
    Return ({gateway_id: rssi}, {gateway_id: age_seconds}) for gateways
    whose last reading arrived within *max_age* seconds.
    Returns None if fewer than 3 are fresh.
    """
    buf = _ble_buffer.get(session_id)
    ts  = _ble_timestamps.get(session_id)
    if not buf or not ts:
        return None
    now = time.monotonic()
    fresh = {gw: rssi for gw, rssi in buf.items() if now - ts.get(gw, 0) <= max_age}
    if len(fresh) < 3:
        return None
    ages = {gw: now - ts[gw] for gw in fresh}
    return fresh, ages


async def mqtt_listener():
    """Background task that listens to MQTT for BLE RSSI messages.

    Expected JSON payload on topic `MQTT_TOPIC_BLE`:
    { "gateway_id": "esp32_A", "session_id": "IRE-xxxxxxxx", "rssi": -67 }
    """
    from ..core.config import MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_TOPIC_BLE

    mosquitto_sub = shutil.which("mosquitto_sub")

    if mosquitto_sub:
        cmd = [mosquitto_sub, "-h", MQTT_BROKER_HOST, "-p", str(MQTT_BROKER_PORT), "-t", MQTT_TOPIC_BLE]
        logger.info("Using mosquitto_sub for MQTT: %s", " ".join(cmd))

        while True:
            proc = None
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                if proc.stdout is None:
                    logger.warning("mosquitto_sub started without stdout; retrying")
                    await asyncio.sleep(2)
                    continue

                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    text = line.decode(errors="ignore").strip()
                    if not text:
                        continue
                    try:
                        payload = json.loads(text)
                    except json.JSONDecodeError:
                        logger.debug("Failed to parse: %s", text)
                        continue

                    gw  = payload.get("gateway_id")
                    sid = payload.get("session_id")
                    try:
                        rssi = float(payload.get("rssi"))
                    except (TypeError, ValueError):
                        continue
                    if sid is None or gw is None:
                        continue
                    # Only accept readings from our app (session names start with "IRE-")
                    if not sid.startswith("IRE-"):
                        continue

                    update_ble_reading(sid, gw, rssi)
                    logger.info("[MQTT] gw=%s  session=%s  rssi=%+.1f dBm", gw, sid, rssi)

                if proc.stderr is not None:
                    try:
                        stderr = await proc.stderr.read()
                        if stderr:
                            logger.warning("mosquitto_sub exited: %s",
                                           stderr.decode(errors="ignore").strip()[:200])
                    except Exception:
                        pass

            except asyncio.CancelledError:
                if proc is not None:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                raise
            except Exception as exc:
                logger.warning("mosquitto_sub error: %s", exc)
            finally:
                if proc is not None and proc.returncode is None:
                    try:
                        proc.kill()
                    except Exception:
                        pass

            await asyncio.sleep(2)

    logger.warning("mosquitto_sub not available — MQTT listener disabled.")
