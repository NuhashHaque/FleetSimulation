# 🚌 Fleet Simulation — Control Room

A real-time bus fleet simulator built with **Python**, **MQTT (Mosquitto)**, and **Streamlit**, orchestrated via **Docker Compose**.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     Docker Network (fleet_net)           │
│                                                          │
│  ┌─────────────┐    MQTT 1883    ┌────────────────────┐  │
│  │  Simulator  │ ─────────────► │  Mosquitto Broker  │  │
│  │  (Python)   │ ◄─────────────  │  eclipse-mosquitto │  │
│  └─────────────┘   commands      └────────────────────┘  │
│                                         ▲  │             │
│                           telemetry     │  │ commands    │
│                                         │  ▼             │
│                                  ┌─────────────────┐     │
│                                  │   Dashboard     │     │
│                                  │  (Streamlit)    │     │
│                                  │  :8501          │     │
│                                  └─────────────────┘     │
└──────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
FleetSimulation/
├── docker-compose.yml
├── mosquitto/
│   ├── config/
│   │   └── mosquitto.conf       # broker config (port 1883, allow_anonymous)
│   ├── data/                    # broker persistence (auto-created)
│   └── log/                     # broker logs (auto-created)
├── simulator/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py                  # Bus state machine + LERP movement
└── dashboard/
    ├── Dockerfile
    ├── requirements.txt
    └── app.py                   # Streamlit UI + MQTT control
```

---

## Quick Start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.

### Run everything

```bash
cd FleetSimulation
docker compose up --build
```

Open **http://localhost:8501** in your browser.

> On first run Docker will pull/build images (~1–2 min).  
> On subsequent runs: `docker compose up` (no `--build` needed).

### Stop

```bash
docker compose down
```

---

## Development Phases

### Phase 1 — Broker
Mosquitto starts first.  The `healthcheck` in `docker-compose.yml` ensures the
Simulator and Dashboard only connect after the broker is fully ready.

```bash
# Verify broker is reachable from your host machine
mosquitto_sub -h localhost -t "fleet/bus/+/telemetry" -v
```

### Phase 2 — Simulator
Each bus runs in its own thread.  Send a `START` command manually to test:

```bash
mosquitto_pub -h localhost -t "fleet/bus/BUS_01/command" \
  -m '{"action": "START"}'
```

Watch telemetry:
```bash
mosquitto_sub -h localhost -t "fleet/bus/BUS_01/telemetry" -v
```

### Phase 3 — Dashboard
Open **http://localhost:8501**.  The four bus cards update live every second.
Progress bars show which leg (FORWARD / RETURN) is active.

### Phase 4 — Buttons
Click **▶ START** on any bus.  The bus in the Simulator container transitions
from `IDLE → RUNNING` and begins publishing moving coordinates.  
Click **⏹ STOP** — the Simulator resets that bus to Station 1 and `IDLE`.

---

## MQTT Messaging Schema

### Telemetry  `fleet/bus/{id}/telemetry`  (Simulator → Dashboard)

```json
{
  "bus_id":     "BUS_01",
  "status":     "RUNNING",
  "pos":        { "lat": 23.7982, "lon": 90.3872 },
  "speed":      45.5,
  "direction":  "FORWARD",
  "progress":   0.35,
  "trip_count": 2
}
```

| Field | Meaning |
|---|---|
| `status` | `IDLE` / `RUNNING` / `PAUSED` |
| `direction` | `FORWARD` (St.1→5) or `RETURN` (St.5→1) |
| `progress` | Fraction of the **current leg** completed (0 → 1) |
| `trip_count` | Increments only after completing the **full Return leg** |

### Command  `fleet/bus/{id}/command`  (Dashboard → Simulator)

```json
{ "action": "START | PAUSE | STOP" }
```

---

## State Machine

```
          ┌─────────┐
   STOP ──►  IDLE   ◄── STOP
          └────┬────┘
               │ START
               ▼
          ┌─────────┐
   PAUSE──► RUNNING │◄── START
          └────┬────┘
               │ PAUSE
               ▼
          ┌─────────┐
          │  PAUSED │
          └─────────┘
```

---

## Movement Physics

```
speed  ~ Uniform(30, 60) km/h   ← randomised per segment
Δt     = (speed_km/s) / segment_distance_km   ← fraction of segment per tick
pos    = lerp(p1, p2, seg_t)                  ← linear interpolation
```

Segment distance uses the **Haversine formula** for accurate km values on the
Earth's surface.

---

## Routes (Dhaka, Bangladesh)

| Bus | From | To |
|---|---|---|
| BUS_01 | Mirpur 10 | Motijheel |
| BUS_02 | Uttara | Gulshan 2 |
| BUS_03 | Demra | Sadarghat |
| BUS_04 | Dhanmondi 27 | New Market |
