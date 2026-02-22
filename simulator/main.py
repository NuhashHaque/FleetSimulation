"""
Fleet Simulator — main.py
=========================
Spawns one thread per bus.  Each thread runs a 1 Hz loop that:
  1. Advances the bus position using Haversine + LERP interpolation.
  2. Publishes a telemetry JSON to  fleet/bus/{id}/telemetry.

Bus state is controlled by commands received on fleet/bus/{id}/command.

State machine
─────────────
  IDLE    →[START]→  RUNNING
  RUNNING →[PAUSE]→  PAUSED
  RUNNING →[STOP ]→  IDLE  (reset to Station 1)
  PAUSED  →[START]→  RUNNING
  PAUSED  →[STOP ]→  IDLE  (reset to Station 1)
"""

import json
import math
import os
import random
import threading
import time

import paho.mqtt.client as mqtt

# ── Configuration ─────────────────────────────────────────────────────────────
BROKER_HOST: str = os.environ.get("BROKER_HOST", "localhost")
BROKER_PORT: int = int(os.environ.get("BROKER_PORT", 1883))
TICK_RATE: float = 1.0  # seconds (1 Hz)

# ── Route Definitions (Dhaka, Bangladesh) ─────────────────────────────────────
# 4 routes × 5 waypoints each.  Real-world corridors for authenticity.
ROUTES: dict = {
    "BUS_01": [  # Mirpur → Motijheel corridor
        {"lat": 23.8223, "lon": 90.3654},  # St.1  Mirpur 10
        {"lat": 23.8100, "lon": 90.3750},  # St.2  Mirpur 2
        {"lat": 23.7982, "lon": 90.3872},  # St.3  Shyamoli
        {"lat": 23.7806, "lon": 90.3993},  # St.4  Farmgate
        {"lat": 23.7279, "lon": 90.4188},  # St.5  Motijheel
    ],
    "BUS_02": [  # Uttara → Gulshan corridor
        {"lat": 23.8759, "lon": 90.3795},  # St.1  Uttara
        {"lat": 23.8469, "lon": 90.3944},  # St.2  Airport
        {"lat": 23.8233, "lon": 90.4152},  # St.3  Banani
        {"lat": 23.7937, "lon": 90.4066},  # St.4  Gulshan 1
        {"lat": 23.7808, "lon": 90.4152},  # St.5  Gulshan 2
    ],
    "BUS_03": [  # Demra → Sadarghat corridor
        {"lat": 23.7208, "lon": 90.4800},  # St.1  Demra
        {"lat": 23.7150, "lon": 90.4600},  # St.2  Jatrabari
        {"lat": 23.7100, "lon": 90.4400},  # St.3  Postogola
        {"lat": 23.7192, "lon": 90.4200},  # St.4  Sutrapur
        {"lat": 23.7185, "lon": 90.4076},  # St.5  Sadarghat
    ],
    "BUS_04": [  # Dhanmondi → New Market corridor
        {"lat": 23.7461, "lon": 90.3742},  # St.1  Dhanmondi 27
        {"lat": 23.7524, "lon": 90.3804},  # St.2  Dhanmondi 15
        {"lat": 23.7590, "lon": 90.3880},  # St.3  Science Lab
        {"lat": 23.7640, "lon": 90.3950},  # St.4  Elephant Road
        {"lat": 23.7820, "lon": 90.4050},  # St.5  New Market
    ],
}


# ── Physics Helpers ───────────────────────────────────────────────────────────

def haversine_km(p1: dict, p2: dict) -> float:
    """Return the great-circle distance in km between two lat/lon points."""
    R = 6371.0
    lat1, lat2 = math.radians(p1["lat"]), math.radians(p2["lat"])
    dlat = lat2 - lat1
    dlon = math.radians(p2["lon"] - p1["lon"])
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def lerp_pos(p1: dict, p2: dict, t: float) -> dict:
    """
    Linear interpolation between two GPS points.

    pos = p1 + t * (p2 - p1),  t ∈ [0, 1]
    """
    return {
        "lat": round(p1["lat"] + t * (p2["lat"] - p1["lat"]), 6),
        "lon": round(p1["lon"] + t * (p2["lon"] - p1["lon"]), 6),
    }


