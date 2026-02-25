# Step 11 Runbook — Controlled Cutover + Cleanup

## Goal
Switch traffic to the v2 Kafka-based pipeline with a safe rollback path, then retire unused legacy paths only after stability gates pass.

## Safety Constraints
- No simulator code changes.
- No frontend code changes.
- Keep rollback command ready at all times.

## Service Groups
### Legacy core (must stay available)
- `mosquitto`
- `simulator`
- `nextjs-dashboard`
- `nginx`

### V2 cutover group
- `fastapi-gateway`
- `kafka-to-mqtt-bridge`
- `mqtt-to-kafka-bridge`
- `timescaledb-audit-etl`
- `timescaledb-telemetry-etl`
- `timescaledb-event-etl`
- `prometheus`

## Commands
### Start/enable v2 path
- `./scripts/cutover_start_v2.sh`

### Rollback to legacy path
- `./scripts/cutover_rollback_legacy.sh`

## Cutover Phases
1. **Shadow mode**
   - Keep legacy path active.
   - Run v2 services in parallel.
   - Confirm parity metrics and DB writes.

2. **Canary operations**
   - Route selected operator commands via `/api/command`.
   - Validate command-audit and telemetry-event consistency.

3. **Full v2 operations**
   - Use v2 command path for operational control.
   - Monitor alerts and lag dashboards continuously.

4. **Stabilization window**
   - Observe for agreed period with no critical alerts.
   - Execute reconciliation checks daily.

5. **Retirement**
   - Retire legacy direct-control path only after sign-off.

## Reconciliation Checks
- Command log growth in `command_audit_log`.
- Telemetry growth in `telemetry` hypertable.
- Event growth in `status_history` and `trip_logs`.
- No sustained alert firing for `ServiceDown` or `ConsumerLagHigh`.
