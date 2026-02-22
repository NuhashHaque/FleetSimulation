"""
Fleet Control Room — app.py
============================
Streamlit dashboard that:
  • Receives live telemetry from 4 buses via MQTT (background thread).
  • Renders real-time status cards with progress bars for each bus.
  • Sends START / PAUSE / STOP commands to the Simulator via MQTT buttons.

Architecture
────────────
  • A single MQTT client is created once at module load (singleton pattern).
    on_message() updates a module-level dict (_bus_data) protected by a Lock.
  • The main Streamlit render loop reads a snapshot of _bus_data, draws the UI,
    then calls time.sleep(1) + st.rerun() to refresh every second.
  • Button clicks call publish_command() immediately before the rerun.

Progress-bar logic
──────────────────
  progress ∈ [0, 1] always counts from the "departure end" of the current leg.
    FORWARD leg  → FORWARD bar fills 0 → 1  (Station 1 to Station 5)
    RETURN  leg  → RETURN  bar fills 0 → 1  (Station 5 back to Station 1)
  Both bars are shown simultaneously so the driver's position is unambiguous.
"""

import json
import os
import threading
import time

import paho.mqtt.client as mqtt
import streamlit as st

# ── Configuration ─────────────────────────────────────────────────────────────
BROKER_HOST: str = os.environ.get("BROKER_HOST", "localhost")
BROKER_PORT: int = int(os.environ.get("BROKER_PORT", 1883))

BUS_IDS = ["BUS_01", "BUS_02", "BUS_03", "BUS_04"]

# Human-readable route labels shown in the UI
ROUTE_LABELS = {
    "BUS_01": "Mirpur 10 ↔ Motijheel",
    "BUS_02": "Uttara ↔ Gulshan 2",
    "BUS_03": "Demra ↔ Sadarghat",
    "BUS_04": "Dhanmondi 27 ↔ New Market",
}

# ── Module-level shared state (written by MQTT thread, read by Streamlit) ─────
_lock = threading.Lock()

_bus_data: dict = {
    bus_id: {
        "bus_id":     bus_id,
        "status":     "IDLE",
        "pos":        {"lat": 0.0, "lon": 0.0},
        "speed":      0.0,
        "direction":  "FORWARD",
        "progress":   0.0,
        "trip_count": 0,
    }
    for bus_id in BUS_IDS
}

# ── MQTT singleton ─────────────────────────────────────────────────────────────
_mqtt_client: mqtt.Client = None          # type: ignore
_mqtt_ready: bool = False
_mqtt_init_lock = threading.Lock()


def _on_connect(client, userdata, flags, rc: int):
    if rc == 0:
        client.subscribe("fleet/bus/+/telemetry", qos=0)
        print(f"[Dashboard] MQTT connected and subscribed (broker={BROKER_HOST}:{BROKER_PORT})")
    else:
        print(f"[Dashboard] MQTT connect failed  rc={rc}")


def _on_message(client, userdata, msg):
    try:
        data: dict = json.loads(msg.payload.decode())
        bus_id: str = data.get("bus_id", "")
        if bus_id in BUS_IDS:
            with _lock:
                _bus_data[bus_id] = data
    except Exception as exc:
        print(f"[Dashboard] Message error: {exc}")


def _init_mqtt() -> mqtt.Client:
    """Create and start the MQTT client exactly once (module-level singleton)."""
    global _mqtt_client, _mqtt_ready
    with _mqtt_init_lock:
        if not _mqtt_ready:
            try:
                c = mqtt.Client(client_id="fleet_dashboard", clean_session=True)
                c.on_connect = _on_connect
                c.on_message = _on_message
                c.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
                c.loop_start()
                _mqtt_client = c
                _mqtt_ready = True
            except Exception as exc:
                print(f"[Dashboard] Could not connect to broker: {exc}")
    return _mqtt_client


def publish_command(bus_id: str, action: str):
    """Publish a command JSON to the bus's command topic."""
    client = _init_mqtt()
    if client:
        topic = f"fleet/bus/{bus_id}/command"
        client.publish(topic, json.dumps({"action": action}), qos=1)
        print(f"[Dashboard] → {topic}  action={action}")


