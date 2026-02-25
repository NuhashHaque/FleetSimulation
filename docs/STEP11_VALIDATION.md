# Step 11 Validation — Controlled Cutover + Cleanup

## Validation Plan
1. Confirm v2 service group is healthy.
2. Execute rollback script and verify legacy core still controls simulator.
3. Re-enable v2 service group.
4. Confirm trace/log pipeline and observability health after recovery.

## Executed Checks
- Ran `./scripts/cutover_rollback_legacy.sh`.
- Published direct MQTT command to simulator while v2 services were stopped.
- Verified telemetry still emitted and status changed, proving rollback continuity.
- Ran `./scripts/cutover_start_v2.sh`.
- Confirmed all v2 services are back up.
- Confirmed Prometheus scrape `up` metrics recovered.
- Sent traced API command after recovery and verified downstream processing.

## Evidence Snapshot
- During rollback drill, direct MQTT control returned telemetry:
	- `bus_id=BUS_03`
	- `status=RUNNING`
	- topic: `fleet/bus/BUS_03/telemetry`
- After re-enable, Prometheus `up` query returned `1` for:
	- `fastapi-gateway`
	- `mqtt-to-kafka-bridge`
	- `kafka-to-mqtt-bridge`
	- `timescaledb-audit-etl`
	- `timescaledb-telemetry-etl`
	- `timescaledb-event-etl`
- Post-recovery cutover sanity:
	- `trace_id=trace-step11-001` observed in `kafka-to-mqtt-bridge`
	- same trace observed in `timescaledb-audit-etl`

## Result
- Rollback path works.
- Recovery path works.
- Controlled cutover mechanics are now codified and repeatable.
