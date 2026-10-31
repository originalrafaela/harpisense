#pragma once
// Copy to config_local.h; all gates remain closed for this delivery.
#define HS_HARDWARE_CONFIRMED false
// Proposed wiring, not homologated. Measure thresholds on the real divider.
#define HS_LDR_PIN 34
#define HS_LED_PIN 25
#define HS_LED_ACTIVE_HIGH true
#define HS_ADC_DARK_IS_LOW true
#define HS_DARK_THRESHOLD -1
#define HS_BRIGHT_THRESHOLD -1
#define HS_WIFI_SSID ""
#define HS_WIFI_PASSWORD ""
#define HS_NTP_SERVER ""
// DNS name matching certificate SAN; no IP-literal/plaintext fallback.
#define HS_MQTT_HOST ""
#define HS_MQTT_PORT 8883
#define HS_MQTT_USERNAME ""
#define HS_MQTT_PASSWORD ""
// Trusted CA PEM, provisioned independently. Never private keys here in Git.
#define HS_MQTT_CA_PEM ""
#define HS_CONTRACT_CONFIRMED false
#define HS_IDENTITY_ACL_VALIDATED false
#define HS_TLS_VALIDATED false
#define HS_ALLOW_PUBLISH false
