#include "poste_core.h"
#include "settings.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <initializer_list>
using namespace poste;
constexpr const char* UTC="2026-10-31T12:00:00Z";
static_assert(!HS_ALLOW_PUBLISH && !HS_HARDWARE_CONFIRMED && !HS_TLS_VALIDATED,"Defaults must stay closed");
static_assert(!HS_IDENTITY_ACL_VALIDATED && !HS_CONTRACT_CONFIRMED,"Acceptance gates must stay closed");
Entry entry(unsigned n,uint32_t at=0) {
  Entry e; char id[65];
  snprintf(id,sizeof(id),"harpisense.poste.poste-1-0123456789abcdef-%u",n);
  assert(serialize(e,id,n,UTC,classify(1234),false,at)); return e;
}
void utcTests() {
  assert(validUtc(UTC)); assert(validUtc("2024-02-29T23:59:59Z"));
  for (auto invalid:{"1970-01-01T00:00:00Z","2025-02-29T00:00:00Z","2026-04-31T00:00:00Z",
      "2026-00-01T00:00:00Z","2026-10-31T24:00:00Z","2026-10-31T12:60:00Z",
      "2026-10-31T12:00:60Z","2026-10-31T12:00:00+00:00","2026-10-31T12:00:00Z\""}) assert(!validUtc(invalid));
  assert(!validUtc(nullptr));
  assert(!freshSync(-1,1000000,3600000));
  assert(!freshSync(2000,1000,3600000));
  assert(freshSync(1000,3600000000LL+1000,3600000));
  assert(!freshSync(1000,3600000000LL+1001,3600000));
}
void hardwareTests() {
  assert(hardwareConfigValid(34,25,1400,2600));
  assert(!hardwareConfigValid(25,26,1400,2600)); // ADC2 excluded with Wi-Fi
  assert(!hardwareConfigValid(34,34,1400,2600));
  assert(!hardwareConfigValid(34,2,1400,2600)); // strapping output excluded
  assert(!hardwareConfigValid(34,25,-1,-1));
  assert(!hardwareConfigValid(34,25,2600,1400));
  assert(!hardwareConfigValid(34,25,0,4096));
  assert(classify(0).quality==Quality::Raw && classify(4095).quality==Quality::Raw);
  assert(classify(-1).quality==Quality::OutOfRange && classify(4096).quality==Quality::OutOfRange);
  assert(classify(0,false).quality==Quality::Unavailable);
  Hysteresis low(1400,2600,true);
  assert(!low.update(classify(2000))); assert(low.update(classify(1400)));
  assert(low.update(classify(2000))); assert(!low.update(classify(2600)));
  assert(low.update(classify(0))); assert(!low.update(classify(-1)));
  Hysteresis high(1400,2600,false);
  assert(high.update(classify(2600))); assert(high.update(classify(2000))); assert(!high.update(classify(1400)));
}
void gateTests() {
  for (unsigned mask=0;mask<128;++mask)
    assert(publicationAllowed(mask&1,mask&2,mask&4,mask&8,mask&16,mask&32,mask&64)==(mask==127));
}
void identityTests() {
  Identity id; char mid[65]; uint64_t seq=0;
  assert(!id.next(mid,seq)); assert(!id.reset("wrong")); assert(!id.reset("0123456789abcdeg"));
  assert(id.reset("0123456789abcdef")); assert(id.next(mid,seq) && seq==1);
  assert(strcmp(mid,"harpisense.poste.poste-1-0123456789abcdef-1")==0);
  assert(id.next(mid,seq) && seq==2);
  assert(id.reset("fedcba9876543210")); assert(id.next(mid,seq) && seq==1);
}
void queueTests() {
  Queue q; Entry out,first=entry(1,1000);
  q.push(first); assert(q.peek(1001,out));
  Entry retry; assert(q.peek(1010,retry)); // failure does not consume or regenerate
  assert(out.size==retry.size && memcmp(out.payload,retry.payload,out.size)==0);
  assert(out.collectedAt==retry.collectedAt);
  for (unsigned n=2;n<=9;++n) q.push(entry(n,1000+n));
  assert(q.size()==8 && q.counters.overflow==1);
  assert(!q.acceptIfHead(first)); // stale successful in-flight publish cannot delete new head
  assert(q.size()==8 && q.peek(1010,out) && strstr(out.payload,"abcdef-2\""));
  assert(q.acceptIfHead(out) && q.size()==7);
  assert(!q.peek(121010,out) && q.counters.expired==7);
  Queue boundary; boundary.push(entry(1,100));
  assert(boundary.peek(120099,out)); assert(!boundary.peek(120100,out));
  Queue wrap; uint32_t start=UINT32_MAX-1000;
  wrap.push(entry(1,start)); assert(wrap.peek(start+119999,out)); assert(!wrap.peek(start+120000,out));
  Queue reboot; assert(!reboot.peek(0,out));
}
void acquisitionTests() {
  Identity id; Queue q; assert(id.reset("0123456789abcdef"));
  assert(!capture(id,q,nullptr,classify(1234),false,100));
  assert(q.size()==0 && q.counters.noUtc==1);
  assert(!capture(id,q,"1970-01-01T00:00:00Z",classify(1234),false,101));
  assert(capture(id,q,UTC,classify(1234),false,200));
  Entry out; assert(q.peek(200,out));
  assert(strstr(out.payload,"abcdef-1\"")); // lost unsynchronized readings never get reconstructed
  assert(strstr(out.payload,"2026-10-31T12:00:00Z"));
}
void serializerTests() {
  Entry e;
  assert(!serialize(e,"bad\"id",1,UTC,classify(0),false,0));
  assert(!serialize(e,"id",MAX_SEQUENCE+1,UTC,classify(0),false,0));
  assert(!serialize(e,"id",1,UTC,{Quality::Raw,4096},false,0));
  assert(!serialize(e,"id",1,UTC,{static_cast<Quality>(100),0},false,0));
  assert(!serialize(e,"id",1,"1970-01-01T00:00:00Z",classify(0),false,0));
  // Real firmware serializer fixtures for external P06 validation, stdout JSONL only.
  unsigned n=0;
  for (Reading r:{classify(0),classify(4095),classify(1800),classify(0,false),classify(-1),classify(4096)}) {
    char id[65]; ++n; snprintf(id,sizeof(id),"harpisense.poste.poste-1-0123456789abcdef-%u",n);
    assert(serialize(e,id,n,UTC,r,n%2,0)); assert(e.size<=1024 && strlen(e.payload)==e.size); puts(e.payload);
  }
  const char* maxId="harpisense.poste.poste-1-0123456789abcdef-9007199254740991";
  assert(serialize(e,maxId,MAX_SEQUENCE,UTC,classify(4095),true,0)); puts(e.payload);
}
int main() {
  utcTests(); hardwareTests(); gateTests(); identityTests(); queueTests(); acquisitionTests(); serializerTests();
  fprintf(stderr,"PASS: 7 core test groups (includes 128 gate combinations)\n");
}
