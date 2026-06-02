"""Serial / UART protocol driver for Glinx.

Requires the ``pyserial-asyncio-fast`` package::

    pip install glinx[serial]
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
    import serial_asyncio_fast  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    serial_asyncio_fast = None  # type: ignore[assignment]


class SerialDriver(BaseDriver):
    """Async serial ingestion driver backed by ``pyserial-asyncio-fast``."""

    protocol = "serial"

    def __init__(self, source) -> None:  # type: ignore[override]
        if serial_asyncio_fast is None:  # pragma: no cover
            raise RuntimeError(
                "The 'pyserial-asyncio-fast' package is required for the Serial driver. "
                "Install it with: pip install glinx[serial]"
            )
        super().__init__(source)
        opts = source.options
        self._port: str = opts.get("port", "")
        self._baudrate: int = int(opts.get("baudrate", 115200))
        self._parser: str = opts.get("parser", "json")
        self._csv_fields: list[str] = opts.get("csv_fields", [])
        self._buffer: list[GlinxMessage] = []
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._task: asyncio.Task[None] | None = None

    async def _read_loop(self) -> None:
        """Background loop that reads lines from the serial port."""
        backoff = 1.0
        while True:
            try:
                self._reader, self._writer = (
                    await serial_asyncio_fast.open_serial_connection(
                        url=self._port,
                        baudrate=self._baudrate,
                    )
                )
                logger.info(
                    "Serial driver '%s' opened %s @ %d baud",
                    self.source.id,
                    self._port,
                    self._baudrate,
                )
                backoff = 1.0
                while True:
                    line = await self._reader.readline()
                    if not line:
                        break
                    parsed = self._parse_line(line)
                    if parsed is not None:
                        self._buffer.append(
                            GlinxMessage(
                                source_id=self.source.id,
                                protocol="serial",
                                timestamp=time.time(),
                                raw_payload=line,
                                parsed=parsed,
                                metadata={
                                    "port": self._port,
                                    "baudrate": self._baudrate,
                                },
                            )
                        )
            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning(
                    "Serial driver '%s' error on %s, reconnecting in %.0fs",
                    self.source.id,
                    self._port,
                    backoff,
                    exc_info=True,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
            finally:
                if self._writer is not None:
                    try:
                        self._writer.close()
                    except Exception:
                        pass
                self._reader = None
                self._writer = None

    def _parse_line(self, line: bytes) -> dict[str, Any] | None:
        """Parse a single line from the serial stream."""
        text = line.decode("utf-8", errors="replace").strip()
        if not text:
            return None

        if self._parser == "json":
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    return data
                return {"value": data}
            except json.JSONDecodeError:
                logger.debug("Serial '%s': non-JSON line: %s", self.source.id, text)
                return {"raw": text}

        if self._parser == "csv":
            parts = text.split(",")
            if self._csv_fields:
                return {
                    field: self._try_number(val)
                    for field, val in zip(self._csv_fields, parts)
                }
            return {f"field_{i}": self._try_number(v) for i, v in enumerate(parts)}

        # Fallback: treat entire line as a raw string value.
        return {"raw": text}

    @staticmethod
    def _try_number(value: str) -> int | float | str:
        """Attempt to parse a string as a number."""
        value = value.strip()
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            return value

    async def poll(self) -> list[GlinxMessage]:
        """Return buffered messages since last poll and start listener if needed."""
        if self._task is None and self._port:
            self._task = asyncio.create_task(self._read_loop())
            await asyncio.sleep(0.1)

        drained = list(self._buffer)
        self._buffer.clear()
        return drained

    async def close(self) -> None:
        """Cancel the background read loop."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
