from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from app.config import KAFKA_COMMAND_TOPIC, SERVICE_NAME
from app.models import CommandAcceptedResponse, CommandRequest

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "service": SERVICE_NAME}


@router.post("/api/command", response_model=CommandAcceptedResponse)
async def command(request: Request, body: CommandRequest):
    producer = request.app.state.command_producer
    if producer is None:
        raise HTTPException(status_code=503, detail="Kafka producer not ready")

    trace_id = body.trace_id or f"trace-{uuid4()}"
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

    return CommandAcceptedResponse(
        accepted=True,
        command_id=command_id,
        trace_id=trace_id,
        bus_id=body.bus_id,
        action=body.action,
        topic=KAFKA_COMMAND_TOPIC,
    )
