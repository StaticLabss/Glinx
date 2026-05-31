from __future__ import annotations

import asyncio
from typing import Any

from .bridges.mcp import MCPBridge
from .bus import MessageBus
from .config import GlinxConfig, SourceConfig
from .drivers import DriverRegistry, MockDriver
from .events import EventFilter
from .models import EventMessage, GlinxMessage, SourceSnapshot
from .schema import SchemaEngine
from .semantic import SemanticTagger


class GlinxRuntime:
    def __init__(self, config: GlinxConfig) -> None:
        self.config = config
        self.bus = MessageBus()
        self.schema_engine = SchemaEngine()
        self.semantic_tagger = SemanticTagger()
        self.event_filter = EventFilter(config.event_rules, config.summary_windows)
        self.events: list[EventMessage] = []
        self.snapshots: dict[str, SourceSnapshot] = {}
        self.registry = DriverRegistry()
        self.registry.register("mock", MockDriver)
        self._sensor_map = config.sensor_map()
        self._init_snapshots()

    @classmethod
    def from_path(cls, path: str) -> "GlinxRuntime":
        return cls(GlinxConfig.from_yaml(path))

    def _init_snapshots(self) -> None:
        for source in self.config.ingestion.sources:
            tool_name = f"get_{source.id}_status"
            description = f"Returns the current semantic state for hardware source '{source.id}'."
            self.snapshots[source.id] = SourceSnapshot(
                source_id=source.id,
                tool_name=tool_name,
                description=description,
                output_schema={"type": "object", "properties": {}},
            )

    async def ingest_source(self, source: SourceConfig) -> list[GlinxMessage]:
        driver = self.registry.create(source)
        messages = await driver.poll()
        processed: list[GlinxMessage] = []
        for message in messages:
            processed.append(await self.process_message(message))
        return processed

    async def process_message(self, message: GlinxMessage) -> GlinxMessage:
        sensor = self._sensor_map.get(message.source_id)
        self.schema_engine.observe(message.source_id, message.parsed)
        message.enriched = self.semantic_tagger.enrich(sensor, message.parsed)
        snapshot = self.snapshots[message.source_id]
        snapshot.latest_message = message
        snapshot.output_schema = self.schema_engine.schema_for(message.source_id)
        for event in self.event_filter.process(message):
            snapshot.latest_event = event
            self.events.append(event)
            await self.bus.publish("events", event)
        await self.bus.publish("messages", message)
        return message

    async def poll_once(self) -> dict[str, list[GlinxMessage]]:
        results: dict[str, list[GlinxMessage]] = {}
        for source in self.config.ingestion.sources:
            results[source.id] = await self.ingest_source(source)
        return results

    async def poll_forever(self, interval_seconds: float = 1.0) -> None:
        while True:
            await self.poll_once()
            await asyncio.sleep(interval_seconds)

    def build_mcp_bridge(self) -> MCPBridge:
        return MCPBridge(self.snapshots, self.events)

    def tool_specs(self) -> list[dict[str, Any]]:
        return self.build_mcp_bridge().tool_specs()
