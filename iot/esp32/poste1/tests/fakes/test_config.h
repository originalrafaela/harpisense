#pragma once
#ifndef TEST_CLOSED
#define HS_HARDWARE_CONFIRMED true
#define HS_ALLOW_PUBLISH true
#define HS_CONTRACT_CONFIRMED true
#define HS_IDENTITY_ACL_VALIDATED true
#define HS_TLS_VALIDATED true
#endif
#define HS_WIFI_SSID "synthetic-test-only"
#define HS_WIFI_PASSWORD "synthetic-test-only"
#define HS_NTP_SERVER "clock.invalid"
#ifdef TEST_IP_LITERAL
#define HS_MQTT_HOST "192.0.2.1"
#else
#define HS_MQTT_HOST "broker.invalid"
#endif
#define HS_MQTT_USERNAME "synthetic-poste1-only"
#define HS_MQTT_PASSWORD "synthetic-test-only"
#ifndef TEST_NO_CA
#define HS_MQTT_CA_PEM "-----BEGIN CERTIFICATE-----\nSYNTHETIC-NOT-A-CERTIFICATE\n-----END CERTIFICATE-----"
#endif
