#pragma once
#include "poste_core.h"
namespace communication {
bool begin();
bool poll();
bool publish(const poste::Entry& entry);
}
