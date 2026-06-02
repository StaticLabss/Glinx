from __future__ import annotations

import asyncio
import importlib
import json
import sys

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


@app.command()
def run(
    module: str = typer.Argument(
        ..., help="Python import path to a Glinx app instance, e.g. 'myapp:app'"
    ),
    transport: str = typer.Option("stdio", "--transport"),
) -> None:
    """Import a Glinx app from a Python module and start serving.

    Similar to ``uvicorn main:app``.  The module path should be in
    ``module:attribute`` format.  Example::

        glinx run demo:app
    """
    if ":" not in module:
        typer.echo("Error: module must be in 'module:attribute' format (e.g. 'demo:app')", err=True)
        raise typer.Exit(1)

    mod_path, attr_name = module.rsplit(":", 1)

    # Allow importing from the current directory.
    if "." not in sys.path:
        sys.path.insert(0, ".")

    try:
        mod = importlib.import_module(mod_path)
    except ModuleNotFoundError as exc:
        typer.echo(f"Error: could not import module '{mod_path}': {exc}", err=True)
        raise typer.Exit(1) from exc

    glinx_app = getattr(mod, attr_name, None)
    if glinx_app is None:
        typer.echo(f"Error: module '{mod_path}' has no attribute '{attr_name}'", err=True)
        raise typer.Exit(1)

    from .app import Glinx

    if not isinstance(glinx_app, Glinx):
        typer.echo(f"Error: '{mod_path}:{attr_name}' is not a Glinx instance", err=True)
        raise typer.Exit(1)

    glinx_app.serve(transport=transport)


if __name__ == "__main__":
    app()
