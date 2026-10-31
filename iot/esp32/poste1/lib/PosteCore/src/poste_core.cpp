#include "poste_core.h"
#include <stdio.h>
#include <string.h>
namespace poste {
Reading classify(int raw, bool available) {
  if (!available) return {Quality::Unavailable, 0};
  if (raw < 0 || raw > 4095) return {Quality::OutOfRange, 0};
  return {Quality::Raw, raw};
}
bool validUtc(const char* s) {
  if (!s || strlen(s) != 20) return false;
  for (int i=0;i<20;++i) {
    char expected = i==4 || i==7 ? '-' : i==10 ? 'T' : i==13 || i==16 ? ':' : i==19 ? 'Z' : 0;
    if (expected ? s[i]!=expected : (s[i]<'0' || s[i]>'9')) return false;
  }
  auto num=[s](int p) { return (s[p]-'0')*10+s[p+1]-'0'; };
  int year=num(0)*100+num(2), month=num(5), day=num(8);
  if (year<2024 || year>2099 || month<1 || month>12) return false;
  const int days[]={31,28,31,30,31,30,31,31,30,31,30,31};
  int maxDay=days[month-1]+(month==2 && year%4==0 ? 1 : 0);
  return day>=1 && day<=maxDay && num(11)<24 && num(14)<60 && num(17)<60;
}
bool hardwareConfigValid(int ldr, int led, int dark, int bright) {
  const int adc1[]={32,33,34,35,36,39};
  const int outputs[]={13,14,16,17,18,19,21,22,23,25,26,27,32,33};
  bool adc=false,output=false;
  for (int pin:adc1) adc|=pin==ldr;
  for (int pin:outputs) output|=pin==led;
  return adc && output && ldr!=led && dark>=0 && bright<=4095 && dark<bright;
}
bool freshSync(int64_t lastSyncUs,int64_t nowUs,uint32_t maxAgeMs) {
  return lastSyncUs>=0 && nowUs>=lastSyncUs && nowUs-lastSyncUs<=static_cast<int64_t>(maxAgeMs)*1000;
}
bool publicationAllowed(bool h,bool a,bool c,bool i,bool t,bool n,bool clock) { return h&&a&&c&&i&&t&&n&&clock; }
bool Hysteresis::update(Reading r) {
  if (r.quality!=Quality::Raw) { on_=false; return on_; }
  if (low_ ? r.raw<=dark_ : r.raw>=bright_) on_=true;
  else if (low_ ? r.raw>=bright_ : r.raw<=dark_) on_=false;
  return on_;
}
bool Identity::reset(const char* boot) {
  if (!boot || strlen(boot)!=16) return false;
  for (int i=0;i<16;++i) if (!((boot[i]>='0'&&boot[i]<='9')||(boot[i]>='a'&&boot[i]<='f'))) return false;
  memcpy(boot_,boot,17); sequence_=0; return true;
}
bool Identity::next(char (&id)[65],uint64_t& seq) {
  if (!boot_[0] || exhausted()) return false;
  seq=++sequence_;
  int n=snprintf(id,sizeof(id),"%s-%s-%llu",DEVICE,boot_,static_cast<unsigned long long>(seq));
  return n>0 && static_cast<size_t>(n)<sizeof(id);
}
bool serialize(Entry& out,const char* id,uint64_t seq,const char* utc,Reading r,bool led,uint32_t at) {
  if (!id || !*id || strlen(id)>64 || seq>MAX_SEQUENCE || !validUtc(utc)) return false;
  for (const char* p=id;*p;++p) if (!((*p>='a'&&*p<='z')||(*p>='A'&&*p<='Z')||(*p>='0'&&*p<='9')||*p=='.'||*p=='_'||*p=='-')) return false;
  if (r.quality==Quality::Raw && (r.raw<0 || r.raw>4095)) return false;
  if (r.quality!=Quality::Raw && r.quality!=Quality::Unavailable && r.quality!=Quality::OutOfRange) return false;
  char raw[12];
  if (r.quality==Quality::Raw) snprintf(raw,sizeof(raw),"%d",r.raw); else memcpy(raw,"null",5);
  const char* quality=r.quality==Quality::Raw ? "RAW_UNCALIBRATED" : r.quality==Quality::Unavailable ? "UNAVAILABLE" : "OUT_OF_RANGE";
  int n=snprintf(out.payload,sizeof(out.payload),
    "{\"schema_version\":\"harpisense.telemetry.candidate.v2\",\"message_id\":\"%s\","
    "\"device_id\":\"%s\",\"observed_at\":\"%s\",\"sensor_type\":\"ldr\",\"sequence\":%llu,"
    "\"measurements\":{\"ldr_adc_raw\":%s,\"led_commanded_on\":%s},"
    "\"status\":{\"origin_type\":\"PHYSICAL\",\"reading_quality\":\"%s\",\"reading_unit\":\"adc_raw\"}}",
    id,DEVICE,utc,static_cast<unsigned long long>(seq),raw,led?"true":"false",quality);
  if (n<=0 || static_cast<size_t>(n)>MAX_PAYLOAD) { out.size=0; return false; }
  out.size=static_cast<size_t>(n); out.collectedAt=at; return true;
}
void Queue::pop() { if (count_) { head_=(head_+1)%CAPACITY; --count_; } }
void Queue::push(const Entry& e) {
  if (count_==CAPACITY) { pop(); ++counters.overflow; }
  entries_[(head_+count_)%CAPACITY]=e; ++count_;
}
bool Queue::peek(uint32_t now,Entry& out) {
  while (count_ && static_cast<uint32_t>(now-entries_[head_].collectedAt)>=MAX_AGE_MS) { pop(); ++counters.expired; }
  if (!count_) return false;
  out=entries_[head_]; return true;
}
bool Queue::acceptIfHead(const Entry& e) {
  // Slow publish can overlap overflow/expiry. Never remove an unrelated head.
  ++counters.acceptedLocal;
  if (!count_ || e.size!=entries_[head_].size || memcmp(e.payload,entries_[head_].payload,e.size)!=0) return false;
  pop(); return true;
}
bool capture(Identity& identity,Queue& queue,const char* utc,Reading reading,bool led,uint32_t at) {
  if (!validUtc(utc)) { ++queue.counters.noUtc; return false; }
  char id[65]; uint64_t sequence; Entry entry;
  if (!identity.next(id,sequence) || !serialize(entry,id,sequence,utc,reading,led,at)) {
    ++queue.counters.invalid; return false;
  }
  queue.push(entry); return true;
}
}
