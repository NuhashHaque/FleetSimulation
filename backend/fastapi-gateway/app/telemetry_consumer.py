import asyncio
from datetime import datetime, timezone

import orjson
from aiokafka import AIOKafkaConsumer

from app.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TELEMETRY_CONSUMER_GROUP,
    KAFKA_TELEMETRY_TOPIC,
)
from app.metrics import FLEET_EVENT_AGE_SECONDS, FLEET_MESSAGES_TOTAL, FLEET_PROCESSING_ERRORS_TOTAL
from app.telemetry_hub import TelemetryHub


def update_event_age(payload: dict):
    event_time = payload.get("event_time")
    if not isinstance(event_time, str):
        return
    try:
        parsed = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
    except ValueError:
        return
    age = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
    FLEET_EVENT_AGE_SECONDS.set(max(age, 0.0))


async def run_telemetry_consumer(hub: TelemetryHub, stop_event: asyncio.Event):
    consumer = AIOKafkaConsumer(
        KAFKA_TELEMETRY_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=KAFKA_TELEMETRY_CONSUMER_GROUP,
        enable_auto_commit=True,
        auto_offset_reset="latest",
    )

    await consumer.start()
    print("[fastapi-sse] telemetry consumer started")
    try:
        while not stop_event.is_set():
            batch = await consumer.getmany(timeout_ms=1000, max_records=200)
            for _tp, messages in batch.items():
                for msg in messages:
                    try:
                        payload = orjson.loads(msg.value)
                        if isinstance(payload, dict):
                            trace_id = payload.get("trace_id", "")
                            update_event_age(payload)
                            FLEET_MESSAGES_TOTAL.inc()
                            await hub.publish(payload)
                            print(f"[fastapi-sse] trace_id={trace_id} bus_id={payload.get('bus_id', '')} forwarded")
                    except Exception:
                        # Ignore malformed telemetry here; DLQ is handled upstream.
                        FLEET_PROCESSING_ERRORS_TOTAL.inc()
                        continue
    finally:
        await consumer.stop()
        print("[fastapi-sse] telemetry consumer stopped")
