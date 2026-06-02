"""MQTT protocol driver for Glinx.

Requires the ``aiomqtt`` package::

    pip install glinx[mqtt]
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from ..models import GlinxMessage
from .base import BaseDriver

logger = logging.getLogger(__name__)

try:
    import aiomqtt
except ImportError:  # pragma: no cover
    aiomqtt = None  # type: ignore[assignment]


class MQTTDriver(BaseDriver):
    """Async MQTT ingestion driver backed by ``aiomqtt``."""

    protocol = "mqtt"

    def __init__(self, source) -> None:  # type: ignore[override]
        if aiomqtt is None:  # pragma: no cover
            raise RuntimeError(
                "The 'aiomqtt' package is required for the MQTT driver. "
                "Install it with: pip install glinx[mqtt]"
            )
        super().__init__(source)
        opts = source.options
        self._broker: str = opts.get("broker", "localhost")
        self._port: int = int(opts.get("port", 1883))
        self._topics: list[str] = opts.get("topics", [])
        self._username: str | None = opts.get("username")
        self._password: str | None = opts.get("password")
        self._client_id: str | None = opts.get("client_id")
        self._buffer: list[GlinxMessage] = []
        self._task: asyncio.Task[None] | None = None
        self._connected = False

    async def _subscribe_loop(self) -> None:
        """Background loop that subscribes to topics and buffers messages."""
        backoff = 1.0
        while True:
            try:
                async with aiomqtt.Client(
                    self._broker,
                    port=self._port,
                    username=self._username,
                    password=self._password,
                    identifier=self._client_id,
                ) as client:
                    for topic in self._topics:
                        await client.subscribe(topic)
                    self._connected = True
                    backoff = 1.0
                    logger.info(
                        "MQTT driver '%s' connected to %s:%d, subscribed to %s",
                        self.source.id,
                        self._broker,
                        self._port,
                        self._topics,
                    )
                    async for msg in client.messages:
                        parsed = self._parse_payload(msg.payload)
                        self._buffer.append(
                            GlinxMessage(
                                source_id=self.source.id,
                                protocol="mqtt",
                                timestamp=time.time(),
                                raw_payload=bytes(msg.payload) if msg.payload else b"",
                                parsed=parsed,
                                metadata={
                                    "topic": str(msg.topic),
                                    "qos": msg.qos,
                                },
                            )
                        )
            except asyncio.CancelledError:
                break
            except Exception:
                self._connected = False
                logger.warning(
                    "MQTT driver '%s' disconnected, reconnecting in %.0fs",
                    self.source.id,
                    backoff,
                    exc_info=True,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    @staticmethod
    def _parse_payload(payload: Any) -> dict[str, Any]:
        """Try JSON, fall back to raw string."""
        if payload is None:
            return {}
        raw = bytes(payload) if not isinstance(payload, bytes) else payload
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
            return {"value": data}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"raw": raw.decode("utf-8", errors="replace")}

    async def poll(self) -> list[GlinxMessage]:
        """Return buffered messages since last poll and start listener if needed."""
        if self._task is None:
            self._task = asyncio.create_task(self._subscribe_loop())
            # Give the subscription a moment to connect on first poll.
            await asyncio.sleep(0.1)

        drained = list(self._buffer)
        self._buffer.clear()
        return drained

    async def close(self) -> None:
        """Cancel the background subscription loop."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._connected = False
