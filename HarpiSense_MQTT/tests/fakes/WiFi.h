#pragma once
#include <string.h>
constexpr int WIFI_STA=1, WL_CONNECTED=3;
struct IPAddress { bool fromString(const char* host) { return strcmp(host,"192.0.2.1")==0; } };
struct WiFiStub {
  unsigned begins=0; int statusValue=WL_CONNECTED;
  void mode(int) {}
  void begin(const char*,const char*) { ++begins; }
  int status() { return statusValue; }
};
extern WiFiStub WiFi;
