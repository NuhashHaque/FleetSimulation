from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI

from app.config import KAFKA_BOOTSTRAP_SERVERS
from app.kafka_producer import KafkaCommandProducer
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
app.include_router(router)
