from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..config import SourceConfig
from ..models import GlinxMessage


class BaseDriver(ABC):
    protocol: str

    def __init__(self, source: SourceConfig) -> None:
        self.source = source

    @abstractmethod
    async def poll(self) -> list[GlinxMessage]:
        """Return zero or more newly-ingested messages."""


class DriverRegistry:
    def __init__(self) -> None:
        self._drivers: dict[str, type[BaseDriver]] = {}

    def register(self, protocol: str, driver_cls: type[BaseDriver]) -> None:
        self._drivers[protocol] = driver_cls

    def create(self, source: SourceConfig) -> BaseDriver:
        driver_cls = self._drivers.get(source.protocol)
        if driver_cls is None:
            raise ValueError(f"No driver registered for protocol '{source.protocol}'")
        return driver_cls(source)

    def protocols(self) -> list[str]:
        return sorted(self._drivers.keys())
