from contextlib import asynccontextmanager
import asyncio
import time
from uuid import uuid4

from fastapi import FastAPI, Request

from app.config import KAFKA_BOOTSTRAP_SERVERS
from app.kafka_producer import KafkaCommandProducer
from app.metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL
from app.routes import router
from app.telemetry_consumer import run_telemetry_consumer
from app.telemetry_hub import TelemetryHub


@asynccontextmanager
async def lifespan(app: FastAPI):
    producer = KafkaCommandProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    await producer.start()
    hub = TelemetryHub()
    stop_event = asyncio.Event()
    consumer_task = asyncio.create_task(run_telemetry_consumer(hub, stop_event))

    app.state.command_producer = producer
    app.state.telemetry_hub = hub
    try:
        yield
    finally:
        stop_event.set()
        await consumer_task
        await producer.stop()


app = FastAPI(title="Fleet API Gateway", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def trace_and_metrics(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id") or f"trace-{uuid4()}"
    request.state.trace_id = trace_id
    started = time.perf_counter()

    response = await call_next(request)

    elapsed = time.perf_counter() - started
    path = request.url.path
    HTTP_REQUEST_DURATION_SECONDS.labels(method=request.method, path=path).observe(elapsed)
    HTTP_REQUESTS_TOTAL.labels(method=request.method, path=path, status=str(response.status_code)).inc()
    response.headers["x-trace-id"] = trace_id
    return response


app.include_router(router)
