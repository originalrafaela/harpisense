#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>

// HarpiSense TCC - laboratório controlado
// Criado em: 2026-09-23
// Broker deliberadamente restrito ao host local do Wokwi Private IoT Gateway.

static const int LDR_PIN = 34;
static const int LED_PIN = 2;
static const int LIGHT_THRESHOLD = 2000;
static const char* WIFI_SSID = "Wokwi-GUEST";
static const char* WIFI_PASSWORD = "";
static const char* MQTT_HOST = "host.wokwi.internal";
static const uint16_t MQTT_PORT = 1883;

WiFiClient net;
PubSubClient mqtt(net);

String makeSessionId(const char* caseId) {
  return String(caseId) + "-" + String((uint32_t)millis()) + "-" + String(random(1000, 9999));
}

void setPhysicalLamp(int raw) {
  bool on = raw < LIGHT_THRESHOLD;
  digitalWrite(LED_PIN, on ? HIGH : LOW);
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.print("[WiFi] conectando");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD, 6);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; ++i) {
    delay(250);
    Serial.print('.');
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("[WiFi] OK IP=");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("[WiFi] FALHA");
  }
}

static const char* USER = "poste01";
static const char* PASS = "poste01-lab-pass";
static const char* TOPIC = "harpisense/city/lights/poste-01/telemetry";
String sessionId;
unsigned long lastPublish = 0;
uint32_t seq = 0;

void ensureMqtt() {
  if (mqtt.connected() || WiFi.status() != WL_CONNECTED) return;
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  if (mqtt.connect("harpisense-poste-01", USER, PASS)) Serial.println("[MQTT] conectado");
  else { Serial.print("[MQTT] falha state="); Serial.println(mqtt.state()); }
}

void publishNormal() {
  int lum = analogRead(LDR_PIN);
  setPhysicalLamp(lum);
  const char* lamp = lum < LIGHT_THRESHOLD ? "ON" : "OFF";
  String payload = String("{\"device_id\":\"poste-01\",\"session_id\":\"") + sessionId +
    "\",\"seq\":" + seq + ",\"luminosity\":" + lum + ",\"lamp\":\"" + lamp + "\"}";
  bool ok = mqtt.publish(TOPIC, payload.c_str());
  Serial.printf("[NORMAL][%lu] publish=%s %s\n", (unsigned long)seq, ok ? "OK" : "FAIL", payload.c_str());
  seq++;
}

void setup() {
  Serial.begin(115200); delay(500); pinMode(LDR_PIN, INPUT); pinMode(LED_PIN, OUTPUT);
  randomSeed(micros() ^ analogRead(LDR_PIN));
  sessionId = makeSessionId("NORMAL");
  Serial.printf("[CASE] NORMAL [SESSION] %s\n", sessionId.c_str());
  connectWiFi(); mqtt.setBufferSize(512);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  ensureMqtt(); mqtt.loop();
  if (mqtt.connected() && millis() - lastPublish >= 1000) { lastPublish = millis(); publishNormal(); }
  delay(5);
}
