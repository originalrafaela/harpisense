#pragma once
#include <stddef.h>
#include <stdint.h>

// Portable application rules: no GPIO, network, wall clock, heap or credentials.
namespace poste {
constexpr const char* DEVICE = "harpisense.poste.poste-1";
constexpr const char* TOPIC = "harpisense/v1/telemetry/harpisense.poste.poste-1/ldr";
constexpr const char* CLIENT_ID = "poste-1";
constexpr uint64_t MAX_SEQUENCE = 9007199254740991ULL;
constexpr size_t MAX_PAYLOAD = 1024, CAPACITY = 8;
constexpr uint32_t MAX_AGE_MS = 120000;
enum class Quality { Raw, Unavailable, OutOfRange };
struct Reading { Quality quality; int raw; };
Reading classify(int raw, bool available = true);
bool validUtc(const char* stamp);
bool freshSync(int64_t lastSyncUs, int64_t nowUs, uint32_t maxAgeMs);
bool hardwareConfigValid(int ldrPin, int ledPin, int dark, int bright);
bool publicationAllowed(bool hardware, bool allow, bool contract, bool identityAcl,
                        bool tlsValidated, bool networkConfig, bool trustedClock);
class Hysteresis {
 public:
  Hysteresis(int dark, int bright, bool darkIsLow) : dark_(dark), bright_(bright), low_(darkIsLow) {}
  bool update(Reading reading);
  bool state() const { return on_; }
 private:
  int dark_, bright_;
  bool low_, on_ = false;
};
class Identity {
 public:
  bool reset(const char* bootHex);
  bool next(char (&id)[65], uint64_t& sequence);
  bool exhausted() const { return sequence_ >= MAX_SEQUENCE; }
 private:
  char boot_[17] = {};
  uint64_t sequence_ = 0;
};
struct Entry {
  char payload[MAX_PAYLOAD + 1] = {};
  size_t size = 0;
  uint32_t collectedAt = 0;
};
bool serialize(Entry& out, const char* id, uint64_t sequence, const char* utc,
               Reading reading, bool led, uint32_t collectedAt);
struct Counters {
  uint32_t noUtc = 0, invalid = 0, overflow = 0, expired = 0, acceptedLocal = 0;
};
// Caller synchronizes access when sharing between tasks.
class Queue {
 public:
  void push(const Entry& entry);
  bool peek(uint32_t now, Entry& out);
  bool acceptIfHead(const Entry& sent);
  size_t size() const { return count_; }
  Counters counters;
 private:
  void pop();
  Entry entries_[CAPACITY];
  size_t head_ = 0, count_ = 0;
};
bool capture(Identity& identity, Queue& queue, const char* utc, Reading reading,
             bool led, uint32_t collectedAt);
}
