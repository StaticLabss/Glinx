from __future__ import annotations

import functools
import inspect
from collections.abc import Awaitable, Callable, MutableSequence
from typing import Any, get_args, get_origin

from ..actions import ActionRegistry
from ..models import EventMessage, SourceSnapshot


class MCPBridge:
    def __init__(
        self,
        snapshots: dict[str, SourceSnapshot],
        events: MutableSequence[EventMessage],
        *,
        actions: ActionRegistry | None = None,
        poll: Callable[[], Awaitable[Any]] | None = None,
    ) -> None:
        self.snapshots = snapshots
        self.events = events
        self.actions = actions or ActionRegistry()
        self.poll = poll

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
        for name in self.actions.names():
            handler = self.actions.get(name)
            specs.append(
                {
                    "name": name,
                    "description": inspect.getdoc(handler) or f"Execute hardware action '{name}'.",
                    "inputSchema": self._action_input_schema(handler),
                    "outputSchema": {"type": "object"},
                }
            )
        return specs

    @staticmethod
    def _action_input_schema(handler: Callable[..., Any]) -> dict[str, Any]:
        properties: dict[str, Any] = {}
        required: list[str] = []
        for parameter in inspect.signature(handler).parameters.values():
            if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
                continue
            properties[parameter.name] = MCPBridge._json_schema_for(parameter.annotation)
            if parameter.default is inspect.Parameter.empty:
                required.append(parameter.name)
            else:
                properties[parameter.name]["default"] = parameter.default
        return {"type": "object", "properties": properties, "required": required}

    @staticmethod
    def _json_schema_for(annotation: Any) -> dict[str, Any]:
        if annotation is inspect.Parameter.empty or annotation is Any:
            return {}
        origin = get_origin(annotation)
        if origin in (list, tuple, set):
            args = get_args(annotation)
            return {
                "type": "array",
                "items": MCPBridge._json_schema_for(args[0]) if args else {},
            }
        if origin is dict:
            return {"type": "object"}
        json_type = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
        }.get(annotation)
        return {"type": json_type} if json_type else {}

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

    async def invoke_async(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a live sensor/event tool or a registered hardware action."""
        if tool_name in self.actions.names():
            return await self.actions.execute(tool_name, **kwargs)
        if self.poll is not None:
            await self.poll()
        return self.invoke(tool_name)

    def serve(self, transport: str = "stdio") -> None:
        try:
            from mcp.server.fastmcp import FastMCP
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Install the optional 'mcp' dependency to run the MCP server."
            ) from exc

        server = FastMCP("glinx")

        def _make_tool_handler(bridge: MCPBridge, tool_name: str):
            """Create an isolated handler to avoid closure capture issues."""

            async def handler() -> Any:
                return await bridge.invoke_async(tool_name)

            return handler

        def _make_action_handler(
            bridge: MCPBridge,
            action_name: str,
            action: Callable[..., Any],
        ) -> Callable[..., Any]:
            # FastMCP follows ``__wrapped__`` to derive the original typed
            # signature while execution still passes through our registry.
            @functools.wraps(action)
            async def handler(*args: Any, **kwargs: Any) -> Any:
                if args:
                    bound = inspect.signature(action).bind(*args, **kwargs)
                    kwargs = dict(bound.arguments)
                return await bridge.invoke_async(action_name, **kwargs)

            return handler

        for spec in self.tool_specs():
            name = spec["name"]
            description = spec["description"]
            if name in self.actions.names():
                action = self.actions.get(name)
                handler = _make_action_handler(self, name, action)
            else:
                handler = _make_tool_handler(self, name)
            server.tool(name=name, description=description)(handler)

        server.run(transport=transport)
