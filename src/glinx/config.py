from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class BridgeConfig(BaseModel):
    name: str = "glinx"
    agent_bridge: Literal["mcp", "langgraph", "langchain", "push"] = "mcp"


class SourceConfig(BaseModel):
    id: str
    protocol: str
    parser: str | None = None
    modality: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def collect_unknown_keys(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        known = {"id", "protocol", "parser", "modality"}
        extra = {key: value for key, value in data.items() if key not in known}
        merged = dict(data)
        merged["options"] = extra
        return merged


class SensorConfig(BaseModel):
    id: str
    type: str
    location: str
    unit: str | None = None
    fields: dict[str, str] = Field(default_factory=dict)
    modality_handler: str | None = None


class EventRuleConfig(BaseModel):
    sensor: str
    condition: str
    priority: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"
    label: str


class SummaryWindowConfig(BaseModel):
    sensors: list[str]
    interval_seconds: int
    label: str


class IngestionConfig(BaseModel):
    sources: list[SourceConfig] = Field(default_factory=list)


class GlinxConfig(BaseModel):
    glinx: BridgeConfig = Field(default_factory=BridgeConfig)
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)
    sensors: list[SensorConfig] = Field(default_factory=list)
    event_rules: list[EventRuleConfig] = Field(default_factory=list)
    summary_windows: list[SummaryWindowConfig] = Field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "GlinxConfig":
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        return cls.model_validate(payload)

    def sensor_map(self) -> dict[str, SensorConfig]:
        return {sensor.id: sensor for sensor in self.sensors}
