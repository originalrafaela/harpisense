#!/bin/sh
set -eu

INPUT_FILE="${1:-/mosquitto/config/lab-users.example}"
OUTPUT_FILE="${2:-/mosquitto/config/passwords}"

if [ ! -f "$INPUT_FILE" ]; then
  echo "Missing users file: $INPUT_FILE" >&2
  exit 1
fi

rm -f "$OUTPUT_FILE"
touch "$OUTPUT_FILE"
chmod 0600 "$OUTPUT_FILE"

while IFS= read -r line || [ -n "$line" ]; do
  case "$line" in
    ""|\#*) continue ;;
  esac

  username="${line%%:*}"
  password="${line#*:}"

  if [ -z "$username" ] || [ "$username" = "$password" ]; then
    echo "Invalid user line. Expected username:password" >&2
    exit 1
  fi

  mosquitto_passwd -b "$OUTPUT_FILE" "$username" "$password"
done < "$INPUT_FILE"

echo "Password file generated at $OUTPUT_FILE"
