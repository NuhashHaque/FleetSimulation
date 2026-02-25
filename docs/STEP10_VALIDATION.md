# Step 10 Validation — Observability Hardening

## Scope
- End-to-end `trace_id` visibility in logs.
- Prometheus metrics scraping for gateway, bridges, and ETL workers.
- Alert rules for service-down, DLQ spikes, lag, and processing errors.

## Implemented Components
- Prometheus service in compose.
- Metrics endpoint on FastAPI: `/metrics`.
- Metrics HTTP servers for worker/bridge services.
- Alert rules:
  - `ServiceDown`
  - `BridgeDLQSpiking`
  - `ConsumerLagHigh`
  - `WorkerProcessingErrors`

## Validation Commands Used
1. Rebuild + start observability services.
2. Query Prometheus `up` metric.
3. Send command with explicit `trace_id`.
4. Verify shared `trace_id` in downstream logs.
5. Inject malformed telemetry payload.
6. Query counters:
   - `mqtt_to_kafka_dlq_total`
   - `fleet_processing_errors_total`
7. Query active alerts from Prometheus API.

## Validation Results
- All scrape targets reported `up = 1`.
- Trace propagation verified across command pipeline logs (`kafka->mqtt`, `audit-etl`) with same `trace_id`.
- Malformed telemetry increased:
  - `mqtt_to_kafka_dlq_total`
  - `fleet_processing_errors_total` for `mqtt-to-kafka-bridge`
- Alerts fired successfully in drill:
  - `BridgeDLQSpiking`
  - `WorkerProcessingErrors`

## Access
- Prometheus UI: `http://localhost:9090`
- Prometheus Alerts API: `http://localhost:9090/api/v1/alerts`
