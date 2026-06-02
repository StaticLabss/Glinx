from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


class MessageBus:
    """Small async pub/sub bus for internal Glinx pipeline events."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[Any]]] = defaultdict(list)

    def subscribe(self, topic: str, maxsize: int = 1000) -> asyncio.Queue[Any]:
        queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=maxsize)
        self._subscribers[topic].append(queue)
        return queue

    async def publish(self, topic: str, payload: Any) -> None:
        for queue in self._subscribers.get(topic, []):
            await queue.put(payload)
