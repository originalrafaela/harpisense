#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <string.h>
#include "settings.h"
#include "trusted_clock.h"
#include "communication.h"
namespace {
WiFiClientSecure tls;
PubSubClient mqtt(tls);
uint32_t lastWifi=0,lastMqtt=0,wifiBackoff=1000,mqttBackoff=1000;
bool enabled=false;
bool filled(const char* value) { return value && value[0]!='\0'; }
bool configured() {
  IPAddress literal;
  return filled(HS_WIFI_SSID) && filled(HS_WIFI_PASSWORD) && filled(HS_NTP_SERVER) &&
    filled(HS_MQTT_HOST) && !literal.fromString(HS_MQTT_HOST) &&
    filled(HS_MQTT_USERNAME) && filled(HS_MQTT_PASSWORD) && HS_MQTT_PORT>0 &&
    strstr(HS_MQTT_CA_PEM,"-----BEGIN CERTIFICATE-----") && strstr(HS_MQTT_CA_PEM,"-----END CERTIFICATE-----");
}
}
namespace communication {
bool begin() {
  if (!poste::publicationAllowed(HS_HARDWARE_CONFIRMED,HS_ALLOW_PUBLISH,HS_CONTRACT_CONFIRMED,
      HS_IDENTITY_ACL_VALIDATED,HS_TLS_VALIDATED,configured(),true)) return false;
  tls.setCACert(HS_MQTT_CA_PEM);
  tls.setHandshakeTimeout(5);
  tls.setTimeout(3); // Arduino-ESP32 2.0.17 uses seconds, unlike Stream.
  mqtt.setServer(HS_MQTT_HOST,HS_MQTT_PORT); // preserve DNS hostname for SNI and verification
  mqtt.setKeepAlive(30); mqtt.setSocketTimeout(3);
  if (!mqtt.setBufferSize(1536)) return false;
  WiFi.mode(WIFI_STA);
  clock_source::begin();
  enabled=true; return true;
}
bool poll() {
  if (!enabled) return false;
  uint32_t now=millis();
  if (WiFi.status()!=WL_CONNECTED) {
    if (static_cast<uint32_t>(now-lastWifi)>=wifiBackoff) {
      WiFi.begin(HS_WIFI_SSID,HS_WIFI_PASSWORD);
      lastWifi=now; wifiBackoff=min(wifiBackoff*2U,60000U);
    }
    return false;
  }
  wifiBackoff=1000;
  char stamp[21];
  if (!clock_source::utc(stamp)) { if (mqtt.connected()) mqtt.disconnect(); return false; }
  if (mqtt.connected()) { mqtt.loop(); return mqtt.connected(); }
  if (static_cast<uint32_t>(now-lastMqtt)<mqttBackoff) return false;
  bool ok=mqtt.connect(poste::CLIENT_ID,HS_MQTT_USERNAME,HS_MQTT_PASSWORD);
  lastMqtt=millis();
  if (ok) mqttBackoff=1000;
  else { mqttBackoff=min(mqttBackoff*2U,60000U); Serial.printf("mqtt_connect_failed state=%d\n",mqtt.state()); }
  return ok;
}
bool publish(const poste::Entry& e) {
  char stamp[21];
  if (!enabled || !mqtt.connected() || !clock_source::utc(stamp) ||
      static_cast<uint32_t>(millis()-e.collectedAt)>=poste::MAX_AGE_MS || !e.size || e.size>poste::MAX_PAYLOAD) return false;
  // QoS 0: true means local transport acceptance, NOT broker or database ACK.
  return mqtt.publish(poste::TOPIC,reinterpret_cast<const uint8_t*>(e.payload),e.size,false);
}
}
