from __future__ import annotations

import signal
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import orjson
import paho.mqtt.client as mqtt
from confluent_kafka import Producer
from prometheus_client import Counter, Gauge, start_http_server

from app.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_DLQ_TOPIC,
    KAFKA_TELEMETRY_TOPIC,
    METRICS_PORT,
    MQTT_HOST,
    MQTT_PORT,
    MQTT_TOPIC,
    SERVICE_NAME,
)


MESSAGES_TOTAL = Counter("fleet_messages_processed_total", "Total messages processed")
PROCESSING_ERRORS_TOTAL = Counter("fleet_processing_errors_total", "Total processing errors")
DLQ_TOTAL = Counter("mqtt_to_kafka_dlq_total", "Total messages routed to telemetry DLQ")
MQTT_CONNECTED = Gauge("mqtt_connection_up", "MQTT connection state (1 up, 0 down)")
EVENT_AGE_SECONDS = Gauge("fleet_event_age_seconds", "Age of latest processed event in seconds")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def delivery_report(err, msg):
    if err is not None:
        print(f"[mqtt->kafka] delivery failed topic={msg.topic()}: {err}")


def validate_and_enrich(payload: dict[str, Any], topic: str) -> tuple[str, dict[str, Any]]:
    bus_id = payload.get("bus_id")
    if not isinstance(bus_id, str) or not bus_id:
        # fallback: parse bus id from topic fleet/bus/{id}/telemetry
        parts = topic.split("/")
        if len(parts) >= 4:
            bus_id = parts[2]
        else:
            raise ValueError("missing bus_id")

    status = payload.get("status")
    pos = payload.get("pos")
    if not isinstance(status, str):
        raise ValueError("missing status")
    if not isinstance(pos, dict) or "lat" not in pos or "lon" not in pos:
        raise ValueError("missing pos.lat/pos.lon")

    enriched = dict(payload)
    enriched.setdefault("schema_version", "telemetry.v1")
    enriched.setdefault("trace_id", f"trace-{uuid4()}")
    enriched.setdefault("telemetry_id", f"tel-{uuid4()}")
    enriched.setdefault("event_time", utc_now_iso())
    enriched.setdefault("metadata", {})
    if isinstance(enriched["metadata"], dict):
        enriched["metadata"].setdefault("source", SERVICE_NAME)

    return bus_id, enriched


def update_event_age(payload: dict[str, Any]):
    event_time = payload.get("event_time")
    if not isinstance(event_time, str):
        return
    try:
        parsed = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
    except ValueError:
        return
    age = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
    EVENT_AGE_SECONDS.set(max(age, 0.0))


class BridgeApp:
    def __init__(self):
        self._running = True
        self.kafka = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
        self.mqtt = mqtt.Client(client_id="mqtt_to_kafka_bridge", clean_session=True)
        self.mqtt.on_connect = self.on_connect
        self.mqtt.on_message = self.on_message

    def on_connect(self, client, _userdata, _flags, rc):
        print(f"[mqtt->kafka] mqtt connected rc={rc}")
        MQTT_CONNECTED.set(1)
        client.subscribe(MQTT_TOPIC)
        print(f"[mqtt->kafka] subscribed {MQTT_TOPIC}")

    def _produce_dlq(self, raw_payload: bytes, topic: str, error: str):
        event = {
            "schema_version": "dlq.v1",
            "trace_id": f"trace-{uuid4()}",
            "failed_topic": topic,
            "error_type": "validation_error",
            "error_message": error,
            "event_time": utc_now_iso(),
            "raw_payload": raw_payload.decode("utf-8", errors="replace"),
            "metadata": {"source": SERVICE_NAME},
        }
        self.kafka.produce(
            topic=KAFKA_DLQ_TOPIC,
            key="dlq".encode("utf-8"),
            value=orjson.dumps(event),
            on_delivery=delivery_report,
        )
        self.kafka.poll(0)
        DLQ_TOTAL.inc()

    def on_message(self, _client, _userdata, msg):
        try:
            payload = orjson.loads(msg.payload)
            if not isinstance(payload, dict):
                raise ValueError("payload is not JSON object")

            bus_id, enriched = validate_and_enrich(payload, msg.topic)
            trace_id = enriched.get("trace_id", "")
            self.kafka.produce(
                topic=KAFKA_TELEMETRY_TOPIC,
                key=bus_id.encode("utf-8"),
                value=orjson.dumps(enriched),
                on_delivery=delivery_report,
            )
            self.kafka.poll(0)
            update_event_age(enriched)
            MESSAGES_TOTAL.inc()
            print(f"[mqtt->kafka] trace_id={trace_id} bus_id={bus_id} forwarded")
        except Exception as exc:
            print(f"[mqtt->kafka] invalid payload on {msg.topic}: {exc}")
            self._produce_dlq(msg.payload, msg.topic, str(exc))
            PROCESSING_ERRORS_TOTAL.inc()

    def run(self):
        start_http_server(METRICS_PORT)
        print(f"[mqtt->kafka] metrics server started on :{METRICS_PORT}")
        self.mqtt.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        self.mqtt.loop_start()

        def stop_handler(_signum, _frame):
            self._running = False

        signal.signal(signal.SIGINT, stop_handler)
        signal.signal(signal.SIGTERM, stop_handler)

        print("[mqtt->kafka] bridge started")
        while self._running:
            self.kafka.poll(0.1)
            time.sleep(0.1)

        MQTT_CONNECTED.set(0)
        self.mqtt.loop_stop()
        self.mqtt.disconnect()
        self.kafka.flush(5)
        print("[mqtt->kafka] bridge stopped")


if __name__ == "__main__":
    BridgeApp().run()
