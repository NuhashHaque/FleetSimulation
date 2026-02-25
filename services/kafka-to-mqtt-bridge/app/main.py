import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any

import orjson
import paho.mqtt.client as mqtt
from aiokafka import AIOKafkaConsumer
from prometheus_client import Counter, Gauge, start_http_server

from app.config import (
    DEDUP_CACHE_SIZE,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_COMMAND_TOPIC,
    KAFKA_GROUP_ID,
    METRICS_PORT,
    MQTT_HOST,
    MQTT_PORT,
    MQTT_QOS,
)


MESSAGES_TOTAL = Counter("fleet_messages_processed_total", "Total messages processed")
PROCESSING_ERRORS_TOTAL = Counter("fleet_processing_errors_total", "Total processing errors")
DUPLICATES_TOTAL = Counter("fleet_duplicates_skipped_total", "Total duplicate messages skipped")
EVENT_AGE_SECONDS = Gauge("fleet_event_age_seconds", "Age of latest processed event in seconds")


class CommandDeduper:
    def __init__(self, max_size: int):
        self._max_size = max_size
        self._seen = set()
        self._order = deque()

    def seen(self, command_id: str) -> bool:
        return command_id in self._seen

    def add(self, command_id: str):
        if command_id in self._seen:
            return
        self._seen.add(command_id)
        self._order.append(command_id)
        if len(self._order) > self._max_size:
            old = self._order.popleft()
            self._seen.discard(old)


def extract_action(payload: dict[str, Any]) -> str:
    action = payload.get("action", "")
    if isinstance(action, str):
        return action.upper()
    return ""


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


async def run():
    start_http_server(METRICS_PORT)
    print(f"[kafka->mqtt] metrics server started on :{METRICS_PORT}")

    mqtt_client = mqtt.Client(client_id="kafka_to_mqtt_bridge", clean_session=True)
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    mqtt_client.loop_start()

    consumer = AIOKafkaConsumer(
        KAFKA_COMMAND_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=KAFKA_GROUP_ID,
        enable_auto_commit=False,
        auto_offset_reset="latest",
    )

    deduper = CommandDeduper(max_size=DEDUP_CACHE_SIZE)

    try:
        await consumer.start()
        print("[kafka->mqtt] bridge started")
        async for msg in consumer:
            try:
                payload = orjson.loads(msg.value)
                if not isinstance(payload, dict):
                    raise ValueError("payload must be JSON object")

                bus_id = payload.get("bus_id", "")
                if not isinstance(bus_id, str) or not bus_id:
                    raise ValueError("missing bus_id")

                command_id = payload.get("command_id", "")
                if isinstance(command_id, str) and command_id and deduper.seen(command_id):
                    print(f"[kafka->mqtt] duplicate command skipped: {command_id}")
                    DUPLICATES_TOTAL.inc()
                    await consumer.commit()
                    continue

                action = extract_action(payload)
                if not action:
                    raise ValueError("missing action")

                mqtt_topic = f"fleet/bus/{bus_id}/command"
                mqtt_payload = orjson.dumps({"action": action})
                info = mqtt_client.publish(mqtt_topic, mqtt_payload, qos=MQTT_QOS)
                info.wait_for_publish(timeout=5)

                if isinstance(command_id, str) and command_id:
                    deduper.add(command_id)

                update_event_age(payload)
                MESSAGES_TOTAL.inc()
                trace_id = payload.get("trace_id", "")
                print(f"[kafka->mqtt] trace_id={trace_id} published {action} to {mqtt_topic}")
                await consumer.commit()
            except Exception as exc:
                print(f"[kafka->mqtt] skipped message at offset {msg.offset}: {exc}")
                PROCESSING_ERRORS_TOTAL.inc()
                await consumer.commit()
    finally:
        await consumer.stop()
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


if __name__ == "__main__":
    asyncio.run(run())
