# FleetSimulation Upgrade Plan (V3)

This document is the approved **implementation plan only** for upgrading the current system design.

## Non-Negotiable Constraints
1. No frontend UI code changes.
2. No simulator code changes.
3. Only architecture/infrastructure/backend flow changes.
4. Keep implementation simple, modular, and testable.

---

## 1) Target Architecture (No code changes in existing UI/simulator)

### Command flow
React UI -> Nginx -> FastAPI (`/api/command`) -> Kafka `fleet-commands` (key=`bus_id`) ->
- Consumer A: TimescaleDB audit ETL (`command_audit_log`)
- Consumer B: Kafka->MQTT outbound bridge -> Mosquitto topic `fleet/bus/{bus_id}/command` -> Simulator

### Telemetry flow
Simulator -> Mosquitto topic `fleet/bus/{bus_id}/telemetry` -> MQTT->Kafka bridge -> Kafka `raw-telemetry` (key=`bus_id`) ->
- Consumer A: FastAPI SSE stream -> Nginx -> React
- Consumer B: TimescaleDB telemetry ETL -> `telemetry` hypertable
- Consumer C: TimescaleDB event ETL -> `trip_logs` / `status_history`

---

## 2) Modular Project Layout (new components in separate folders)

Create these new folders (keep existing folders unchanged):

- `infra/`
  - `nginx/`
  - `kafka/`
  - `timescaledb/`
- `backend/fastapi-gateway/`
- `services/mqtt-to-kafka-bridge/`
- `services/kafka-to-mqtt-bridge/`
- `workers/timescaledb-audit-etl/`
- `workers/timescaledb-telemetry-etl/`
- `workers/timescaledb-event-etl/`
- `contracts/schemas/` (JSON/Avro schemas)
- `docs/` (runbooks, validation checklists)

Keep existing:
- `nextjs-dashboard/` (unchanged)
- `simulator/` (unchanged)
- `mosquitto/` (mostly unchanged)

---

## 3) Port Plan (simple and conflict-safe)

Use the following host ports:

| Component | Host Port | Container Port | Purpose |
|---|---:|---:|---|
| Next.js UI | 3000 | 3000 | Dashboard |
| Mosquitto MQTT TCP | 1884 | 1883 | Internal/debug MQTT clients |
| Mosquitto MQTT WS | 9002 | 9001 | Browser WebSocket path (existing) |
| Nginx HTTP | 8080 | 80 | API + SSE gateway (dev) |
| Nginx HTTPS | 8443 | 443 | TLS endpoint (dev/prod-like) |
| FastAPI | 8000 | 8000 | Internal API service |
| Kafka broker | 9094 | 9092 | Kafka client access from host |
| Schema Registry | 8081 | 8081 | Schema management |
| TimescaleDB | 5433 | 5432 | SQL and ETL writes |

Notes:
- Keep `3000`, `1884`, `9002` as-is to avoid UI breakage.
- Nginx will front FastAPI and SSE.
- Kafka and DB can be internal-only later; host mappings are for setup/testing stage.

---

## 4) Component Requirements (minimal setup)

### A) `backend/fastapi-gateway`
Responsibilities:
- `POST /api/command`
- Validate payload
- Add `command_id`, `trace_id`, timestamp
- Produce to Kafka `fleet-commands` with key=`bus_id`
- SSE endpoint for live telemetry fanout

Runtime deps:
- `fastapi`, `uvicorn`, `pydantic`
- `aiokafka`
- `orjson` (optional)

### B) `services/mqtt-to-kafka-bridge`
Responsibilities:
- Subscribe MQTT telemetry topics
- Validate + enrich payload
- Produce to Kafka `raw-telemetry` key=`bus_id`
- Send malformed messages to telemetry DLQ

Runtime deps:
- `paho-mqtt`
- Kafka client (`confluent-kafka` recommended)

### C) `services/kafka-to-mqtt-bridge`
Responsibilities:
- Consume `fleet-commands`
- Publish to MQTT command topics
- Preserve command ordering per bus

Runtime deps:
- Kafka client (`confluent-kafka`)
- `paho-mqtt`

### D) `workers/timescaledb-audit-etl`
Responsibilities:
- Consume `fleet-commands`
- Insert immutable command records into `command_audit_log`
- Idempotent insert via unique `command_id`

Runtime deps:
- Kafka client
- `psycopg`/`psycopg2`

### E) `workers/timescaledb-telemetry-etl`
Responsibilities:
- Consume `raw-telemetry`
- Insert all points to hypertable `telemetry`
- Idempotent handling via `telemetry_id`

Runtime deps:
- Kafka client
- Postgres client

### F) `workers/timescaledb-event-etl`
Responsibilities:
- Consume `raw-telemetry`
- Detect transitions (`status`, `trip_count`, etc.)
- Insert to `trip_logs` / `status_history`

