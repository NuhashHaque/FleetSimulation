"""
bus.py
──────
Defines the ``Bus`` class — the core simulation entity.

Each Bus:
  • Holds its own state machine  (IDLE / RUNNING / PAUSED)
  • Runs a 1 Hz movement loop on a dedicated thread
  • Publishes telemetry JSON to  fleet/bus/{id}/telemetry
  • Reacts to commands           fleet/bus/{id}/command

Movement model
──────────────
The route has N waypoints → (N-1) segments.

  seg_idx  : index of the segment currently being traversed (0 … N-2)
  seg_t    : fractional progress through that segment [0.0, 1.0)
  direction: FORWARD (0 → N-1) or RETURN (N-1 → 0)

Overall leg-progress  p = (seg_idx + seg_t) / (N-1)  ∈ [0, 1]

At each tick:
  Δt = (speed_km_h / 3600) / segment_distance_km
  seg_t += Δt
  If seg_t ≥ 1.0 → arrived at next station, dwell, then flip if end-of-leg
"""

import json
import random
import threading
import time

import paho.mqtt.client as mqtt

from config import DWELL_TIME, TICK_RATE, TIME_SCALE
from physics import haversine_km, lerp_pos


class Bus:
    """
    Models a single bus with an internal state machine and 1 Hz movement loop.

    Parameters
    ----------
    bus_id    : str              Unique identifier (e.g. "BUS_01")
    waypoints : list[dict]       Ordered route waypoints  {"lat", "lon", "name"}
    client    : mqtt.Client      Shared MQTT client used to publish telemetry
    """

    def __init__(self, bus_id: str, waypoints: list, client: mqtt.Client):
        self.bus_id    = bus_id
        self.waypoints = waypoints
        self.n_segs    = len(waypoints) - 1   # 4 segments for 5 waypoints
        self.client    = client
        self._lock     = threading.Lock()
        self._reset()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _reset(self):
        """Reset to IDLE at Station 1.  Caller must NOT hold ``_lock``."""
        self.state      = "IDLE"
        self.direction  = "FORWARD"
        self.seg_idx    = 0
        self.seg_t      = 0.0
        self.speed      = 0.0
        self.trip_count = 0
        wp0 = self.waypoints[0]
        self.pos               = {"lat": wp0["lat"], "lon": wp0["lon"]}
        self.at_stop: bool     = False
        self.dwell_remaining: int = 0
        self.current_stop_name: str = wp0["name"]

    def _segment_endpoints(self) -> tuple[dict, dict]:
        """Return (p1, p2) for the current segment according to direction."""
        if self.direction == "FORWARD":
            return self.waypoints[self.seg_idx], self.waypoints[self.seg_idx + 1]
        # RETURN: seg_idx=0 → waypoints[4]→[3],  seg_idx=1 → [3]→[2], …
        hi = self.n_segs - self.seg_idx
        return self.waypoints[hi], self.waypoints[hi - 1]

    def _overall_progress(self) -> float:
        """Fractional progress through the current leg: 0.0 → 1.0."""
        return round((self.seg_idx + self.seg_t) / self.n_segs, 4)

    def _next_stop_name(self) -> str:
        """Return the name of the station the bus is heading towards."""
        if self.direction == "FORWARD":
            next_idx = self.seg_idx + 1
            if next_idx <= self.n_segs:
                return self.waypoints[next_idx]["name"]
        else:
            next_idx = self.n_segs - self.seg_idx - 1
            if next_idx >= 0:
                return self.waypoints[next_idx]["name"]
        return ""

    # ── Public API ────────────────────────────────────────────────────────────

    def handle_command(self, action: str):
        """
        Apply a dashboard command.

        Accepted actions
        ────────────────
        START   – IDLE / PAUSED  → RUNNING
        PAUSE   – RUNNING        → PAUSED
        STOP    – RUNNING/PAUSED → IDLE (reset to Station 1)
        RESTART – any state      → IDLE reset then immediately RUNNING
        """
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
            elif action == "RESTART":
                self._reset()
                self.state = "RUNNING"
                self.speed = random.uniform(30, 60)

    def step(self):
        """Advance the bus by one 1-second simulation tick."""
        with self._lock:
            if self.state != "RUNNING":
                return

            # ── Dwell at station ──────────────────────────────────────────────
            if self.at_stop:
                self.dwell_remaining -= 1
                if self.dwell_remaining <= 0:
                    self.at_stop = False
                return   # stay put until dwell expires

            p1, p2 = self._segment_endpoints()
            seg_dist_km  = haversine_km(p1, p2)
            speed_km_s   = self.speed / 3600.0
            # TIME_SCALE warps simulated time: dt jumps TIME_SCALE× larger per tick
            # while speed stays realistic (km/h) and TICK_RATE stays 1 Hz.
            dt           = (speed_km_s / seg_dist_km) * TIME_SCALE if seg_dist_km > 0 else 1.0
            self.seg_t  += dt

            if self.seg_t >= 1.0:
                # ── Arrived at the next station ───────────────────────────────
                self.seg_t   = 0.0
                self.seg_idx += 1

                if self.seg_idx >= self.n_segs:
                    # Completed this leg — flip direction
                    self.seg_idx = 0
                    if self.direction == "FORWARD":
                        self.direction = "RETURN"
                        wp = self.waypoints[self.n_segs]       # terminal station
                    else:
                        self.direction = "FORWARD"
                        self.trip_count += 1
                        wp = self.waypoints[0]                 # back to Station 1
                else:
                    # Arrived at an intermediate station
                    if self.direction == "FORWARD":
                        wp = self.waypoints[self.seg_idx]
                    else:
                        wp = self.waypoints[self.n_segs - self.seg_idx]

                self.pos               = {"lat": wp["lat"], "lon": wp["lon"]}
                self.current_stop_name = wp["name"]
                self.at_stop           = True
                self.dwell_remaining   = DWELL_TIME
                self.speed             = random.uniform(30, 60)
                print(f"[{self.bus_id}] AT STOP → {wp['name']}  ({self.direction})")

            else:
                # ── Mid-segment: interpolate position ─────────────────────────
                self.pos               = lerp_pos(p1, p2, self.seg_t)
                self.current_stop_name = ""
                # Subtle speed variation each tick (±3 km/h, clamped 30–60)
                self.speed = round(
                    max(30.0, min(60.0, self.speed + random.uniform(-3.0, 3.0))), 1
                )

    def telemetry(self) -> dict:
        """Return a snapshot of the current bus state as a telemetry dict."""
        with self._lock:
            return {
                "bus_id":       self.bus_id,
                "status":       self.state,
                "pos":          dict(self.pos),
                "speed":        round(self.speed, 1) if not self.at_stop else 0.0,
                "direction":    self.direction,
                "progress":     self._overall_progress(),
                "full_trips":   self.trip_count,
                "at_stop":      self.at_stop,
                "current_stop": self.current_stop_name if self.at_stop else None,
                "next_stop":    self._next_stop_name(),
            }

    # ── Thread entry point ────────────────────────────────────────────────────

    def run(self):
        """Bus thread entry point.  Runs indefinitely at TICK_RATE Hz."""
        print(f"[{self.bus_id}] Thread started.")
        while True:
            self.step()
            payload = json.dumps(self.telemetry())
            self.client.publish(f"fleet/bus/{self.bus_id}/telemetry", payload, qos=0)
            time.sleep(TICK_RATE)
