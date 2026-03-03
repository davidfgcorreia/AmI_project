"""
MQTT listener – subscribes to ESP32 BLE RSSI data and feeds the
localisation pipeline.
"""
import asyncio
import json
import logging

logger = logging.getLogger("mqtt")

# In-memory store of latest RSSI per session
# { session_id: { gateway_id: rssi } }
_ble_buffer: dict[str, dict[str, float]] = {}


def get_ble_buffer() -> dict[str, dict[str, float]]:
    return _ble_buffer


async def mqtt_listener():
    """
    Background task that listens to MQTT for BLE RSSI messages from ESP32s.

    Expected MQTT payload (JSON):
    {
        "gateway_id": "esp32_A",
        "session_id": "phone-uuid-xyz",
        "rssi": -67
    }
    """
    from ..core.config import MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_TOPIC_BLE

    try:
        import aiomqtt  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("aiomqtt not installed – MQTT listener disabled")
        return

    while True:
        try:
            async with aiomqtt.Client(
                hostname=MQTT_BROKER_HOST,
                port=MQTT_BROKER_PORT,
            ) as client:
                await client.subscribe(MQTT_TOPIC_BLE)
                logger.info("MQTT connected → subscribed to %s", MQTT_TOPIC_BLE)

                async for message in client.messages:
                    try:
                        payload = json.loads(message.payload.decode())
                        gw = payload["gateway_id"]
                        sid = payload["session_id"]
                        rssi = float(payload["rssi"])

                        if sid not in _ble_buffer:
                            _ble_buffer[sid] = {}
                        _ble_buffer[sid][gw] = rssi

                    except (json.JSONDecodeError, KeyError) as exc:
                        logger.debug("Bad MQTT payload: %s", exc)

        except Exception as exc:
            logger.warning("MQTT connection lost (%s), retrying in 5 s …", exc)
            await asyncio.sleep(5)
