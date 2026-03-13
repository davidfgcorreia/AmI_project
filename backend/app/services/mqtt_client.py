"""
MQTT listener – subscribes to ESP32 BLE RSSI data and feeds the
localisation pipeline.

This implementation prefers the system `mosquitto_sub` client (reads
JSON lines from stdout). If `mosquitto_sub` is not available it falls
back to `aiomqtt`.
"""
import asyncio
import json
import logging
import shutil

logger = logging.getLogger("mqtt")

# In-memory store of latest RSSI per session
# { session_id: { gateway_id: rssi } }
_ble_buffer: dict[str, dict[str, float]] = {}


def get_ble_buffer() -> dict[str, dict[str, float]]:
    return _ble_buffer


async def mqtt_listener():
    """Background task that listens to MQTT for BLE RSSI messages.

    Expected JSON payload on topic `MQTT_TOPIC_BLE`:
    { "gateway_id": "esp32_A", "session_id": "phone-uuid", "rssi": -67 }
    """
    from ..core.config import MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_TOPIC_BLE

    mosquitto_sub = shutil.which("mosquitto_sub")

    # Hard-coded session filter (only process messages for this session id)
    allowed_session = 'A32 de David'
    logger.info("MQTT session filter active: %s", allowed_session)

    if mosquitto_sub:
        cmd = [mosquitto_sub, "-h", MQTT_BROKER_HOST, "-p", str(MQTT_BROKER_PORT), "-t", MQTT_TOPIC_BLE]
        logger.info("Using mosquitto_sub for MQTT: %s", " ".join(cmd))

        while True:
            proc = None
            try:
                proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

                if proc.stdout is None:
                    logger.warning("mosquitto_sub started without stdout; retrying")
                    await asyncio.sleep(2)
                    continue

                # Read lines from mosquitto_sub stdout
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
                        logger.debug("Failed to parse mosquitto_sub line: %s", text)
                        continue

                    gw = payload.get("gateway_id")
                    sid = payload.get("session_id")
                    try:
                        rssi = float(payload.get("rssi"))
                    except (TypeError, ValueError):
                        logger.debug("Invalid rssi in payload: %s", payload)
                        continue

                    if sid is None or gw is None:
                        logger.debug("Bad MQTT payload from mosquitto_sub: %s", payload)
                        continue

                    # Session filtering
                    if allowed_session and sid != allowed_session:
                        logger.debug("Ignoring session %s (filter=%s)", sid, allowed_session)
                        continue

                    if sid not in _ble_buffer:
                        _ble_buffer[sid] = {}
                        logger.info("[MQTT] 🆕 New session via mosquitto_sub: %s", sid)
                    _ble_buffer[sid][gw] = rssi
                    logger.info("[MQTT] 📡 gw=%s  session=%s  rssi=%+.1f dBm", gw, sid, rssi)

                # Process exited — capture stderr if available
                if proc.stderr is not None:
                    try:
                        stderr = await proc.stderr.read()
                        if stderr:
                            logger.warning("mosquitto_sub exited, stderr=%s", stderr.decode(errors="ignore").strip()[:200])
                    except Exception:
                        logger.debug("Failed to read mosquitto_sub stderr")

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
                # ensure subprocess is cleaned up
                if proc is not None and proc.returncode is None:
                    try:
                        proc.kill()
                    except Exception:
                        pass

            await asyncio.sleep(2)

    logger.warning("mosquitto_sub not available — MQTT listener disabled. Install mosquitto-clients to enable.")
    return
