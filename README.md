# Glinx

Glinx is a Python middleware framework that connects physical hardware streams to LLM agents through a unified, semantic, MCP-friendly interface.

## What This MVP Includes

- Config-driven project setup via `glinx.yaml`
- Pluggable ingestion drivers with a working `mock` driver
- Automatic schema inference from live payload samples
- Semantic sensor enrichment from YAML field mappings
- Rule, anomaly, and summary event generation
- MCP bridge scaffold that exposes per-sensor tool definitions
- CLI commands for config inspection and tool generation

## Project Layout

```text
src/glinx/
  bridges/       MCP bridge
  drivers/       protocol drivers
  bus.py         async internal bus
  cli.py         CLI entrypoint
  config.py      YAML config models
  events.py      anomaly/rule/summary filtering
  models.py      core message/event models
  runtime.py     orchestration layer
  schema.py      schema inference
  semantic.py    semantic enrichment
```

## Quick Start

```bash
uv sync --extra dev
uv run glinx inspect-config --config glinx.example.yaml
uv run glinx print-tools --config glinx.example.yaml
```

To expose the MCP server, install the MCP extra:

```bash
uv sync --extra mcp
uv run glinx start --config glinx.example.yaml --serve-mcp
```

## Example Config

See `glinx.example.yaml` for a full working demo with mock sources and event rules.

## Current Scope

This first pass focuses on the middleware architecture and a working local demo path. Real MQTT, Serial, WebSocket, BLE, CAN, ROS2, and modality handlers are not implemented yet, but the driver/plugin system is ready for them.
