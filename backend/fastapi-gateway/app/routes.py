from datetime import datetime, timezone
from uuid import uuid4
import asyncio

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
import orjson
import psycopg2
from psycopg2.extras import RealDictCursor

from app.config import (
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    KAFKA_COMMAND_TOPIC,
    SERVICE_NAME,
)
from app.metrics import SSE_CLIENTS_CONNECTED, render_metrics
from app.models import CommandAcceptedResponse, CommandRequest

router = APIRouter()


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


@router.get("/health")
async def health():
    return {"status": "ok", "service": SERVICE_NAME}


@router.get("/api/health")
async def api_health():
    return {"status": "ok", "service": SERVICE_NAME}


@router.get("/metrics")
async def metrics():
    payload, content_type = render_metrics()
    return Response(content=payload, media_type=content_type)


@router.get("/api/ops/telemetry/latest")
async def ops_telemetry_latest(limit: int = 4):
    safe_limit = max(1, min(limit, 100))
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM (
                    SELECT DISTINCT ON (bus_id)
                        bus_id,
                        telemetry_id,
                        event_time,
                        status,
                        lat,
                        lon,
                        speed,
                        direction,
                        progress,
                        full_trips,
                        at_stop,
                        current_stop,
                        next_stop
                    FROM telemetry
                    ORDER BY bus_id, event_time DESC
                ) latest
                ORDER BY event_time DESC
                LIMIT %s;
                """,
                (safe_limit,),
            )
            rows = cur.fetchall()
        return {"count": len(rows), "items": rows}
    finally:
        conn.close()


@router.get("/api/ops/telemetry/history")
async def ops_telemetry_history(bus_id: str | None = None, limit: int = 100):
    safe_limit = max(1, min(limit, 500))
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if bus_id:
                cur.execute(
                    """
                    SELECT
                        bus_id,
                        telemetry_id,
                        event_time,
                        status,
                        lat,
                        lon,
                        speed,
                        direction,
                        progress,
                        full_trips,
                        at_stop,
                        current_stop,
                        next_stop
                    FROM telemetry
                    WHERE bus_id = %s
                    ORDER BY event_time DESC
                    LIMIT %s;
                    """,
                    (bus_id, safe_limit),
                )
            else:
                cur.execute(
                    """
                    SELECT
                        bus_id,
                        telemetry_id,
                        event_time,
                        status,
                        lat,
                        lon,
                        speed,
                        direction,
                        progress,
                        full_trips,
                        at_stop,
                        current_stop,
                        next_stop
                    FROM telemetry
                    ORDER BY event_time DESC
                    LIMIT %s;
                    """,
                    (safe_limit,),
                )
            rows = cur.fetchall()
        return {"count": len(rows), "items": rows}
    finally:
        conn.close()


@router.get("/api/ops/events")
async def ops_events(bus_id: str | None = None, limit: int = 100):
    safe_limit = max(1, min(limit, 500))
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if bus_id:
                cur.execute(
                    """
                    SELECT *
                    FROM (
                        SELECT
                            event_time,
                            bus_id,
                            'status_transition' AS event_type,
                            telemetry_id,
                            from_status,
                            to_status,
                            NULL::INTEGER AS trip_count
                        FROM status_history
                        WHERE bus_id = %s
                        UNION ALL
                        SELECT
                            event_time,
                            bus_id,
                            'trip_increment' AS event_type,
                            telemetry_id,
                            NULL::TEXT AS from_status,
                            NULL::TEXT AS to_status,
                            trip_count
                        FROM trip_logs
                        WHERE bus_id = %s
                    ) e
                    ORDER BY event_time DESC
                    LIMIT %s;
                    """,
                    (bus_id, bus_id, safe_limit),
                )
            else:
                cur.execute(
                    """
                    SELECT *
                    FROM (
                        SELECT
                            event_time,
                            bus_id,
                            'status_transition' AS event_type,
                            telemetry_id,
                            from_status,
                            to_status,
                            NULL::INTEGER AS trip_count
                        FROM status_history
                        UNION ALL
                        SELECT
                            event_time,
                            bus_id,
                            'trip_increment' AS event_type,
                            telemetry_id,
                            NULL::TEXT AS from_status,
                            NULL::TEXT AS to_status,
                            trip_count
                        FROM trip_logs
                    ) e
                    ORDER BY event_time DESC
                    LIMIT %s;
                    """,
                    (safe_limit,),
                )
            rows = cur.fetchall()
        return {"count": len(rows), "items": rows}
    finally:
        conn.close()




@router.post("/api/command", response_model=CommandAcceptedResponse)
async def command(request: Request, body: CommandRequest):
    producer = request.app.state.command_producer
    if producer is None:
        raise HTTPException(status_code=503, detail="Kafka producer not ready")

    request_trace_id = getattr(request.state, "trace_id", None)
    trace_id = body.trace_id or request_trace_id or f"trace-{uuid4()}"
    command_id = body.command_id or f"cmd-{uuid4()}"

    event = {
        "schema_version": "command.v1",
        "trace_id": trace_id,
        "command_id": command_id,
        "event_time": datetime.now(timezone.utc).isoformat(),
        "bus_id": body.bus_id,
        "action": body.action,
        "user_id": body.user_id,
        "metadata": {
            "source": SERVICE_NAME,
        },
    }

    await producer.publish(KAFKA_COMMAND_TOPIC, key=body.bus_id, payload=event)
    print(f"[fastapi] trace_id={trace_id} command_id={command_id} accepted bus_id={body.bus_id} action={body.action}")

    return CommandAcceptedResponse(
        accepted=True,
        command_id=command_id,
        trace_id=trace_id,
        bus_id=body.bus_id,
        action=body.action,
        topic=KAFKA_COMMAND_TOPIC,
    )


@router.get("/sse/telemetry")
async def sse_telemetry(request: Request, snapshot: bool = True):
    hub = request.app.state.telemetry_hub
    queue = await hub.subscribe()
    SSE_CLIENTS_CONNECTED.inc()
    trace_id = getattr(request.state, "trace_id", None)
    print(f"[fastapi-sse] trace_id={trace_id} client connected snapshot={snapshot}")

    async def event_stream():
        try:
            if snapshot:
                latest = hub.snapshot()
                for item in latest:
                    data = orjson.dumps(item).decode("utf-8")
                    yield f"event: snapshot\ndata: {data}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    data = orjson.dumps(event).decode("utf-8")
                    yield f"event: telemetry\ndata: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            await hub.unsubscribe(queue)
            SSE_CLIENTS_CONNECTED.dec()
            print(f"[fastapi-sse] trace_id={trace_id} client disconnected")

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)
