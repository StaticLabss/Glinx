"""Glinx — decorator-based API for hardware-to-agent middleware.

Usage::

    from glinx import Glinx

    app = Glinx()

    @app.sensor("room_temp", protocol="mqtt", topic="home/temp")
    def room_temp(raw):
        return {"temperature_c": raw["t"], "humidity_pct": raw["h"]}

    @app.rule("room_temp", when="temperature_c > 40", priority="HIGH")
    def overheat(event):
        return "Room temperature critically high"

    app.serve()
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any, Callable, Literal

from .config import (
    BridgeConfig,
    EventRuleConfig,
    GlinxConfig,
    IngestionConfig,
    SensorConfig,
    SourceConfig,
    SummaryWindowConfig,
)
from .models import EventMessage, Priority
from .runtime import GlinxRuntime
from .actions import ActionRegistry

logger = logging.getLogger(__name__)


class _SensorRegistration:
    """Internal record for a decorated sensor."""

    __slots__ = ("id", "protocol", "driver_opts", "fields", "sensor_type", "location", "unit", "transform")

    def __init__(
        self,
        id: str,
        protocol: str,
        driver_opts: dict[str, Any],
        transform: Callable[[dict[str, Any]], dict[str, Any]] | None,
        fields: dict[str, str] | None,
        sensor_type: str | None,
        location: str | None,
        unit: str | None,
    ) -> None:
        self.id = id
        self.protocol = protocol
        self.driver_opts = driver_opts
        self.transform = transform
        self.fields = fields or {}
        self.sensor_type = sensor_type or "generic"
        self.location = location or ""
        self.unit = unit


class Glinx:
    """FastAPI-style entry point for building hardware-to-agent pipelines.

    Example::

        app = Glinx()

        @app.sensor("temp", protocol="mqtt", topic="env/temp")
        def temp(raw):
            return {"temperature_c": raw["t"]}

        app.serve()
    """

    def __init__(self, name: str = "glinx", bridge: Literal["mcp", "langgraph", "langchain", "push"] = "mcp") -> None:
        self.name = name
        self.bridge = bridge
        self._sensors: list[_SensorRegistration] = []
        self._rules: list[EventRuleConfig] = []
        self._summaries: list[SummaryWindowConfig] = []
        self._event_callbacks: dict[str, Callable[..., Any]] = {}
        self._runtime: GlinxRuntime | None = None
        self._transforms: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}
        self._actions = ActionRegistry()

    # ── Decorators ──────────────────────────────────────────────

    def sensor(
        self,
        id: str,
        *,
        protocol: str = "mock",
        fields: dict[str, str] | None = None,
        sensor_type: str | None = None,
        location: str | None = None,
        unit: str | None = None,
        **driver_kwargs: Any,
    ) -> Callable[..., Any]:
        """Register a hardware sensor source.

        The decorated function receives the raw parsed payload ``dict``
        and must return a ``dict`` of enriched key-value pairs.  If no
        transform is needed, decorate a no-op or pass ``None``.

        Args:
            id: Unique sensor identifier (becomes the MCP tool suffix).
            protocol: Ingestion protocol (``"mqtt"``, ``"serial"``, ``"mock"``).
            fields: Optional mapping of raw field names to semantic names.
            sensor_type: Sensor type label (e.g. ``"imu"``, ``"force_sensor"``).
            location: Dot-path location descriptor (e.g. ``"robot.hand.left"``).
            unit: Physical unit label (e.g. ``"kPa"``, ``"C"``).
            **driver_kwargs: Additional options forwarded to the protocol driver
                (e.g. ``topic="home/temp"`` for MQTT, ``port="/dev/ttyUSB0"``
                for serial).
        """

        def decorator(fn: Callable[[dict[str, Any]], dict[str, Any]]) -> Callable[[dict[str, Any]], dict[str, Any]]:
            reg = _SensorRegistration(
                id=id,
                protocol=protocol,
                driver_opts=driver_kwargs,
                transform=fn,
                fields=fields,
                sensor_type=sensor_type,
                location=location,
                unit=unit,
            )
            self._sensors.append(reg)
            self._transforms[id] = fn
            return fn

        return decorator

    def rule(
        self,
        sensor_id: str,
        *,
        when: str,
        priority: Priority = "MEDIUM",
        label: str | None = None,
    ) -> Callable[..., Any]:
        """Register an event rule for a sensor.

        Args:
            sensor_id: The sensor this rule applies to.
            when: A safe Python expression evaluated against enriched fields.
            priority: ``"LOW"``, ``"MEDIUM"``, or ``"HIGH"``.
            label: Human-readable event label.  Defaults to the function name.
        """

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._rules.append(
                EventRuleConfig(
                    sensor=sensor_id,
                    condition=when,
                    priority=priority,
                    label=label or fn.__name__,
                )
            )
            return fn

        return decorator

    def summary(
        self,
        sensors: list[str],
        *,
        interval_seconds: int = 5,
        label: str | None = None,
    ) -> Callable[..., Any]:
        """Register a summary window.

        Args:
            sensors: List of sensor IDs to include.
            interval_seconds: How often to generate a summary event.
            label: Label for the summary event.
        """

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._summaries.append(
                SummaryWindowConfig(
                    sensors=sensors,
                    interval_seconds=interval_seconds,
                    label=label or fn.__name__,
                )
            )
            return fn

        return decorator

    def on_event(self, label: str) -> Callable[..., Any]:
        """Register a callback that fires when an event with *label* occurs.

        The callback receives the :class:`EventMessage` as its sole argument.
        """

        def decorator(fn: Callable[[EventMessage], Any]) -> Callable[[EventMessage], Any]:
            self._event_callbacks[label] = fn
            return fn

        return decorator

    def action(self, name: str) -> Callable[..., Any]:
        """Register an action that agents can call to control hardware.

        Example::

            @app.action("turn_on_led")
            def turn_on_led():
                gpio.output(LED_PIN, HIGH)
                return {"status": "LED on"}
        """

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._actions.register(name, fn)
            return fn

        return decorator

    # ── Config builder ──────────────────────────────────────────

    def _build_config(self) -> GlinxConfig:
        """Compile decorator registrations into a ``GlinxConfig``."""
        sources: list[SourceConfig] = []
        sensor_configs: list[SensorConfig] = []

        for reg in self._sensors:
            # Build SourceConfig — driver_opts become "options" via the
            # model_validator on SourceConfig that sweeps unknown keys.
            source_data: dict[str, Any] = {
                "id": reg.id,
                "protocol": reg.protocol,
                **reg.driver_opts,
            }
            sources.append(SourceConfig.model_validate(source_data))

            # Build SensorConfig if fields or type/location were specified.
            if reg.fields or reg.sensor_type != "generic" or reg.location:
                sensor_configs.append(
                    SensorConfig(
                        id=reg.id,
                        type=reg.sensor_type,
                        location=reg.location,
                        unit=reg.unit,
                        fields=reg.fields or {},
                    )
                )

        return GlinxConfig(
            glinx=BridgeConfig(name=self.name, agent_bridge=self.bridge),
            ingestion=IngestionConfig(sources=sources),
            sensors=sensor_configs,
            event_rules=list(self._rules),
            summary_windows=list(self._summaries),
        )

    def _build_runtime(self) -> GlinxRuntime:
        """Build and cache the runtime."""
        if self._runtime is None:
            config = self._build_config()
            self._runtime = GlinxRuntime(config)
        return self._runtime

    # ── Lifecycle ───────────────────────────────────────────────

    def serve(self, transport: str = "stdio") -> None:
        """Build the runtime, run one poll cycle, and start the MCP server.

        This is the main entry point for exposing sensors as MCP tools.
        """
        self._apply_windows_event_loop_policy()
        runtime = self._build_runtime()
        asyncio.run(runtime.poll_once())
        runtime.build_mcp_bridge().serve(transport=transport)

    def run(self, *, interval: float = 1.0) -> None:
        """Build the runtime and start the polling loop (no MCP server).

        Useful for headless ingestion, logging, or feeding events to
        callbacks registered with :meth:`on_event`.
        """
        self._apply_windows_event_loop_policy()
        runtime = self._build_runtime()

        async def _loop() -> None:
            while True:
                await runtime.poll_once()
                # Fire event callbacks.
                while runtime.events:
                    event = runtime.events.popleft()
                    cb = self._event_callbacks.get(event.label)
                    if cb is not None:
                        cb(event)
                await asyncio.sleep(interval)

        asyncio.run(_loop())

    def poll_once(self) -> dict[str, Any]:
        """Run a single synchronous poll cycle and return results.

        Handy for testing or one-shot usage.
        """
        self._apply_windows_event_loop_policy()
        runtime = self._build_runtime()
        return asyncio.run(runtime.poll_once())

    # ── Utilities ───────────────────────────────────────────────

    @staticmethod
    def _apply_windows_event_loop_policy() -> None:
        """On Windows, aiomqtt needs SelectorEventLoop."""
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    def __repr__(self) -> str:
        return (
            f"Glinx(name={self.name!r}, sensors={len(self._sensors)}, "
            f"rules={len(self._rules)})"
        )
