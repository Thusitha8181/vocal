import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any


class EventBus:
    """In-process pub/sub for live dashboard updates.

    Single-instance only; swap for Redis pub/sub or Postgres LISTEN/NOTIFY when running
    more than one backend replica.
    """

    def __init__(self, max_queue: int = 256) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._max_queue = max_queue

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        event = {"type": event_type, **payload}
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(self._max_queue)
        self._subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers.discard(queue)


def to_json(event: dict[str, Any]) -> str:
    return json.dumps(event, default=str)


bus = EventBus()
