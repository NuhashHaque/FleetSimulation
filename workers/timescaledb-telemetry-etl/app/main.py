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
    KAFKA_GROUP_ID,
    KAFKA_TELEMETRY_TOPIC,
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
        cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry (
                id BIGSERIAL,
                telemetry_id TEXT NOT NULL,
                event_time TIMESTAMPTZ NOT NULL,
                bus_id TEXT NOT NULL,
                status TEXT NOT NULL,
                lat DOUBLE PRECISION NOT NULL,
                lon DOUBLE PRECISION NOT NULL,
                speed DOUBLE PRECISION NOT NULL,
                direction TEXT NOT NULL,
                progress DOUBLE PRECISION NOT NULL,
                full_trips INTEGER NOT NULL,
                at_stop BOOLEAN NOT NULL,
                current_stop TEXT,
                next_stop TEXT,
                metadata JSONB,
                ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (event_time, id),
                UNIQUE (telemetry_id, event_time)
            );
            """
        )
        cur.execute(
            """
            SELECT create_hypertable('telemetry', 'event_time', if_not_exists => TRUE);
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
    required = [
        "telemetry_id",
        "event_time",
        "bus_id",
        "status",
        "pos",
        "speed",
        "direction",
        "progress",
        "full_trips",
        "at_stop",
        "next_stop",
    ]
    for field in required:
        if field not in payload:
            raise ValueError(f"missing field: {field}")

    pos = payload.get("pos")
    if not isinstance(pos, dict):
        raise ValueError("pos must be object")
    if "lat" not in pos or "lon" not in pos:
        raise ValueError("missing pos.lat/pos.lon")

    return {
        "telemetry_id": str(payload["telemetry_id"]),
        "event_time": parse_event_time(payload["event_time"]),
        "bus_id": str(payload["bus_id"]),
        "status": str(payload["status"]),
        "lat": float(pos["lat"]),
        "lon": float(pos["lon"]),
        "speed": float(payload["speed"]),
        "direction": str(payload["direction"]),
        "progress": float(payload["progress"]),
        "full_trips": int(payload["full_trips"]),
        "at_stop": bool(payload["at_stop"]),
        "current_stop": payload.get("current_stop"),
        "next_stop": str(payload["next_stop"]),
        "metadata": payload.get("metadata", {}),
    }


def insert_telemetry(conn, row: dict[str, Any]) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO telemetry (
                telemetry_id, event_time, bus_id, status,
                lat, lon, speed, direction, progress,
                full_trips, at_stop, current_stop, next_stop, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (telemetry_id, event_time) DO NOTHING;
            """,
            (
                row["telemetry_id"],
                row["event_time"],
                row["bus_id"],
                row["status"],
                row["lat"],
                row["lon"],
                row["speed"],
                row["direction"],
                row["progress"],
                row["full_trips"],
                row["at_stop"],
                row["current_stop"],
                row["next_stop"],
                Json(row["metadata"]),
            ),
        )
        inserted = cur.rowcount == 1
    conn.commit()
    return inserted


async def run():
    start_http_server(METRICS_PORT)
    print(f"[telemetry-etl] metrics server started on :{METRICS_PORT}")

    conn = get_connection()
    ensure_schema(conn)

    consumer = AIOKafkaConsumer(
        KAFKA_TELEMETRY_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=KAFKA_GROUP_ID,
        enable_auto_commit=False,
        auto_offset_reset=KAFKA_AUTO_OFFSET_RESET,
    )

    try:
        await consumer.start()
        print("[telemetry-etl] worker started")
        async for msg in consumer:
            try:
                payload = orjson.loads(msg.value)
                if not isinstance(payload, dict):
                    raise ValueError("payload must be object")

                row = validate_telemetry(payload)
                inserted = insert_telemetry(conn, row)
                update_event_age(row["event_time"])
                MESSAGES_TOTAL.inc()
                trace_id = payload.get("trace_id", "")
                if inserted:
                    print(f"[telemetry-etl] trace_id={trace_id} inserted telemetry_id={row['telemetry_id']}")
                else:
                    DUPLICATES_TOTAL.inc()
                    print(f"[telemetry-etl] trace_id={trace_id} duplicate skipped telemetry_id={row['telemetry_id']}")
                await consumer.commit()
            except Exception as exc:
                print(f"[telemetry-etl] failed at offset {msg.offset}: {exc}")
                PROCESSING_ERRORS_TOTAL.inc()
                await consumer.commit()
    finally:
        await consumer.stop()
        conn.close()


if __name__ == "__main__":
    asyncio.run(run())
