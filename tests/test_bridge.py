"""Tests for the MCP bridge."""

import pytest

from glinx.bridges.mcp import MCPBridge
from glinx.models import EventMessage, GlinxMessage, SourceSnapshot


def _make_snapshot(source_id: str, with_message: bool = True) -> SourceSnapshot:
    msg = None
    if with_message:
        msg = GlinxMessage(
            source_id=source_id,
            protocol="mock",
            timestamp=1000.0,
            parsed={"v": 42},
            enriched={"value": 42, "semantic_summary": "test sensor"},
        )
    return SourceSnapshot(
        source_id=source_id,
        tool_name=f"get_{source_id}_status",
        description=f"Status for {source_id}",
        output_schema={"type": "object", "properties": {"v": {"type": "number"}}},
        latest_message=msg,
    )


def _make_event(source_id: str = "s1", label: str = "alert") -> EventMessage:
    return EventMessage(
        source_id=source_id,
        label=label,
        priority="HIGH",
        timestamp=1000.0,
        kind="rule",
        description="Test event",
        payload={"v": 99},
    )


# ── tool_specs tests ───────────────────────────────────────────


def test_tool_specs_includes_source_tools_and_drain() -> None:
    snapshots = {"s1": _make_snapshot("s1"), "s2": _make_snapshot("s2")}
    bridge = MCPBridge(snapshots, [])
    specs = bridge.tool_specs()

    names = [s["name"] for s in specs]
    assert "get_s1_status" in names
    assert "get_s2_status" in names
    assert "drain_glinx_events" in names


# ── invoke tests ───────────────────────────────────────────────


def test_invoke_source_tool_with_data() -> None:
    snapshots = {"s1": _make_snapshot("s1", with_message=True)}
    bridge = MCPBridge(snapshots, [])
    result = bridge.invoke("get_s1_status")
    assert result["status"] == "ok"
    assert result["source_id"] == "s1"
    assert result["data"]["value"] == 42


def test_invoke_source_tool_without_data() -> None:
    snapshots = {"s1": _make_snapshot("s1", with_message=False)}
    bridge = MCPBridge(snapshots, [])
    result = bridge.invoke("get_s1_status")
    assert result["status"] == "unavailable"


def test_invoke_drain_events() -> None:
    events = [_make_event("s1", "a"), _make_event("s2", "b")]
    bridge = MCPBridge({}, events)
    drained = bridge.invoke("drain_glinx_events")
    assert len(drained) == 2
    assert drained[0]["label"] == "a"
    # Events should be cleared after drain.
    assert bridge.invoke("drain_glinx_events") == []


def test_invoke_unknown_tool_raises() -> None:
    bridge = MCPBridge({}, [])
    with pytest.raises(KeyError, match="Unknown tool"):
        bridge.invoke("nonexistent_tool")
