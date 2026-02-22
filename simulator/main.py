"""
Fleet Simulator — main.py
=========================
Entry point.  Wires together the Bus objects, MQTT client, and threads.

Module layout
─────────────
  config.py        – env-driven constants (BROKER_HOST, TICK_RATE, …)
  routes.py        – ROUTES dict (4 buses × 5 waypoints each)
  physics.py       – haversine_km, lerp_pos
  bus.py           – Bus class  (state machine + 1 Hz movement loop)
  mqtt_handlers.py – on_connect, on_message, connect_with_retry
  main.py          – this file: wiring + process entry point

State machine summary
─────────────────────
  IDLE    →[START  ]→ RUNNING
  RUNNING →[PAUSE  ]→ PAUSED
  RUNNING →[STOP   ]→ IDLE   (reset to Station 1)
  PAUSED  →[START  ]→ RUNNING
  PAUSED  →[STOP   ]→ IDLE   (reset to Station 1)
  any     →[RESTART]→ RUNNING (hard reset to Station 1)
"""

import threading
import time

import paho.mqtt.client as mqtt

from bus import Bus
from config import BROKER_HOST, BROKER_PORT
from mqtt_handlers import connect_with_retry, on_connect, on_message
from routes import ROUTES


def main():
    # 1. Instantiate Bus objects (MQTT client back-filled below)
    buses: dict[str, Bus] = {
        bus_id: Bus(bus_id, waypoints, None)  # type: ignore[arg-type]
        for bus_id, waypoints in ROUTES.items()
    }

    # 2. Configure MQTT client
    client = mqtt.Client(
        client_id="fleet_simulator",
        userdata=buses,
        clean_session=True,
    )
    client.on_connect = on_connect
    client.on_message = on_message

    # Inject the real client reference into every bus
    for bus in buses.values():
        bus.client = client

    # 3. Connect to broker (with retry — simulator may start before Mosquitto)
    if not connect_with_retry(client, BROKER_HOST, BROKER_PORT):
        print("[Simulator] Could not reach broker. Exiting.")
        return

    client.loop_start()  # MQTT network thread

    # 4. One thread per bus
    for bus in buses.values():
        threading.Thread(
            target=bus.run,
            name=f"bus-{bus.bus_id}",
            daemon=True,
        ).start()

    print("[Simulator] All 4 bus threads running.  Waiting for commands …")

    # Keep the main thread alive indefinitely
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
