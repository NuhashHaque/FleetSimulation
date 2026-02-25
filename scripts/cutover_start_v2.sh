#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

docker compose up -d \
  fastapi-gateway \
  kafka-to-mqtt-bridge \
  mqtt-to-kafka-bridge \
  timescaledb-audit-etl \
  timescaledb-telemetry-etl \
  timescaledb-event-etl \
  prometheus

echo "[cutover] v2 services started"
