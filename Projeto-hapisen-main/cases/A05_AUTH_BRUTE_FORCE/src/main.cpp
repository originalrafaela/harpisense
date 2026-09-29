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

static const char* USER = "test_auth";
static const char* VALID_PASS = "auth-lab-pass";
static const char* BAD_PASSWORDS[] = {"bad001","bad002","bad003","bad004","bad005","bad006"};
static const size_t BAD_COUNT = sizeof(BAD_PASSWORDS)/sizeof(BAD_PASSWORDS[0]);
static const uint32_t GAP_MS = 700;
size_t attempt = 0;
unsigned long lastAttempt = 0;
String sessionId;

void setup() {
  Serial.begin(115200); delay(500); pinMode(LDR_PIN, INPUT); pinMode(LED_PIN, OUTPUT);
  randomSeed(micros() ^ analogRead(LDR_PIN)); sessionId = makeSessionId("A05");
  Serial.printf("[CASE] A05 MQTT Authentication Brute Force CONTROLADO [SESSION] %s\n", sessionId.c_str());
  connectWiFi(); mqtt.setServer(MQTT_HOST, MQTT_PORT);
}

void loop() {
  int lum = analogRead(LDR_PIN); setPhysicalLamp(lum);
  if (WiFi.status() != WL_CONNECTED) { connectWiFi(); delay(100); return; }
  if (attempt < BAD_COUNT && millis() - lastAttempt >= GAP_MS) {
    lastAttempt = millis();
    String cid = "A05-auth-" + String(attempt);
    bool ok = mqtt.connect(cid.c_str(), USER, BAD_PASSWORDS[attempt]);
    int state = mqtt.state();
    if (ok) mqtt.disconnect();
    Serial.printf("[A05] attempt=%u result=%s mqtt_state=%d\n", (unsigned)attempt, ok ? "UNEXPECTED_SUCCESS" : "EXPECTED_FAIL", state);
    attempt++;
  } else if (attempt == BAD_COUNT && millis() - lastAttempt >= GAP_MS) {
    lastAttempt = millis();
    bool ok = mqtt.connect("A05-auth-final-valid", USER, VALID_PASS);
    Serial.printf("[A05][CONTROL] valid_credentials=%s mqtt_state=%d\n", ok ? "SUCCESS" : "FAIL", mqtt.state());
    if (ok) mqtt.disconnect();
    attempt++;
  } else if (attempt == BAD_COUNT + 1) {
    Serial.printf("[A05][DONE] invalid_attempts=%u + 1 valid control\n", (unsigned)BAD_COUNT);
    attempt++;
  }
  delay(5);
}
