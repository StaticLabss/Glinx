from __future__ import annotations

from typing import Any

from ..models import EventMessage, SourceSnapshot


class MCPBridge:
    def __init__(self, snapshots: dict[str, SourceSnapshot], events: list[EventMessage]) -> None:
        self.snapshots = snapshots
        self.events = events

    def tool_specs(self) -> list[dict[str, Any]]:
        specs: list[dict[str, Any]] = []
        for snapshot in self.snapshots.values():
            specs.append(
                {
                    "name": snapshot.tool_name,
                    "description": snapshot.description,
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                    },
                    "outputSchema": snapshot.output_schema,
                }
            )
        specs.append(
            {
                "name": "drain_glinx_events",
                "description": "Returns queued hardware events with semantic descriptions.",
                "inputSchema": {"type": "object", "properties": {}},
                "outputSchema": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source_id": {"type": "string"},
                            "label": {"type": "string"},
                            "priority": {"type": "string"},
                            "kind": {"type": "string"},
                            "description": {"type": "string"},
                        },
                    },
                },
            }
        )
        return specs

    def invoke(self, tool_name: str) -> dict[str, Any] | list[dict[str, Any]]:
        if tool_name == "drain_glinx_events":
            drained = [event.model_dump() for event in self.events]
            self.events.clear()
            return drained

        for snapshot in self.snapshots.values():
            if snapshot.tool_name != tool_name:
                continue
            latest = snapshot.latest_message
            if latest is None:
                return {
                    "status": "unavailable",
                    "source_id": snapshot.source_id,
                    "message": "No sensor data has been ingested yet.",
                }
            return {
                "status": "ok",
                "source_id": snapshot.source_id,
                "timestamp": latest.timestamp,
                "data": latest.enriched or latest.parsed,
            }
        raise KeyError(f"Unknown tool: {tool_name}")

    def serve(self, transport: str = "stdio") -> None:
        try:
            from mcp.server.fastmcp import FastMCP
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Install the optional 'mcp' dependency to run the MCP server."
            ) from exc

        server = FastMCP("glinx")

        for spec in self.tool_specs():
            name = spec["name"]
            description = spec["description"]

            @server.tool(name=name, description=description)
            def _tool(name: str = name) -> Any:
                return self.invoke(name)

        server.run(transport=transport)
