# Schemas (Step 2)

This folder contains versioned message contracts for FleetSimulation V2.

## Contracts
- `command.v1.schema.json`
- `telemetry.v1.schema.json`
- `dlq.v1.schema.json`

## Versioning Rules
1. Do not modify existing versions in-place.
2. Add new schema files for breaking changes (e.g. `command.v2.schema.json`).
3. Keep backward compatibility for additive non-breaking changes.
4. All events must carry `schema_version` and `trace_id`.

## Idempotency Fields
- Commands: `command_id`
- Telemetry: `telemetry_id`

## Example Payloads
- `examples.command.valid.json`
- `examples.telemetry.valid.json`
- `examples.telemetry.invalid.json`
