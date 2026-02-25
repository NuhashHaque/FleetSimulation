#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

docker compose stop \
  fastapi-gateway \
  kafka-to-mqtt-bridge \
  mqtt-to-kafka-bridge \
  timescaledb-audit-etl \
  timescaledb-telemetry-etl \
  timescaledb-event-etl \
  prometheus

echo "[rollback] legacy path active (simulator + mosquitto + nextjs still running)"
