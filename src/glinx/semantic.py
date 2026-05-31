from __future__ import annotations

from typing import Any

from .config import SensorConfig


class SemanticTagger:
    def enrich(self, sensor: SensorConfig | None, parsed: dict[str, Any]) -> dict[str, Any]:
        if sensor is None:
            return dict(parsed)

        enriched: dict[str, Any] = {
            "sensor": sensor.id,
            "sensor_type": sensor.type,
            "location": sensor.location,
        }

        summary_parts: list[str] = []
        for raw_key, semantic_name in sensor.fields.items():
            if raw_key not in parsed:
                continue
            enriched_key = semantic_name
            if sensor.unit and not semantic_name.endswith(f"_{sensor.unit}"):
                enriched_key = f"{semantic_name}_{sensor.unit}"
            enriched[enriched_key] = parsed[raw_key]
            summary_parts.append(f"{semantic_name}={parsed[raw_key]}")

        if not summary_parts:
            summary_parts = [f"{key}={value}" for key, value in parsed.items()]

        enriched["semantic_summary"] = (
            f"{sensor.id} at {sensor.location}: " + ", ".join(summary_parts)
        )
        return enriched
