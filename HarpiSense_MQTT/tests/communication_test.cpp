// Test doubles exercise the firmware's network orchestration, NOT real TLS/MQTT.
#include <assert.h>
#include <string.h>
#include "Arduino.h"
#include "WiFi.h"
#include "settings.h"
#include "communication.h"
uint32_t fakeMillis=1000;
SerialStub Serial;
WiFiStub WiFi;
const char *capturedCa=nullptr,*capturedHost=nullptr,*capturedClientId=nullptr,*capturedTopic=nullptr;
unsigned capturedHandshake=0,capturedTimeout=0,capturedPort=0,connectCalls=0,publishCalls=0;
bool fakeConnectOk=false,fakePublishOk=false,fakeBufferOk=true,capturedRetain=true;
bool trusted=false;
namespace clock_source {
void begin() {}
bool utc(char (&s)[21]) { memcpy(s,"2026-10-31T12:00:00Z",21);return trusted; }
}
int main() {
#if defined(TEST_CLOSED) || defined(TEST_NO_CA) || defined(TEST_IP_LITERAL)
  assert(!communication::begin()); assert(!communication::poll());
  assert(WiFi.begins==0 && connectCalls==0 && capturedCa==nullptr);
#else
  assert(communication::begin());
  assert(strcmp(capturedCa,HS_MQTT_CA_PEM)==0);
  assert(strcmp(capturedHost,"broker.invalid")==0 && capturedPort==8883);
  assert(capturedHandshake==5 && capturedTimeout==3);
  assert(!communication::poll() && connectCalls==0); // no UTC: no TLS connection attempt
  trusted=true;
  assert(!communication::poll() && connectCalls==1); // failed connection never falls back
  assert(!communication::poll() && connectCalls==1); // backoff
  fakeMillis=100000; fakeConnectOk=true;
  assert(communication::poll() && connectCalls==2);
  assert(strcmp(capturedClientId,"poste-1")==0);
  poste::Entry entry;
  assert(poste::serialize(entry,"harpisense.poste.poste-1-0123456789abcdef-1",1,
    "2026-10-31T12:00:00Z",poste::classify(1234),true,fakeMillis));
  assert(!communication::publish(entry)); // local send failure reported
  fakePublishOk=true;
  assert(communication::publish(entry));
  assert(strcmp(capturedTopic,poste::TOPIC)==0 && !capturedRetain);
  fakeMillis+=120000;
  unsigned before=publishCalls;
  assert(!communication::publish(entry) && publishCalls==before); // expired bytes never sent
  entry.collectedAt=fakeMillis; trusted=false;
  assert(!communication::publish(entry) && publishCalls==before);
  assert(!communication::poll()); // clock trust lost: disconnect
#endif
}
