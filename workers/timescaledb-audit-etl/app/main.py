import asyncio
from datetime import datetime, timezone
from typing import Any

import orjson
import psycopg2
from aiokafka import AIOKafkaConsumer
from prometheus_client import Counter, Gauge, start_http_server
from psycopg2.extras import Json

from app.config import (
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    KAFKA_AUTO_OFFSET_RESET,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_COMMAND_TOPIC,
    KAFKA_GROUP_ID,
    METRICS_PORT,
)


MESSAGES_TOTAL = Counter("fleet_messages_processed_total", "Total messages processed")
PROCESSING_ERRORS_TOTAL = Counter("fleet_processing_errors_total", "Total processing errors")
DUPLICATES_TOTAL = Counter("fleet_duplicates_skipped_total", "Total duplicate messages skipped")
EVENT_AGE_SECONDS = Gauge("fleet_event_age_seconds", "Age of latest processed event in seconds")


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS command_audit_log (
                id BIGSERIAL PRIMARY KEY,
                command_id TEXT NOT NULL UNIQUE,
                trace_id TEXT NOT NULL,
                bus_id TEXT NOT NULL,
                action TEXT NOT NULL,
                user_id TEXT NOT NULL,
                event_time TIMESTAMPTZ NOT NULL,
                metadata JSONB,
                ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
    conn.commit()


def parse_event_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("event_time must be string")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def update_event_age(event_time: datetime):
    age = (datetime.now(timezone.utc) - event_time.astimezone(timezone.utc)).total_seconds()
    EVENT_AGE_SECONDS.set(max(age, 0.0))


def validate_command(payload: dict[str, Any]) -> dict[str, Any]:
    required = [
        "command_id",
        "trace_id",
        "bus_id",
        "action",
        "user_id",
        "event_time",
    ]
    for field in required:
        if field not in payload:
            raise ValueError(f"missing field: {field}")

    event_time = parse_event_time(payload["event_time"])

    return {
        "command_id": str(payload["command_id"]),
        "trace_id": str(payload["trace_id"]),
        "bus_id": str(payload["bus_id"]),
        "action": str(payload["action"]),
        "user_id": str(payload["user_id"]),
        "event_time": event_time,
        "metadata": payload.get("metadata", {}),
    }


def insert_command(conn, event: dict[str, Any]) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO command_audit_log
            (command_id, trace_id, bus_id, action, user_id, event_time, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (command_id) DO NOTHING;
            """,
            (
                event["command_id"],
                event["trace_id"],
                event["bus_id"],
                event["action"],
                event["user_id"],
                event["event_time"],
                Json(event["metadata"]),
            ),
        )
        inserted = cur.rowcount == 1
    conn.commit()
    return inserted


async def run():
    start_http_server(METRICS_PORT)
    print(f"[audit-etl] metrics server started on :{METRICS_PORT}")

    conn = get_connection()
    ensure_schema(conn)

    consumer = AIOKafkaConsumer(
        KAFKA_COMMAND_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=KAFKA_GROUP_ID,
        enable_auto_commit=False,
        auto_offset_reset=KAFKA_AUTO_OFFSET_RESET,
    )

    try:
        await consumer.start()
        print("[audit-etl] worker started")
        async for msg in consumer:
            try:
                payload = orjson.loads(msg.value)
                if not isinstance(payload, dict):
                    raise ValueError("payload must be object")

                event = validate_command(payload)
                inserted = insert_command(conn, event)
                update_event_age(event["event_time"])
                MESSAGES_TOTAL.inc()

                if inserted:
                    print(f"[audit-etl] trace_id={event['trace_id']} inserted command_id={event['command_id']}")
                else:
                    DUPLICATES_TOTAL.inc()
                    print(f"[audit-etl] trace_id={event['trace_id']} duplicate skipped command_id={event['command_id']}")

                await consumer.commit()
            except Exception as exc:
                print(f"[audit-etl] failed at offset {msg.offset}: {exc}")
                PROCESSING_ERRORS_TOTAL.inc()
                await consumer.commit()
    finally:
        await consumer.stop()
        conn.close()


if __name__ == "__main__":
    asyncio.run(run())
