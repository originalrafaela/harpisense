#include <Arduino.h>
#include "settings.h"
#include "hardware.h"
namespace hardware {
bool begin() {
  if (!HS_HARDWARE_CONFIRMED || !poste::hardwareConfigValid(HS_LDR_PIN,HS_LED_PIN,HS_DARK_THRESHOLD,HS_BRIGHT_THRESHOLD)) return false;
  digitalWrite(HS_LED_PIN,HS_LED_ACTIVE_HIGH?LOW:HIGH);
  pinMode(HS_LED_PIN,OUTPUT);
  pinMode(HS_LDR_PIN,INPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(HS_LDR_PIN,ADC_11db);
  return true;
}
poste::Reading readLdr() { return poste::classify(analogRead(HS_LDR_PIN)); }
void commandLed(bool on) { digitalWrite(HS_LED_PIN,(on==HS_LED_ACTIVE_HIGH)?HIGH:LOW); }
}
