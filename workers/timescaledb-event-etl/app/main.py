import asyncio
from dataclasses import dataclass
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
    KAFKA_GROUP_ID,
    KAFKA_TELEMETRY_TOPIC,
    METRICS_PORT,
)


MESSAGES_TOTAL = Counter("fleet_messages_processed_total", "Total messages processed")
PROCESSING_ERRORS_TOTAL = Counter("fleet_processing_errors_total", "Total processing errors")
DUPLICATES_TOTAL = Counter("fleet_duplicates_skipped_total", "Total duplicate messages skipped")
EVENT_AGE_SECONDS = Gauge("fleet_event_age_seconds", "Age of latest processed event in seconds")


@dataclass
class BusState:
    last_status: str
    last_full_trips: int
    last_event_time: datetime


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
            CREATE TABLE IF NOT EXISTS status_history (
                id BIGSERIAL PRIMARY KEY,
                telemetry_id TEXT NOT NULL UNIQUE,
                bus_id TEXT NOT NULL,
                from_status TEXT,
                to_status TEXT NOT NULL,
                event_time TIMESTAMPTZ NOT NULL,
                trace_id TEXT,
                metadata JSONB,
                ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS trip_logs (
                id BIGSERIAL PRIMARY KEY,
                telemetry_id TEXT NOT NULL UNIQUE,
                bus_id TEXT NOT NULL,
                trip_count INTEGER NOT NULL,
                event_time TIMESTAMPTZ NOT NULL,
                trace_id TEXT,
                metadata JSONB,
                ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (bus_id, trip_count)
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


def validate_telemetry(payload: dict[str, Any]) -> dict[str, Any]:
    required = ["telemetry_id", "event_time", "bus_id", "status", "full_trips"]
    for field in required:
        if field not in payload:
            raise ValueError(f"missing field: {field}")

    return {
        "telemetry_id": str(payload["telemetry_id"]),
        "event_time": parse_event_time(payload["event_time"]),
        "bus_id": str(payload["bus_id"]),
        "status": str(payload["status"]),
        "full_trips": int(payload["full_trips"]),
        "trace_id": str(payload["trace_id"]) if payload.get("trace_id") is not None else None,
        "metadata": payload.get("metadata", {}),
    }


def insert_status_event(conn, event: dict[str, Any]) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO status_history
            (telemetry_id, bus_id, from_status, to_status, event_time, trace_id, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (telemetry_id) DO NOTHING;
            """,
            (
                event["telemetry_id"],
                event["bus_id"],
                event["from_status"],
                event["to_status"],
                event["event_time"],
                event["trace_id"],
                Json(event.get("metadata", {})),
            ),
        )
        return cur.rowcount == 1


def insert_trip_event(conn, event: dict[str, Any]) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO trip_logs
            (telemetry_id, bus_id, trip_count, event_time, trace_id, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING;
            """,
            (
                event["telemetry_id"],
                event["bus_id"],
                event["trip_count"],
                event["event_time"],
                event["trace_id"],
                Json(event.get("metadata", {})),
            ),
        )
        return cur.rowcount == 1


async def run():
    start_http_server(METRICS_PORT)
    print(f"[event-etl] metrics server started on :{METRICS_PORT}")

    conn = get_connection()
    ensure_schema(conn)

    bus_state: dict[str, BusState] = {}

    consumer = AIOKafkaConsumer(
        KAFKA_TELEMETRY_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=KAFKA_GROUP_ID,
        enable_auto_commit=False,
        auto_offset_reset=KAFKA_AUTO_OFFSET_RESET,
    )

    try:
        await consumer.start()
        print("[event-etl] worker started")

        async for msg in consumer:
            try:
                payload = orjson.loads(msg.value)
                if not isinstance(payload, dict):
                    raise ValueError("payload must be object")

                event = validate_telemetry(payload)
                update_event_age(event["event_time"])
                MESSAGES_TOTAL.inc()
                bus_id = event["bus_id"]
                previous = bus_state.get(bus_id)
                trace_id = event.get("trace_id")

                if previous and event["event_time"] <= previous.last_event_time:
                    print(
                        f"[event-etl] trace_id={trace_id} stale telemetry skipped bus_id={bus_id} telemetry_id={event['telemetry_id']}"
                    )
                    DUPLICATES_TOTAL.inc()
                    await consumer.commit()
                    continue

                status_inserted = False
                trip_inserted = False

                if previous is not None and event["status"] != previous.last_status:
                    status_inserted = insert_status_event(
                        conn,
                        {
                            "telemetry_id": event["telemetry_id"],
                            "bus_id": bus_id,
                            "from_status": previous.last_status,
                            "to_status": event["status"],
                            "event_time": event["event_time"],
                            "trace_id": event["trace_id"],
                            "metadata": event["metadata"],
                        },
                    )

                if previous is not None and event["full_trips"] > previous.last_full_trips:
                    trip_inserted = insert_trip_event(
                        conn,
                        {
                            "telemetry_id": event["telemetry_id"],
                            "bus_id": bus_id,
                            "trip_count": event["full_trips"],
                            "event_time": event["event_time"],
                            "trace_id": event["trace_id"],
                            "metadata": event["metadata"],
                        },
                    )

                conn.commit()

                bus_state[bus_id] = BusState(
                    last_status=event["status"],
                    last_full_trips=event["full_trips"],
                    last_event_time=event["event_time"],
                )

                if status_inserted:
                    print(
                        f"[event-etl] trace_id={trace_id} status transition bus_id={bus_id} {previous.last_status}->{event['status']}"
                    )
                if trip_inserted:
                    print(
                        f"[event-etl] trace_id={trace_id} trip increment bus_id={bus_id} full_trips={event['full_trips']}"
                    )

                await consumer.commit()
            except Exception as exc:
                print(f"[event-etl] failed at offset {msg.offset}: {exc}")
                conn.rollback()
                PROCESSING_ERRORS_TOTAL.inc()
                await consumer.commit()
    finally:
        await consumer.stop()
        conn.close()


if __name__ == "__main__":
    asyncio.run(run())
