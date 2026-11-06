#pragma once
#include <stdint.h>
constexpr int LOW=0,HIGH=1,INPUT=0,OUTPUT=1,ADC_11db=3;
void digitalWrite(int pin,int value);
void pinMode(int pin,int mode);
void analogReadResolution(int bits);
void analogSetPinAttenuation(int pin,int attenuation);
int analogRead(int pin);
