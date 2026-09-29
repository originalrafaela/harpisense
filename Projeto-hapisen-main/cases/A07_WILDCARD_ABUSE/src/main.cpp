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

static const char* USER = "reader_limited";
static const char* PASS = "reader-lab-pass";
static const char* TOPICS[] = {"#", "harpisense/#", "harpisense/+/lights/#", "+/+/+/+/telemetry"};
static const size_t TOPIC_COUNT = sizeof(TOPICS)/sizeof(TOPICS[0]);
static const uint32_t MAX_ATTEMPTS = 12;
uint32_t attempts = 0;
unsigned long lastTry = 0;
String sessionId;

void callback(char* topic, byte* payload, unsigned int length) {
  Serial.printf("[RX] topic=%s bytes=%u\n", topic, length);
}

void ensureMqtt() {
  if (mqtt.connected() || WiFi.status() != WL_CONNECTED) return;
  mqtt.setServer(MQTT_HOST, MQTT_PORT); mqtt.setCallback(callback);
  if (mqtt.connect("A07-reader-limited", USER, PASS)) Serial.println("[MQTT] conectado como reader_limited");
  else { Serial.print("[MQTT] falha state="); Serial.println(mqtt.state()); }
}

void setup() {
  Serial.begin(115200); delay(500); pinMode(LDR_PIN, INPUT); pinMode(LED_PIN, OUTPUT);
  randomSeed(micros() ^ analogRead(LDR_PIN)); sessionId = makeSessionId("A07");
  Serial.printf("[CASE] A07 MQTT Topic/Wildcard Abuse [SESSION] %s\n", sessionId.c_str());
  connectWiFi();
}

void loop() {
  int lum = analogRead(LDR_PIN); setPhysicalLamp(lum);
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  ensureMqtt(); mqtt.loop();
  if (mqtt.connected() && attempts < MAX_ATTEMPTS && millis() - lastTry >= 1000) {
    lastTry = millis();
    const char* topic = TOPICS[attempts % TOPIC_COUNT];
    bool sent = mqtt.subscribe(topic, 0);
    Serial.printf("[A07] subscribe_attempt=%lu topic=%s packet_sent=%s; validar ACL no log do broker\n",
      (unsigned long)attempts, topic, sent ? "YES" : "NO");
    attempts++;
  }
  if (attempts == MAX_ATTEMPTS) { Serial.println("[A07][DONE] conferir 'Denied SUBSCRIBE' no broker/log/mosquitto.log"); attempts++; }
  delay(5);
}
