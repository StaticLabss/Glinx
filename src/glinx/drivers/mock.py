from __future__ import annotations

import time
from typing import Any

from ..models import GlinxMessage
from .base import BaseDriver


class MockDriver(BaseDriver):
    protocol = "mock"

    def __init__(self, source) -> None:  # type: ignore[override]
        super().__init__(source)
        payloads = source.options.get("payloads", [])
        self._payloads: list[dict[str, Any]] = list(payloads)
        self._cursor = 0

    async def poll(self) -> list[GlinxMessage]:
        if not self._payloads:
            return []

        payload = self._payloads[self._cursor % len(self._payloads)]
        self._cursor += 1
        return [
            GlinxMessage(
                source_id=self.source.id,
                protocol=self.source.protocol,
                timestamp=time.time(),
                parsed=dict(payload),
                metadata=self.source.options,
            )
        ]
