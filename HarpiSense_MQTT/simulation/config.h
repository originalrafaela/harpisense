#pragma once
// SIMULATION ONLY. Never flash to a physical board.
#if __has_include("config_local.h")
#error "Remove config_local.h before building Wokwi; no physical credentials in simulation"
#endif
#define HS_HARDWARE_CONFIRMED true
#define HS_LDR_PIN 34
#define HS_LED_PIN 25
#define HS_LED_ACTIVE_HIGH true
// Wokwi AO rises in darkness. Numeric thresholds remain ordered low < high.
#define HS_ADC_DARK_IS_LOW false
#define HS_DARK_THRESHOLD 1200
#define HS_BRIGHT_THRESHOLD 2800
#define HS_ALLOW_PUBLISH false
#define HS_CONTRACT_CONFIRMED false
#define HS_IDENTITY_ACL_VALIDATED false
#define HS_TLS_VALIDATED false
