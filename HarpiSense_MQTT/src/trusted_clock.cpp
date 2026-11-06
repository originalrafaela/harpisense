#include <Arduino.h>
#include <esp_timer.h>
#include <esp_sntp.h>
#include <time.h>
#include "settings.h"
#include "poste_core.h"
#include "trusted_clock.h"
namespace {
portMUX_TYPE clockMux=portMUX_INITIALIZER_UNLOCKED;
int64_t lastSyncUs=-1;
void synced(struct timeval*) {
  portENTER_CRITICAL(&clockMux); lastSyncUs=esp_timer_get_time(); portEXIT_CRITICAL(&clockMux);
}
}
namespace clock_source {
void begin() {
  if (!HS_NTP_SERVER[0]) return;
  sntp_set_time_sync_notification_cb(synced);
  configTime(0,0,HS_NTP_SERVER);
}
bool utc(char (&out)[21]) {
  portENTER_CRITICAL(&clockMux); int64_t sync=lastSyncUs; portEXIT_CRITICAL(&clockMux);
  if (!poste::freshSync(sync,esp_timer_get_time(),settings::CLOCK_TRUST_MS)) return false;
  time_t now=time(nullptr); struct tm utcTime;
  if (!gmtime_r(&now,&utcTime) || !strftime(out,sizeof(out),"%Y-%m-%dT%H:%M:%SZ",&utcTime)) return false;
  return poste::validUtc(out);
}
}
