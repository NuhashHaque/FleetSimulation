import asyncio
from typing import Any


class TelemetryHub:
    """In-memory fanout hub for SSE clients with latest snapshot per bus."""

    def __init__(self):
        self._latest_by_bus: dict[str, dict[str, Any]] = {}
        self._subscribers: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    async def publish(self, event: dict[str, Any]):
        bus_id = event.get("bus_id")
        if isinstance(bus_id, str) and bus_id:
            self._latest_by_bus[bus_id] = event

        async with self._lock:
            stale: list[asyncio.Queue] = []
            for queue in self._subscribers:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    stale.append(queue)
            for queue in stale:
                self._subscribers.discard(queue)

    def snapshot(self) -> list[dict[str, Any]]:
        return list(self._latest_by_bus.values())

    async def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue):
        async with self._lock:
            self._subscribers.discard(queue)
