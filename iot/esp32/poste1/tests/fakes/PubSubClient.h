#pragma once
#include <stddef.h>
#include <stdint.h>
#include "WiFiClientSecure.h"
extern const char *capturedHost,*capturedClientId,*capturedTopic;
extern unsigned capturedPort, connectCalls, publishCalls;
extern bool fakeConnectOk, fakePublishOk, fakeBufferOk, capturedRetain;
struct PubSubClient {
  bool connected_=false;
  explicit PubSubClient(WiFiClientSecure&) {}
  void setServer(const char* host,unsigned port) { capturedHost=host; capturedPort=port; }
  void setKeepAlive(unsigned) {}
  void setSocketTimeout(unsigned) {}
  bool setBufferSize(unsigned n) { return fakeBufferOk && n>=1536; }
  bool connected() { return connected_; }
  void disconnect() { connected_=false; }
  void loop() {}
  bool connect(const char* id,const char*,const char*) { ++connectCalls;capturedClientId=id;connected_=fakeConnectOk;return connected_; }
  int state() { return -2; }
  bool publish(const char* topic,const uint8_t*,size_t,bool retain) {
    ++publishCalls;capturedTopic=topic;capturedRetain=retain;return fakePublishOk;
  }
};
