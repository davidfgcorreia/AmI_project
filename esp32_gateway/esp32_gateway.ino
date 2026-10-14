/*
 * ESP32 BLE Gateway – Intelligent Retail Ecosystem
 * ─────────────────────────────────────────────────
 * Scans for BLE devices, extracts RSSI,
 * and publishes to MQTT broker.
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

// Network credentials are local deployment configuration, not source code.
#if __has_include("gateway_config.h")
#include "gateway_config.h"
#else
#include "gateway_config.example.h"
#endif

// ── CONFIGURATION ───────────────────────────────────
#define GATEWAY_ID   "esp32_B"              // Unique per gateway (esp32_A / B / C)
#define MQTT_PORT    1883
#define MQTT_TOPIC   "ire/ble/rssi"
#define SCAN_TIME    1                      // BLE scan duration (seconds)

// ── BLE FILTER ──────────────────────────────────────
#define BLE_NAME_PREFIX  "IRE-"            // Only accept devices whose name starts with this
#define RSSI_MIN        -150               // Accept signals down to -150 dBm

WiFiClient   wifiClient;
PubSubClient mqtt(wifiClient);
BLEScan*     bleScan;

void setup_wifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting to WiFi");
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println(" connected!");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println(" FAILED!");
    Serial.print("Status: ");
    Serial.println(WiFi.status());
  }
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

// ── Helper: check if name starts with prefix ────────
bool hasValidPrefix(const String& name) {
  if (name.length() == 0) return false;
  return name.startsWith(BLE_NAME_PREFIX);
}

// ── BLE callback ────────────────────────────────────
class ScanCallback : public BLEAdvertisedDeviceCallbacks {
  void onResult(BLEAdvertisedDevice device) override {
    String name = device.getName().c_str();
    int    rssi  = device.getRSSI();

    // ── FILTER 1: Must have a name starting with "IRE-" ──
    if (!hasValidPrefix(name)) {
      Serial.printf("Skipped (name filter): [%s] RSSI=%d\n",
                    name.length() > 0 ? name.c_str() : "<no name>", rssi);
      return;
    }

    // ── FILTER 2: RSSI must be within acceptable range ──
    if (rssi < RSSI_MIN) {
      Serial.printf("Skipped (RSSI too low): [%s] RSSI=%d\n", name.c_str(), rssi);
      return;
    }

    // ── Passed all filters → publish ────────────────────
    String payload = "{\"gateway_id\":\"" + String(GATEWAY_ID)
                   + "\",\"session_id\":\"" + name
                   + "\",\"rssi\":"         + String(rssi) + "}";

    if (mqtt.connected()) {
      mqtt.publish(MQTT_TOPIC, payload.c_str());
      Serial.println("Published: " + payload);
    } else {
      Serial.println("MQTT not connected – dropped: " + payload);
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

  Serial.printf("BLE filter: name prefix = \"%s\", RSSI >= %d dBm\n",
                BLE_NAME_PREFIX, RSSI_MIN);
}

void loop() {
  if (!mqtt.connected()) reconnect_mqtt();
  mqtt.loop();

  BLEScanResults* results = bleScan->start(SCAN_TIME, false);
  Serial.printf("Scan complete – %d devices found (pre-filter)\n", results->getCount());
  bleScan->clearResults();

  delay(100);
}