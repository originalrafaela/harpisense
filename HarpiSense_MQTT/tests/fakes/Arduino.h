#pragma once
#include <stdint.h>
extern uint32_t fakeMillis;
inline uint32_t millis() { return fakeMillis; }
template<class T> T min(T a,T b) { return a<b?a:b; }
struct SerialStub { template<class... T> void printf(const char*,T...) {} };
extern SerialStub Serial;
