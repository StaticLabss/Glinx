"""Tests for hybrid Python/C++ runtime."""

import pytest
import asyncio
from glinx.runtime import GlinxRuntime
from glinx.config import GlinxConfig, IngestionConfig, SourceConfig, BridgeConfig
from glinx.core import has_cpp_core


@pytest.fixture
def mock_config():
    """Create a test configuration."""
    return GlinxConfig(
        glinx=BridgeConfig(name="test", agent_bridge="mcp"),
        ingestion=IngestionConfig(
            sources=[
                SourceConfig(
                    id="mock1",
                    protocol="mock",
                    options={"payloads": [{"x": 1.0}, {"x": 2.0}, {"x": 3.0}]},
                )
            ]
        ),
        sensors=[],
        event_rules=[],
        summary_windows=[],
    )


@pytest.mark.asyncio
async def test_runtime_poll_once(mock_config):
    """Test single poll cycle."""
    runtime = GlinxRuntime(mock_config)
    
    # Poll multiple times since mock driver cycles through payloads
    for _ in range(3):
        results = await runtime.poll_once()
    
    assert "mock1" in results
    assert len(results["mock1"]) > 0
    
    # Check message structure
    msg = results["mock1"][0]
    assert msg.source_id == "mock1"
    assert msg.protocol == "mock"
    assert "x" in msg.parsed


@pytest.mark.asyncio
async def test_runtime_message_enrichment(mock_config):
    """Test that messages get enriched."""
    runtime = GlinxRuntime(mock_config)
    
    for _ in range(3):
        results = await runtime.poll_once()
    
    if results["mock1"]:
        msg = results["mock1"][0]
        assert msg.enriched is not None
        assert isinstance(msg.enriched, dict)


@pytest.mark.asyncio
async def test_runtime_snapshots(mock_config):
    """Test that snapshots are updated."""
    runtime = GlinxRuntime(mock_config)
    
    for _ in range(3):
        await runtime.poll_once()
    
    snapshot = runtime.snapshots["mock1"]
    # Snapshot should be updated after multiple polls
    assert snapshot.source_id == "mock1"
    assert snapshot.tool_name == "get_mock1_status"


def test_mcp_bridge_generation(mock_config):
    """Test MCP bridge tool generation."""
    runtime = GlinxRuntime(mock_config)
    bridge = runtime.build_mcp_bridge()
    
    tool_specs = bridge.tool_specs()
    assert len(tool_specs) > 0
    
    # Check for source tool
    source_tools = [t for t in tool_specs if t["name"] == "get_mock1_status"]
    assert len(source_tools) == 1
    
    # Check for drain events tool
    event_tools = [t for t in tool_specs if t["name"] == "drain_glinx_events"]
    assert len(event_tools) == 1


@pytest.mark.skipif(not has_cpp_core(), reason="C++ core not available")
def test_cpp_driver_selection():
    """Test that runtime selects C++ drivers when available."""
    config = GlinxConfig(
        glinx=BridgeConfig(name="test", agent_bridge="mcp"),
        ingestion=IngestionConfig(
            sources=[
                SourceConfig(
                    id="serial1",
                    protocol="serial",
                    options={"port": "COM3", "baudrate": 115200},
                )
            ]
        ),
        sensors=[],
        event_rules=[],
        summary_windows=[],
    )
    
    runtime = GlinxRuntime(config)
    
    # Check if C++ bridge was initialized
    assert runtime._should_use_cpp(config.ingestion.sources[0])
    assert runtime._cpp_bridge is not None
