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
static const uint32_t MAX_CYCLES = 30;
static const uint32_t GAP_MS = 250; // máximo ~4 tentativas/s, somente laboratório local
uint32_t cycles = 0, okCount = 0, failCount = 0;
unsigned long lastAttempt = 0;
String sessionId;

void setup() {
  Serial.begin(115200); delay(500); pinMode(LDR_PIN, INPUT); pinMode(LED_PIN, OUTPUT);
  randomSeed(micros() ^ analogRead(LDR_PIN)); sessionId = makeSessionId("A03");
  Serial.printf("[CASE] A03 MQTT Connection Flood [SESSION] %s\n", sessionId.c_str());
  connectWiFi(); mqtt.setServer(MQTT_HOST, MQTT_PORT);
}

void loop() {
  int lum = analogRead(LDR_PIN); setPhysicalLamp(lum);
  if (WiFi.status() != WL_CONNECTED) { connectWiFi(); delay(100); return; }
  if (cycles < MAX_CYCLES && millis() - lastAttempt >= GAP_MS) {
    lastAttempt = millis();
    String cid = "A03-poste01-" + String(cycles);
    bool ok = mqtt.connect(cid.c_str(), USER, PASS);
    if (ok) { okCount++; mqtt.disconnect(); }
    else { failCount++; }
    Serial.printf("[A03] cycle=%lu connected=%s state=%d ok=%lu fail=%lu\n",
      (unsigned long)cycles, ok ? "YES" : "NO", mqtt.state(),
      (unsigned long)okCount, (unsigned long)failCount);
    cycles++;
  }
  if (cycles == MAX_CYCLES) {
    Serial.printf("[A03][DONE] cycles=%lu ok=%lu fail=%lu\n",
      (unsigned long)cycles, (unsigned long)okCount, (unsigned long)failCount);
    cycles++; // imprime uma vez
  }
  delay(5);
}
