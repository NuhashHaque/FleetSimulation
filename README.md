# FleetSimulation (V2)

FleetSimulation is a Docker-based transit simulation platform with:
- MQTT simulator control + telemetry
- Kafka event backbone
- FastAPI command + SSE gateway
- TimescaleDB audit/telemetry/event ETL
- Prometheus observability + alerting

## Core URLs
- Next.js dashboard: http://localhost:3000
- API/SSE via Nginx: http://localhost:8080
- Prometheus: http://localhost:9090
- Kafka external listener: localhost:9094
- TimescaleDB: localhost:5433

## Bring up full stack
```bash
docker compose up --build -d
```

## Step 11 operational controls
### Enable/start v2 cutover services
```bash
./scripts/cutover_start_v2.sh
```

### Rollback to legacy-safe mode
```bash
./scripts/cutover_rollback_legacy.sh
```

Legacy-safe mode keeps these running:
- `mosquitto`
- `simulator`
- `nextjs-dashboard`
- `nginx`

## Runbooks
- Step 10 observability validation: `docs/STEP10_VALIDATION.md`
- Step 11 cutover runbook: `docs/STEP11_CUTOVER_RUNBOOK.md`
- Step 11 validation record: `docs/STEP11_VALIDATION.md`
- Overall plan: `UPGRADE_README.md`
