from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Priority = Literal["LOW", "MEDIUM", "HIGH"]


class GlinxMessage(BaseModel):
    source_id: str
    protocol: str
    timestamp: float
    raw_payload: bytes = b""
    parsed: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    enriched: dict[str, Any] = Field(default_factory=dict)


class EventMessage(BaseModel):
    source_id: str
    label: str
    priority: Priority
    timestamp: float
    kind: Literal["rule", "anomaly", "summary"]
    description: str
    payload: dict[str, Any] = Field(default_factory=dict)


class SourceSnapshot(BaseModel):
    source_id: str
    tool_name: str
    description: str
    output_schema: dict[str, Any]
    latest_message: GlinxMessage | None = None
    latest_event: EventMessage | None = None
