#!/bin/sh
set -eu

INPUT_FILE="${1:-/mosquitto/config/lab-users.example}"
OUTPUT_FILE="${2:-/mosquitto/config/passwords}"
MODE="${3:-create}"
BACKEND_CONSUMER_USER="${HARPISENSE_BACKEND_CONSUMER_USERNAME:-harpisense_backend_consumer}"

if [ ! -f "$INPUT_FILE" ]; then
  echo "Missing users file: $INPUT_FILE" >&2
  exit 1
fi

if [ "$MODE" != "create" ] && [ "$MODE" != "--force" ]; then
  echo "Invalid mode: $MODE. Use create or --force." >&2
  exit 1
fi

if [ -f "$OUTPUT_FILE" ] && [ "$MODE" != "--force" ]; then
  echo "Password file already exists: $OUTPUT_FILE" >&2
  echo "Refusing to overwrite silently. Re-run with --force to regenerate it." >&2
  exit 1
fi

if [ -z "${HARPISENSE_BACKEND_CONSUMER_PASSWORD:-}" ]; then
  echo "Missing HARPISENSE_BACKEND_CONSUMER_PASSWORD for $BACKEND_CONSUMER_USER" >&2
  exit 1
fi

: > "$OUTPUT_FILE"
chmod 0600 "$OUTPUT_FILE"

while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    ""|\#*) continue ;;
  esac

  username="${line%%:*}"
  password="${line#*:}"

  if [ -z "$username" ] || [ -z "$password" ] || [ "$username" = "$password" ]; then
    echo "Invalid user line. Expected username:password" >&2
    exit 1
  fi

  if [ "$username" = "$BACKEND_CONSUMER_USER" ]; then
    echo "$BACKEND_CONSUMER_USER must be provided via HARPISENSE_BACKEND_CONSUMER_PASSWORD, not $INPUT_FILE" >&2
    exit 1
  fi

  mosquitto_passwd -b "$OUTPUT_FILE" "$username" "$password"
done < "$INPUT_FILE"

mosquitto_passwd -b "$OUTPUT_FILE" "$BACKEND_CONSUMER_USER" "$HARPISENSE_BACKEND_CONSUMER_PASSWORD"

echo "Password file generated at $OUTPUT_FILE"
echo "Included externally supplied user: $BACKEND_CONSUMER_USER"
