/*
 * ESP32 BLE Gateway – Intelligent Retail Ecosystem
 * ─────────────────────────────────────────────────
 * Scans for phone BLE advertisements, extracts RSSI,
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

// ── CONFIGURATION ───────────────────────────────────
#define GATEWAY_ID   "esp32_A"          // Unique per gateway (esp32_A / B / C)
#define WIFI_SSID    "STORE_WIFI"
#define WIFI_PASS    "store_password"
#define MQTT_HOST    "192.168.1.100"    // Backend server IP
#define MQTT_PORT    1883
#define MQTT_TOPIC   "ire/ble/rssi"
#define SCAN_TIME    2                  // BLE scan duration (seconds)

// ── Target BLE service UUID (broadcast by PWA) ─────
// The phone PWA advertises this service UUID so gateways can filter
#define TARGET_SERVICE_UUID "12345678-1234-1234-1234-123456789abc"

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
    Serial.print("MQTT connecting…");
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
    // Check if the device advertises our target service
    if (!device.haveServiceUUID()) return;
    if (!device.isAdvertisingService(BLEUUID(TARGET_SERVICE_UUID))) return;

    int rssi = device.getRSSI();
    String name = device.getName().c_str();
    // Use the device name or manufacturer data as session_id
    String sessionId = (name.length() > 0) ? name : device.getAddress().toString().c_str();

    // Build JSON payload
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

  // Initialise BLE scanner
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

  // Run BLE scan
  BLEScanResults results = bleScan->start(SCAN_TIME, false);
  Serial.printf("Scan complete – %d devices found\n", results.getCount());
  bleScan->clearResults();

  delay(100);  // Small gap between scans
}
