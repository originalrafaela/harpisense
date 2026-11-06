#pragma once
#include "poste_core.h"
namespace hardware {
bool begin();
poste::Reading readLdr();
void commandLed(bool on);
}
