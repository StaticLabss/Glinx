from __future__ import annotations

from collections import defaultdict
from typing import Any


def infer_json_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


class SchemaEngine:
    def __init__(self, sample_size: int = 5) -> None:
        self.sample_size = sample_size
        self._samples: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def observe(self, source_id: str, payload: dict[str, Any]) -> None:
        samples = self._samples[source_id]
        if len(samples) < self.sample_size:
            samples.append(dict(payload))

    def schema_for(self, source_id: str) -> dict[str, Any]:
        fields: dict[str, dict[str, Any]] = {}
        for sample in self._samples.get(source_id, []):
            for key, value in sample.items():
                fields.setdefault(key, {"type": infer_json_type(value)})
        return {
            "type": "object",
            "properties": fields,
            "required": sorted(fields.keys()),
        }
