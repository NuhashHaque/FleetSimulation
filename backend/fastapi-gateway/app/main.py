from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import KAFKA_BOOTSTRAP_SERVERS
from app.kafka_producer import KafkaCommandProducer
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    producer = KafkaCommandProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    await producer.start()
    app.state.command_producer = producer
    try:
        yield
    finally:
        await producer.stop()


app = FastAPI(title="Fleet API Gateway", version="0.1.0", lifespan=lifespan)
app.include_router(router)
