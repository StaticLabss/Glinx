from __future__ import annotations

import asyncio
import json

import typer

from .runtime import GlinxRuntime

app = typer.Typer(help="Glinx: universal hardware-to-agent middleware.")


@app.command()
def inspect_config(config: str = typer.Option(..., "--config", "-c")) -> None:
    """Load a config and print detected source and sensor counts."""
    runtime = GlinxRuntime.from_path(config)
    typer.echo(
        json.dumps(
            {
                "name": runtime.config.glinx.name,
                "agent_bridge": runtime.config.glinx.agent_bridge,
                "sources": [source.id for source in runtime.config.ingestion.sources],
                "sensors": [sensor.id for sensor in runtime.config.sensors],
            },
            indent=2,
        )
    )


@app.command()
def print_tools(config: str = typer.Option(..., "--config", "-c")) -> None:
    """Infer schemas from one ingestion cycle and print generated tool specs."""
    runtime = GlinxRuntime.from_path(config)
    asyncio.run(runtime.poll_once())
    typer.echo(json.dumps(runtime.tool_specs(), indent=2))


@app.command()
def start(
    config: str = typer.Option(..., "--config", "-c"),
    transport: str = typer.Option("stdio", "--transport"),
    interval_seconds: float = typer.Option(1.0, "--interval"),
    serve_mcp: bool = typer.Option(False, "--serve-mcp"),
) -> None:
    """Start Glinx ingestion, optionally exposing an MCP server."""
    runtime = GlinxRuntime.from_path(config)
    asyncio.run(runtime.poll_once())

    if serve_mcp:
        runtime.build_mcp_bridge().serve(transport=transport)
        return

    typer.echo("Glinx runtime initialized.")
    typer.echo(f"Loaded {len(runtime.snapshots)} source tools.")
    typer.echo(f"Polling interval: {interval_seconds}s")
    typer.echo("Use --serve-mcp to expose tools over MCP.")


if __name__ == "__main__":
    app()
