#include <Arduino.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>

#include "config.h"

static const char *DEVICE_KEY = "poste-1";
static const char *DEVICE_ID = "harpisense.poste.poste-1";
static const char *TELEMETRY_TOPIC = "harpisense/v1/telemetry/harpisense.poste.poste-1/environment";
static const unsigned long PUBLISH_INTERVAL_MS = 10000;

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

unsigned long lastPublishAt = 0;
uint32_t sequenceNumber = 1;

struct EnvironmentReading {
  bool hasTemperature;
  bool hasHumidity;
  float temperatureC;
  float humidityPct;
};

EnvironmentReading readEnvironment() {
  // Sensor model and ESP32 pin mapping are not defined in the shared contracts yet.
  // Keep the payload contract active without inventing hardware details.
  return {false, false, 0.0, 0.0};
}

String observedAtUtc() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo, 1000)) {
    return "1970-01-01T00:00:00.000Z";
  }

  char buffer[25];
  strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%S.000Z", &timeinfo);
  return String(buffer);
}

String messageId() {
  char buffer[33];
  snprintf(buffer, sizeof(buffer), "%08lx%08lx%08lx%08lx",
           static_cast<unsigned long>(esp_random()),
           static_cast<unsigned long>(esp_random()),
           static_cast<unsigned long>(millis()),
           static_cast<unsigned long>(sequenceNumber));
  return String(buffer);
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.print("WiFi connected: ");
  Serial.println(WiFi.localIP());
}

void connectMqtt() {
  while (!mqttClient.connected()) {
    Serial.print("Connecting MQTT as ");
    Serial.println(DEVICE_KEY);

    if (mqttClient.connect(DEVICE_KEY, MQTT_USERNAME, MQTT_PASSWORD)) {
      Serial.println("MQTT connected");
      return;
    }

    Serial.print("MQTT connect failed, state=");
    Serial.println(mqttClient.state());
    delay(3000);
  }
}

void publishEnvironment() {
  EnvironmentReading reading = readEnvironment();

  StaticJsonDocument<512> doc;
  doc["schema_version"] = "1.0";
  doc["message_id"] = messageId();
  doc["device_id"] = DEVICE_ID;
  doc["observed_at"] = observedAtUtc();
  doc["sensor_type"] = "environment";
  doc["sequence"] = sequenceNumber;

  JsonObject measurements = doc["measurements"].to<JsonObject>();
  if (reading.hasTemperature) {
    measurements["temperature_c"] = reading.temperatureC;
  } else {
    measurements["temperature_c"] = nullptr;
  }
  if (reading.hasHumidity) {
    measurements["humidity_pct"] = reading.humidityPct;
  } else {
    measurements["humidity_pct"] = nullptr;
  }

  JsonObject status = doc["status"].to<JsonObject>();
  status["battery_pct"] = nullptr;
  status["rssi_dbm"] = WiFi.RSSI();

  char payload[512];
  size_t payloadSize = serializeJson(doc, payload, sizeof(payload));
  bool ok = mqttClient.publish(TELEMETRY_TOPIC, reinterpret_cast<const uint8_t *>(payload), payloadSize, false);

  Serial.print("Published sequence=");
  Serial.print(sequenceNumber);
  Serial.print(" ok=");
  Serial.println(ok ? "true" : "false");

  sequenceNumber++;
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  connectWifi();
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");

  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  mqttClient.setKeepAlive(30);
  connectMqtt();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWifi();
  }

  if (!mqttClient.connected()) {
    connectMqtt();
  }

  mqttClient.loop();

  unsigned long now = millis();
  if (now - lastPublishAt >= PUBLISH_INTERVAL_MS || lastPublishAt == 0) {
    lastPublishAt = now;
    publishEnvironment();
  }
}
