#!/bin/sh
set -eu
: "${POSTE01_PASSWORD:?missing POSTE01_PASSWORD}"
: "${POSTE02_PASSWORD:?missing POSTE02_PASSWORD}"
: "${READER_PASSWORD:?missing READER_PASSWORD}"
: "${AUTH_PASSWORD:?missing AUTH_PASSWORD}"
: "${COLLECTOR_PASSWORD:?missing COLLECTOR_PASSWORD}"
PASS=/mosquitto/data/passwd
rm -f "$PASS"
mosquitto_passwd -b -c "$PASS" poste01 "$POSTE01_PASSWORD"
mosquitto_passwd -b "$PASS" poste02 "$POSTE02_PASSWORD"
mosquitto_passwd -b "$PASS" reader_limited "$READER_PASSWORD"
mosquitto_passwd -b "$PASS" test_auth "$AUTH_PASSWORD"
mosquitto_passwd -b "$PASS" collector "$COLLECTOR_PASSWORD"
chmod 600 "$PASS"
exec mosquitto -c /mosquitto/config/mosquitto.conf