# ── Bus Class (State Machine + Movement) ─────────────────────────────────────

class Bus:
    """
    Models a single bus with an internal state machine and 1 Hz movement loop.

    Movement model
    ──────────────
    The route has N waypoints → (N-1) segments.
    seg_idx  : index of the segment we are currently traversing (0 … N-2)
    seg_t    : fractional progress through that segment [0.0, 1.0)
    direction: FORWARD (seg 0→…→N-2) or RETURN (seg 0→…→N-2 traversed backwards)

    Overall leg-progress  p = (seg_idx + seg_t) / (N-1)  ∈ [0, 1]

    At each tick:
      Δt = (speed_km_h / 3600) / segment_distance_km
      seg_t += Δt
      If seg_t ≥ 1.0 → advance to next station, pick new random speed
    """

    def __init__(self, bus_id: str, waypoints: list, client: mqtt.Client):
        self.bus_id = bus_id
        self.waypoints = waypoints
        self.n_segs = len(waypoints) - 1       # 4 segments for 5 waypoints
        self.client = client
        self._lock = threading.Lock()
        self._reset()

    # ── State helpers ─────────────────────────────────────────────────────────

    def _reset(self):
        """Reset to IDLE at Station 1 (no lock required — caller must hold it)."""
        self.state = "IDLE"
        self.direction = "FORWARD"
        self.seg_idx = 0
        self.seg_t = 0.0
        self.speed = 0.0
        self.trip_count = 0
        self.pos = dict(self.waypoints[0])

    def _segment_endpoints(self):
        """Return (p1, p2) for the current segment according to direction."""
        if self.direction == "FORWARD":
            return self.waypoints[self.seg_idx], self.waypoints[self.seg_idx + 1]
        else:
            # RETURN: seg_idx=0 → waypoints[4]→[3],  seg_idx=1 → [3]→[2], …
            hi = self.n_segs - self.seg_idx
            return self.waypoints[hi], self.waypoints[hi - 1]

    def _overall_progress(self) -> float:
        """Fractional progress through the current leg: 0.0 (station 1-side) → 1.0."""
        return round((self.seg_idx + self.seg_t) / self.n_segs, 4)

    # ── Public API (called from MQTT thread) ──────────────────────────────────

    def handle_command(self, action: str):
        """Apply a START / PAUSE / STOP command from the dashboard."""
        with self._lock:
            print(f"[{self.bus_id}] CMD={action}  state={self.state}")
            if action == "START":
                if self.state == "IDLE":
                    self.state = "RUNNING"
                    self.speed = random.uniform(30, 60)
                elif self.state == "PAUSED":
                    self.state = "RUNNING"
            elif action == "PAUSE":
                if self.state == "RUNNING":
                    self.state = "PAUSED"
            elif action == "STOP":
                if self.state in ("RUNNING", "PAUSED"):
                    self._reset()

    # ── Movement tick (called every second from bus thread) ───────────────────

    def step(self):
        """Advance the bus by one 1-second tick."""
        with self._lock:
            if self.state != "RUNNING":
                return

            p1, p2 = self._segment_endpoints()
            seg_dist_km = haversine_km(p1, p2)

            # How far do we travel in 1 second at current speed?
            speed_km_s = self.speed / 3600.0
            dt = (speed_km_s / seg_dist_km) if seg_dist_km > 0 else 1.0

            self.seg_t += dt

            if self.seg_t >= 1.0:
                # ── Arrived at the next station ───────────────────────────────
                self.seg_t = 0.0
                self.seg_idx += 1

                if self.seg_idx >= self.n_segs:
                    # Completed this leg — flip direction
                    self.seg_idx = 0
                    if self.direction == "FORWARD":
                        self.direction = "RETURN"
                        self.pos = dict(self.waypoints[self.n_segs])   # last station
                    else:
                        self.direction = "FORWARD"
                        self.trip_count += 1
                        self.pos = dict(self.waypoints[0])             # back to station 1
                else:
                    # Arrived at an intermediate station
                    if self.direction == "FORWARD":
                        self.pos = dict(self.waypoints[self.seg_idx])
                    else:
                        self.pos = dict(self.waypoints[self.n_segs - self.seg_idx])

                # Pick a fresh random speed for the next segment
                self.speed = random.uniform(30, 60)
            else:
                # ── Mid-segment: interpolate position ────────────────────────
                self.pos = lerp_pos(p1, p2, self.seg_t)

    def telemetry(self) -> dict:
        """Return a snapshot of bus state as the standard telemetry JSON."""
        with self._lock:
            return {
                "bus_id":     self.bus_id,
                "status":     self.state,
                "pos":        dict(self.pos),
                "speed":      round(self.speed, 1),
                "direction":  self.direction,
                "progress":   self._overall_progress(),
                "trip_count": self.trip_count,
            }

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        """Bus thread entry point.  Runs forever at TICK_RATE Hz."""
        print(f"[{self.bus_id}] Thread started.")
        while True:
            self.step()
            payload = json.dumps(self.telemetry())
            self.client.publish(f"fleet/bus/{self.bus_id}/telemetry", payload, qos=0)
            time.sleep(TICK_RATE)


