// Host verification of the real hardware adapter and hysteresis with synthetic ADC.
// This is neither Wokwi execution nor electrical validation.
#include <cassert>
#include <cstdio>
#include "Arduino.h"
#include "settings.h"
#include "hardware.h"
namespace { int adc=0,level=-1,readPin=-1,ldrMode=-1,ledMode=-1,bits=-1,attenuation=-1; }
void digitalWrite(int pin,int value) { assert(pin==25); level=value; }
void pinMode(int pin,int mode) {
  assert(pin==34 || pin==25);
  (pin==34?ldrMode:ledMode)=mode;
}
void analogReadResolution(int value) { bits=value; }
void analogSetPinAttenuation(int pin,int value) { assert(pin==34); attenuation=value; }
int analogRead(int pin) { readPin=pin; return adc; }
int main() {
  static_assert(HS_LDR_PIN==34 && HS_LED_PIN==25,"preserve proposed GPIOs");
  static_assert(!HS_ALLOW_PUBLISH && !HS_CONTRACT_CONFIRMED &&
                !HS_TLS_VALIDATED && !HS_IDENTITY_ACL_VALIDATED,"MQTT must remain closed");
  assert(hardware::begin());
  assert(level==LOW && ldrMode==INPUT && ledMode==OUTPUT && bits==12 && attenuation==ADC_11db);
  poste::Hysteresis hysteresis(HS_DARK_THRESHOLD,HS_BRIGHT_THRESHOLD,HS_ADC_DARK_IS_LOW);
  const int inputs[]={500,2000,3000,2000,500};
  const bool expected[]={false,false,true,true,false};
  for (unsigned i=0;i<5;++i) {
    adc=inputs[i]; auto reading=hardware::readLdr();
    assert(readPin==34 && reading.quality==poste::Quality::Raw && reading.raw==adc);
    bool on=hysteresis.update(reading); hardware::commandLed(on);
    assert(on==expected[i] && level==(on?HIGH:LOW));
    std::printf("synthetic_adc=%d GPIO34_read=%d GPIO25_command=%d\n",adc,readPin,level);
  }
  assert(!poste::publicationAllowed(true,HS_ALLOW_PUBLISH,HS_CONTRACT_CONFIRMED,
      HS_IDENTITY_ACL_VALIDATED,HS_TLS_VALIDATED,true,true));
  std::puts("PASS: real hardware.cpp and hysteresis; synthetic ADC; MQTT closed");
}
