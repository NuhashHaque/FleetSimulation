import asyncio

import orjson
from aiokafka import AIOKafkaConsumer

from app.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TELEMETRY_CONSUMER_GROUP,
    KAFKA_TELEMETRY_TOPIC,
)
from app.telemetry_hub import TelemetryHub


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
                            await hub.publish(payload)
                    except Exception:
                        # Ignore malformed telemetry here; DLQ is handled upstream.
                        continue
    finally:
        await consumer.stop()
        print("[fastapi-sse] telemetry consumer stopped")
