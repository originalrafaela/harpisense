#pragma once
// No automatic inclusion of the legacy config.h: it has plaintext lab settings.
#if __has_include("config_local.h")
#include "config_local.h"
#endif
#ifndef HS_HARDWARE_CONFIRMED
#define HS_HARDWARE_CONFIRMED false
#endif
#ifndef HS_ALLOW_PUBLISH
#define HS_ALLOW_PUBLISH false
#endif
#ifndef HS_CONTRACT_CONFIRMED
#define HS_CONTRACT_CONFIRMED false
#endif
#ifndef HS_IDENTITY_ACL_VALIDATED
#define HS_IDENTITY_ACL_VALIDATED false
#endif
#ifndef HS_TLS_VALIDATED
#define HS_TLS_VALIDATED false
#endif
#ifndef HS_LDR_PIN
#define HS_LDR_PIN 34
#endif
#ifndef HS_LED_PIN
#define HS_LED_PIN 25
#endif
#ifndef HS_DARK_THRESHOLD
#define HS_DARK_THRESHOLD -1
#endif
#ifndef HS_BRIGHT_THRESHOLD
#define HS_BRIGHT_THRESHOLD -1
#endif
#ifndef HS_ADC_DARK_IS_LOW
#define HS_ADC_DARK_IS_LOW true
#endif
#ifndef HS_LED_ACTIVE_HIGH
#define HS_LED_ACTIVE_HIGH true
#endif
#ifndef HS_WIFI_SSID
#define HS_WIFI_SSID ""
#endif
#ifndef HS_WIFI_PASSWORD
#define HS_WIFI_PASSWORD ""
#endif
#ifndef HS_MQTT_HOST
#define HS_MQTT_HOST ""
#endif
#ifndef HS_MQTT_PORT
#define HS_MQTT_PORT 8883
#endif
#ifndef HS_MQTT_USERNAME
#define HS_MQTT_USERNAME ""
#endif
#ifndef HS_MQTT_PASSWORD
#define HS_MQTT_PASSWORD ""
#endif
#ifndef HS_MQTT_CA_PEM
#define HS_MQTT_CA_PEM ""
#endif
#ifndef HS_NTP_SERVER
#define HS_NTP_SERVER ""
#endif
namespace settings {
constexpr unsigned SAMPLE_MS=1000, PUBLISH_MS=5000;
constexpr unsigned CLOCK_TRUST_MS=3600000;
}
