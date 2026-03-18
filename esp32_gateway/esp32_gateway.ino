/*
 * ESP32 BLE Gateway - Intelligent Retail Ecosystem
 * ─────────────────────────────────────────────────
 * Scans for BLE devices advertising the IRE service UUID,
 * extracts RSSI, and publishes to MQTT broker.
 *
 * The Android app continuously advertises with:
 *   - Service UUID: 6e400001-b5a3-f393-e0a9-e50e24dcca9e
 *   - Device name:  session_id (e.g. "IRE-a3b4c5d6")
 *
 * Session ID priority:
 *   1. BLE advertisement name  (set by the Android app)
 *   2. BLE MAC address         (fallback)
 *
 * Requirements:
 *   - ESP32 board package in Arduino IDE
 *   - PubSubClient library (MQTT)
 *
 * Adjust GATEWAY_ID, WiFi, and MQTT settings below.
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <BLEDevice.h>
#include <BLEScan.h>
#include <BLEAdvertisedDevice.h>

// ── CONFIGURATION ───────────────────────────────────
#define GATEWAY_ID   "esp32_A"          // Unique per gateway (esp32_A / B / C)
#define WIFI_SSID    "TP-Link_9772"     // WiFi SSID
#define WIFI_PASS    "99326685"         // WiFi password
#define MQTT_HOST    "192.168.0.102"    // Backend server IP
#define MQTT_PORT    1883
#define MQTT_TOPIC   "ire/ble/rssi"
#define SCAN_TIME    1                  // BLE scan duration (seconds)

// IRE app service UUID – only report devices advertising this UUID
#define IRE_SERVICE_UUID "6e400001-b5a3-f393-e0a9-e50e24dcca9e"

WiFiClient   wifiClient;
PubSubClient mqtt(wifiClient);
BLEScan*     bleScan;

void setup_wifi() {
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" connected!");
  Serial.println(WiFi.localIP());
}

void reconnect_mqtt() {
  while (!mqtt.connected()) {
    Serial.print("MQTT connecting...");
    if (mqtt.connect(GATEWAY_ID)) {
      Serial.println(" connected!");
    } else {
      Serial.print(" failed (rc=");
      Serial.print(mqtt.state());
      Serial.println("), retrying in 2 s");
      delay(2000);
    }
  }
}

// ── BLE callback ────────────────────────────────────
class ScanCallback : public BLEAdvertisedDeviceCallbacks {
  void onResult(BLEAdvertisedDevice device) override {
    // Only process IRE app devices (filter by service UUID)
    if (!device.haveServiceUUID() ||
        !device.isAdvertisingService(BLEUUID(IRE_SERVICE_UUID))) {
      return;
    }

    int rssi = device.getRSSI();

    // Use the advertised device name as session_id (set by the Android app).
    // Fall back to MAC address if the name is not present.
    String name = device.getName().c_str();
    String sessionId = (name.length() > 0) ? name : device.getAddress().toString().c_str();

    String payload = "{\"gateway_id\":\"" + String(GATEWAY_ID)
                   + "\",\"session_id\":\"" + sessionId
                   + "\",\"rssi\":" + String(rssi) + "}";

    if (mqtt.connected()) {
      mqtt.publish(MQTT_TOPIC, payload.c_str());
      Serial.println("Published: " + payload);
    }
  }
};

void setup() {
  Serial.begin(115200);
  setup_wifi();

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  reconnect_mqtt();

  BLEDevice::init(GATEWAY_ID);
  bleScan = BLEDevice::getScan();
  bleScan->setAdvertisedDeviceCallbacks(new ScanCallback());
  bleScan->setActiveScan(true);
  bleScan->setInterval(100);
  bleScan->setWindow(99);
}

void loop() {
  if (!mqtt.connected()) reconnect_mqtt();
  mqtt.loop();

  BLEScanResults* results = bleScan->start(SCAN_TIME, false);
  Serial.printf("Scan complete - %d devices found\n", results->getCount());
  bleScan->clearResults();

  delay(100);
}