# ── MQTT Callbacks ────────────────────────────────────────────────────────────

def on_connect(client, userdata, flags, rc):
    buses: dict = userdata
    print(f"[Simulator] Broker connected (rc={rc})")
    for bus_id in buses:
        topic = f"fleet/bus/{bus_id}/command"
        client.subscribe(topic)
        print(f"[Simulator] Subscribed → {topic}")


def on_message(client, userdata, msg):
    buses: dict = userdata
    # Topic: fleet/bus/{BUS_ID}/command
    parts = msg.topic.split("/")
    if len(parts) < 4:
        return
    bus_id = parts[2]
    try:
        payload = json.loads(msg.payload.decode())
        action = payload.get("action", "").upper()
        if bus_id in buses and action:
            buses[bus_id].handle_command(action)
    except json.JSONDecodeError as exc:
        print(f"[Simulator] Bad JSON on {msg.topic}: {exc}")


# ── Connection Helper ─────────────────────────────────────────────────────────

def connect_with_retry(client: mqtt.Client, host: str, port: int, retries: int = 20) -> bool:
    """Retry broker connection — important because the simulator may start before mosquitto."""
    for attempt in range(1, retries + 1):
        try:
            client.connect(host, port, keepalive=60)
            return True
        except Exception as exc:
            print(f"[Simulator] Attempt {attempt}/{retries} failed: {exc}  (retry in 5 s)")
            time.sleep(5)
    return False


# ── Entry Point ───────────────────────────────────────────────────────────────

def main():
    # 1. Build the bus objects (client reference filled in after MQTT setup)
    dummy_client = None  # type: ignore
    buses = {
        bus_id: Bus(bus_id, waypoints, dummy_client)
        for bus_id, waypoints in ROUTES.items()
    }

    # 2. Set up MQTT client
    client = mqtt.Client(
        client_id="fleet_simulator",
        userdata=buses,
        clean_session=True,
    )
    client.on_connect = on_connect
    client.on_message = on_message

    # Back-fill the client reference into every bus
    for bus in buses.values():
        bus.client = client

    # 3. Connect to broker
    if not connect_with_retry(client, BROKER_HOST, BROKER_PORT):
        print("[Simulator] Could not reach broker. Exiting.")
        return

    client.loop_start()   # starts the MQTT network thread

    # 4. Start one thread per bus
    for bus in buses.values():
        t = threading.Thread(
            target=bus.run,
            name=f"bus-{bus.bus_id}",
            daemon=True,
        )
        t.start()

    print("[Simulator] All 4 bus threads running.  Waiting for commands …")

    # Keep the main thread alive
    try:
        while True:
            time.sleep(30)
    except KeyboardInterrupt:
        print("[Simulator] Shutting down.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