Runtime deps:
- Kafka client
- Postgres client

---

## 5) Kafka Topic + Consumer Group Design

Topics:
- `fleet-commands` (4 partitions to start)
- `raw-telemetry` (4+ partitions)
- `fleet-commands-dlq`
- `raw-telemetry-dlq`

Rules:
- Key all messages by `bus_id`.
- This preserves per-bus ordering.
- At-least-once delivery + consumer dedupe.

Initial consumer groups:
- `timescaledb-audit-etl-group`
- `mqtt-outbound-bridge-group`
- `fastapi-sse-group`
- `timescaledb-telemetry-etl-group`
- `timescaledb-event-etl-group`

---

## 6) Data Contract Requirements

Every command message must include:
- `command_id` (idempotency)
- `trace_id`
- `bus_id`
- `action`
- `user_id` (or actor)
- `event_time`
- `schema_version`

Every telemetry message must include:
- `telemetry_id` (idempotency)
- `trace_id`
- `bus_id`
- core telemetry payload (status, pos, speed, direction, progress, etc.)
- `event_time`
- `schema_version`

Schema governance:
- Keep schema files in `contracts/schemas/`
- Enforce compatibility checks before deploy

---

## 7) Step-by-Step Implementation Plan (gated)

### Step 1 — Infra bootstrap only
- Add Kafka, Schema Registry, TimescaleDB, Nginx into compose.
- Do not reroute existing app traffic yet.

Validation:
- All services healthy
- Kafka produce/consume smoke test
- DB insert/select smoke test

### Step 2 — Contracts and topic setup
- Finalize schemas and versioning policy.
- Create topics + DLQs + partition settings.

Validation:
- Contract tests pass
- Key=`bus_id` routing verified
- DLQ test with malformed payload passes

### Step 3 — FastAPI command gateway
- Implement API producer path only.
- React traffic switch controlled via proxy path (no UI code changes).

Validation:
- `POST /api/command` returns fast
- Command appears in `fleet-commands`
- trace/idempotency fields present

### Step 4 — Kafka->MQTT command bridge
- Consume commands and publish to MQTT command topic.
- Keep simulator unchanged.

Validation:
- Simulator responds to commands as before
- Ordering preserved per bus
- Duplicate command replay does not double-apply

### Step 5 — Audit ETL worker
- Persist command audit to TimescaleDB.

Validation:
- Exactly-once logical insert by `command_id`
- Replay does not duplicate rows

### Step 6 — MQTT->Kafka telemetry bridge
- Ingest simulator telemetry from MQTT into Kafka `raw-telemetry`.

Validation:
- Per-bus ordering verified
- Throughput stable at expected tick rate
- Invalid payload -> telemetry DLQ

### Step 7 — FastAPI SSE fanout
- Consume `raw-telemetry` and stream to UI via Nginx.
- Add reconnect + last-known snapshot replay.

Validation:
- UI updates live through SSE path
- Reconnect works with snapshot replay
- No browser freeze

### Step 8 — TimescaleDB telemetry ETL
- Store all telemetry points in hypertable.

Validation:
- Write rate sustained
- Data completeness checks pass

### Step 9 — TimescaleDB event ETL
- Store only significant events/transitions.

Validation:
- Transition detection tests pass
- No duplicate event rows

### Step 10 — Observability hardening
- End-to-end `trace_id` across services.
- Metrics and alerts for lag, DLQ, errors, disconnects.

Validation:
- Alerts fire correctly in fault drills
- Recovery objectives achieved

### Step 11 — Controlled cutover and cleanup
- Gradually switch all traffic to new architecture.
- Keep rollback path during stabilization window.

Validation:
- Stable for agreed window
- Data reconciliation passes
- Legacy direct paths can be retired

---

## 8) Testing Strategy Per Step (must pass before next step)

For each step run:
1. Unit tests (component behavior)
2. Integration tests (cross-service contracts)
3. Failure tests (restart/retry/duplicate)
4. Load smoke tests (expected throughput)
5. Rollback test (can return to previous working state)

If any gate fails: stop, fix, retest, then continue.

---

## 9) Keep It Simple Rules (anti-spaghetti)

- One responsibility per service.
- Shared contracts in one place (`contracts/schemas/`).
- No hidden coupling between workers.
- Use explicit env vars, no magic constants.
- Add healthcheck endpoints for every new service.
- Log with `trace_id` in every component.
- Prefer small, composable modules over large files.

---

## 10) Definition of Done (Upgrade)

Upgrade is complete when:
- UI behaves same as today (no UI code changes).
- Simulator behaves same as today (no simulator code changes).
- Commands and telemetry flow through Kafka-based design.
- TimescaleDB has complete audit + telemetry + events.
- Ordering, idempotency, DLQ, replay, and observability requirements are all verified.