# Ensure MQTT starts on the very first module load (before any button click)
_init_mqtt()

# ── Page config (must be the first Streamlit call) ────────────────────────────
st.set_page_config(
    page_title="Fleet Control Room",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🚌  Fleet Control Room")
broker_status = "🟢 Connected" if _mqtt_ready else "🔴 Disconnected"
st.caption(
    f"Broker `{BROKER_HOST}:{BROKER_PORT}` — {broker_status} "
    "| UI auto-refreshes every second"
)
st.divider()

# ── Snapshot shared state (single lock acquisition for the whole render) ───────
with _lock:
    snapshot: dict = {bus_id: dict(v) for bus_id, v in _bus_data.items()}

# ── Status styling helpers ─────────────────────────────────────────────────────
STATUS_ICON = {"IDLE": "🟡", "RUNNING": "🟢", "PAUSED": "🔴"}
STATUS_COLOR = {"IDLE": "orange", "RUNNING": "green", "PAUSED": "red"}

# ── Render one card per bus (2 columns × 2 rows) ──────────────────────────────
col_left, col_right = st.columns(2, gap="large")
col_map = {
    "BUS_01": col_left,
    "BUS_02": col_right,
    "BUS_03": col_left,
    "BUS_04": col_right,
}

for bus_id in BUS_IDS:
    data = snapshot[bus_id]
    status    = data["status"]
    direction = data["direction"]
    progress  = float(data["progress"])   # 0–1, within current leg
    speed     = data["speed"]
    trips     = data["trip_count"]
    lat       = data["pos"]["lat"]
    lon       = data["pos"]["lon"]

    with col_map[bus_id].container(border=True):
        # ── Title row ──────────────────────────────────────────────────────────
        icon = STATUS_ICON.get(status, "⚪")
        st.subheader(f"{icon}  {bus_id}")
        st.caption(f"Route: {ROUTE_LABELS[bus_id]}")

        # ── Metrics ────────────────────────────────────────────────────────────
        m1, m2, m3 = st.columns(3)
        m1.metric("Status",  status)
        m2.metric("Speed",   f"{speed:.1f} km/h")
        m3.metric("Trips ✓", trips)

        st.caption(f"📍 GPS  lat={lat:.5f}  lon={lon:.5f}")

        # ── Progress bars ──────────────────────────────────────────────────────
        # Two bars are shown: the active one fills based on current leg progress.
        # The inactive one stays at 0 so the driver's leg is immediately obvious.
        pb_fwd, pb_ret = st.columns(2)

        with pb_fwd:
            st.caption("➡️  FORWARD  (St.1 → St.5)")
            fwd_val = progress if direction == "FORWARD" else 0.0
            st.progress(fwd_val)

        with pb_ret:
            st.caption("⬅️  RETURN   (St.5 → St.1)")
            ret_val = progress if direction == "RETURN" else 0.0
            st.progress(ret_val)

        # ── Control buttons (Phase 4) ──────────────────────────────────────────
        st.write("")   # small spacer
        btn_start, btn_pause, btn_stop = st.columns(3)

        if btn_start.button(
            "▶ START", key=f"start_{bus_id}",
            use_container_width=True,
            type="primary" if status == "IDLE" else "secondary",
        ):
            publish_command(bus_id, "START")

        if btn_pause.button(
            "⏸ PAUSE", key=f"pause_{bus_id}",
            use_container_width=True,
            disabled=(status != "RUNNING"),
        ):
            publish_command(bus_id, "PAUSE")

        if btn_stop.button(
            "⏹ STOP", key=f"stop_{bus_id}",
            use_container_width=True,
            type="primary" if status in ("RUNNING", "PAUSED") else "secondary",
        ):
            publish_command(bus_id, "STOP")

# ── Footer ─────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Commands are published instantly.  "
    "Progress = fraction of current leg completed.  "
    "Trips increment only after completing the full Return leg."
)

# ── Auto-refresh every 1 second ───────────────────────────────────────────────
time.sleep(1)
st.rerun()
