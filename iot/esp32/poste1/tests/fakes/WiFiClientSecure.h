#pragma once
extern const char* capturedCa;
extern unsigned capturedHandshake, capturedTimeout;
struct WiFiClientSecure {
  void setCACert(const char* ca) { capturedCa=ca; }
  void setHandshakeTimeout(unsigned seconds) { capturedHandshake=seconds; }
  void setTimeout(unsigned timeout) { capturedTimeout=timeout; }
  // Deliberately no insecure API: accidental bypass fails test compilation.
};
