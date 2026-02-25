#!/usr/bin/env sh
set -eu

BOOTSTRAP_SERVER="${BOOTSTRAP_SERVER:-kafka:9092}"

create_topic() {
  topic="$1"
  partitions="$2"
  retention_ms="$3"

  echo "[topics] Ensuring topic: ${topic}"
  kafka-topics --bootstrap-server "$BOOTSTRAP_SERVER" \
    --create --if-not-exists \
    --topic "$topic" \
    --partitions "$partitions" \
    --replication-factor 1 \
    --config retention.ms="$retention_ms"
}

# Core topics
create_topic "fleet-commands" 4 604800000
create_topic "raw-telemetry" 4 172800000

# Dead-letter topics
create_topic "fleet-commands-dlq" 4 1209600000
create_topic "raw-telemetry-dlq" 4 1209600000

echo "[topics] Current topic list:"
kafka-topics --bootstrap-server "$BOOTSTRAP_SERVER" --list
