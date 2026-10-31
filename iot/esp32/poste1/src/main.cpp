#include <Arduino.h>
#include <esp_system.h>
#include <bootloader_random.h>
#include "poste_core.h"
#include "settings.h"
#include "hardware.h"
#include "trusted_clock.h"
#include "communication.h"
namespace {
poste::Queue samples;
poste::Identity identity;
poste::Hysteresis led(HS_DARK_THRESHOLD,HS_BRIGHT_THRESHOLD,HS_ADC_DARK_IS_LOW);
SemaphoreHandle_t queueMutex=nullptr;
bool hardwareReady=false;
bool rotateBoot() {
  // At startup only, before ADC/Wi-Fi use. Activate ESP32's entropy source.
  char boot[17]; uint32_t random[2];
  bootloader_random_enable();
  esp_fill_random(random,sizeof(random));
  bootloader_random_disable();
  snprintf(boot,sizeof(boot),"%08lx%08lx",static_cast<unsigned long>(random[0]),static_cast<unsigned long>(random[1]));
  return identity.reset(boot);
}
void networkTask(void*) {
  if (!communication::begin()) { Serial.println("network_closed: configuration/acceptance gates"); vTaskDelete(nullptr); return; }
  poste::Entry candidate; uint32_t lastAttempt=0;
  for (;;) {
    bool connected=communication::poll(); uint32_t now=millis();
    xSemaphoreTake(queueMutex,portMAX_DELAY);
    bool pending=samples.peek(now,candidate);
    xSemaphoreGive(queueMutex);
    if (connected && pending && static_cast<uint32_t>(now-lastAttempt)>=settings::PUBLISH_MS) {
      lastAttempt=now;
      for (size_t attempt=0; attempt<poste::CAPACITY && pending; ++attempt) {
        if (!communication::publish(candidate)) break;
        xSemaphoreTake(queueMutex,portMAX_DELAY);
        samples.acceptIfHead(candidate);
        pending=samples.peek(millis(),candidate);
        xSemaphoreGive(queueMutex);
      }
    }
    vTaskDelay(pdMS_TO_TICKS(20));
  }
}
}
void setup() {
  Serial.begin(115200);
  queueMutex=xSemaphoreCreateMutex();
  if (!queueMutex || !rotateBoot()) { Serial.println("startup_failed"); return; }
  hardwareReady=hardware::begin();
  if (!hardwareReady) { Serial.println("hardware_closed: confirm wiring/thresholds; GPIO untouched"); return; }
  if (xTaskCreate(networkTask,"poste1-net",8192,nullptr,1,nullptr)!=pdPASS) Serial.println("network_task_failed: offline only");
}
void loop() {
  static uint32_t lastSample=0,lastReport=0;
  if (!hardwareReady) { delay(1000); return; }
  uint32_t now=millis();
  if (static_cast<uint32_t>(now-lastSample)>=settings::SAMPLE_MS) {
    lastSample=now;
    poste::Reading reading=hardware::readLdr(); char utc[21];
    bool trusted=clock_source::utc(utc);
    hardware::commandLed(led.update(reading));
    Serial.printf("ldr_adc_raw=%d quality=%u led_commanded=%u utc_valid=%u\n",
      reading.quality==poste::Quality::Raw?reading.raw:-1,static_cast<unsigned>(reading.quality),led.state(),trusted);
    if (identity.exhausted()) { Serial.println("sequence_exhausted: reboot/new boot ID; RAM queue lost"); ESP.restart(); return; }
    xSemaphoreTake(queueMutex,portMAX_DELAY);
    poste::capture(identity,samples,trusted?utc:nullptr,reading,led.state(),now);
    xSemaphoreGive(queueMutex);
  }
  if (static_cast<uint32_t>(now-lastReport)>=30000) {
    lastReport=now;
    xSemaphoreTake(queueMutex,portMAX_DELAY);
    poste::Entry ignored; samples.peek(now,ignored);
    auto c=samples.counters; size_t pending=samples.size();
    xSemaphoreGive(queueMutex);
    Serial.printf("queue=%u no_utc=%lu invalid=%lu overflow=%lu expired=%lu accepted_local=%lu\n",
      static_cast<unsigned>(pending),static_cast<unsigned long>(c.noUtc),static_cast<unsigned long>(c.invalid),
      static_cast<unsigned long>(c.overflow),static_cast<unsigned long>(c.expired),static_cast<unsigned long>(c.acceptedLocal));
  }
  delay(5);
}
