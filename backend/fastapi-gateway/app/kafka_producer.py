import json
from typing import Any

from aiokafka import AIOKafkaProducer


class KafkaCommandProducer:
    def __init__(self, bootstrap_servers: str):
        self._producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers)

    async def start(self):
        await self._producer.start()

    async def stop(self):
        await self._producer.stop()

    async def publish(self, topic: str, key: str, payload: dict[str, Any]):
        await self._producer.send_and_wait(
            topic=topic,
            key=key.encode("utf-8"),
            value=json.dumps(payload).encode("utf-8"),
        )
