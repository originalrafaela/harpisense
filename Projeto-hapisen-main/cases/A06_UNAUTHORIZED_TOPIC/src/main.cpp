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
static const char* ALLOWED_TOPIC = "harpisense/city/lights/poste-01/telemetry";
static const char* FORBIDDEN_TOPIC = "harpisense/city/lights/poste-01/commands";
static const uint32_t MAX_ATTEMPTS = 10;
uint32_t attempts = 0, seq = 0;
unsigned long lastTry = 0, lastNormal = 0;
String sessionId;

void ensureMqtt() {
  if (mqtt.connected() || WiFi.status() != WL_CONNECTED) return;
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  if (mqtt.connect("A06-poste01", USER, PASS)) Serial.println("[MQTT] conectado como poste01");
  else { Serial.print("[MQTT] falha state="); Serial.println(mqtt.state()); }
}

void setup() {
  Serial.begin(115200); delay(500); pinMode(LDR_PIN, INPUT); pinMode(LED_PIN, OUTPUT);
  randomSeed(micros() ^ analogRead(LDR_PIN)); sessionId = makeSessionId("A06");
  Serial.printf("[CASE] A06 Unauthorized Topic Access [SESSION] %s\n", sessionId.c_str());
  connectWiFi(); mqtt.setBufferSize(512);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  ensureMqtt(); mqtt.loop();
  if (!mqtt.connected()) { delay(20); return; }
  int lum = analogRead(LDR_PIN); setPhysicalLamp(lum);
  if (millis() - lastNormal >= 2000) {
    lastNormal = millis();
    String p = String("{\"device_id\":\"poste-01\",\"session_id\":\"") + sessionId + "\",\"seq\":" + seq++ + ",\"luminosity\":" + lum + "}";
    mqtt.publish(ALLOWED_TOPIC, p.c_str());
  }
  if (attempts < MAX_ATTEMPTS && millis() - lastTry >= 1000) {
    lastTry = millis();
    String cmd = String("{\"cmd\":\"FORCED_ON\",\"session_id\":\"") + sessionId + "\"}";
    bool packetSent = mqtt.publish(FORBIDDEN_TOPIC, cmd.c_str());
    Serial.printf("[A06] unauthorized_publish=%lu packet_sent=%s; conferir 'Denied PUBLISH' no log do broker\n",
      (unsigned long)attempts, packetSent ? "YES" : "NO");
    attempts++;
  }
  if (attempts == MAX_ATTEMPTS) { Serial.println("[A06][DONE] validar ACL no broker/log/mosquitto.log"); attempts++; }
  delay(5);
}
