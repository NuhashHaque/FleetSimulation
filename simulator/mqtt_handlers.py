"""
mqtt_handlers.py
────────────────
MQTT lifecycle callbacks and connection helper used by the simulator.

Functions
─────────
on_connect(client, userdata, flags, rc)
    Subscribes every bus to its command topic on broker connection.

on_message(client, userdata, msg)
    Routes an incoming command message to the correct Bus instance.

connect_with_retry(client, host, port, retries) → bool
    Attempts to connect to the broker with exponential-style delay.
    Returns True on success, False if all retries are exhausted.
    (The simulator may start before Mosquitto is ready, so retrying is essential.)
"""

import json
import time

import paho.mqtt.client as mqtt


def on_connect(client: mqtt.Client, userdata: dict, flags, rc: int):
    """Subscribe every bus to its command topic after a successful connection."""
    buses: dict = userdata
    print(f"[Simulator] Broker connected (rc={rc})")
    for bus_id in buses:
        topic = f"fleet/bus/{bus_id}/command"
        client.subscribe(topic)
        print(f"[Simulator] Subscribed → {topic}")


def on_message(client: mqtt.Client, userdata: dict, msg: mqtt.MQTTMessage):
    """
    Dispatch an incoming command to the correct Bus.

    Expected topic  : fleet/bus/{BUS_ID}/command
    Expected payload: {"action": "START"|"PAUSE"|"STOP"|"RESTART"}
    """
    buses: dict = userdata
    parts = msg.topic.split("/")
    if len(parts) < 4:
        return
    bus_id = parts[2]
    try:
        payload = json.loads(msg.payload.decode())
        action  = payload.get("action", "").upper()
        if bus_id in buses and action:
            buses[bus_id].handle_command(action)
    except json.JSONDecodeError as exc:
        print(f"[Simulator] Bad JSON on {msg.topic}: {exc}")


def connect_with_retry(
    client: mqtt.Client,
    host: str,
    port: int,
    retries: int = 20,
) -> bool:
    """
    Try to connect to the MQTT broker, retrying on failure.

    Parameters
    ----------
    client  : mqtt.Client  Already-configured client instance
    host    : str          Broker hostname or IP
    port    : int          Broker TCP port
    retries : int          Maximum number of attempts (default 20)

    Returns
    -------
    bool  True on success, False after all retries are exhausted.
    """
    for attempt in range(1, retries + 1):
        try:
            client.connect(host, port, keepalive=60)
            return True
        except Exception as exc:
            print(f"[Simulator] Attempt {attempt}/{retries} failed: {exc}  (retry in 5 s)")
            time.sleep(5)
    return False
