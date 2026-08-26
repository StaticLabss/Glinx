"""Tests for action system."""

import pytest
import asyncio
from glinx.actions import ActionRegistry


@pytest.fixture
def registry():
    return ActionRegistry()


def test_register_action(registry):
    """Test action registration."""
    def my_action(value: int):
        return value * 2
    
    registry.register("double", my_action)
    actions = registry.list_actions()
    
    assert len(actions) == 1
    assert actions[0]["name"] == "double"


@pytest.mark.asyncio
async def test_execute_action(registry):
    """Test action execution."""
    def add(a: int, b: int):
        return a + b
    
    registry.register("add", add)
    
    result = await registry.execute("add", a=5, b=3)
    assert result["status"] == "success"
    assert result["result"] == 8


@pytest.mark.asyncio
async def test_execute_async_action(registry):
    """Test async action execution."""
    async def async_multiply(x: int, y: int):
        await asyncio.sleep(0.01)
        return x * y
    
    registry.register("multiply", async_multiply)
    
    result = await registry.execute("multiply", x=4, y=7)
    assert result["status"] == "success"
    assert result["result"] == 28


@pytest.mark.asyncio
async def test_execute_unknown_action(registry):
    """Test executing non-existent action."""
    result = await registry.execute("nonexistent")
    assert result["status"] == "error"
    assert "Unknown action" in result["error"]


@pytest.mark.asyncio
async def test_execute_action_with_error(registry):
    """Test action that raises exception."""
    def failing_action():
        raise ValueError("Something went wrong")
    
    registry.register("fail", failing_action)
    
    result = await registry.execute("fail")
    assert result["status"] == "error"
    assert "Something went wrong" in result["error"]


def test_list_actions_with_parameters(registry):
    """Test listing actions shows parameters."""
    def action_with_params(required: int, optional: str = "default"):
        return f"{required} {optional}"
    
    registry.register("test_action", action_with_params)
    
    actions = registry.list_actions()
    assert len(actions) == 1
    
    params = actions[0]["parameters"]
    assert len(params) == 2
    assert params[0]["name"] == "required"
    assert params[0]["required"] is True
    assert params[1]["name"] == "optional"
    assert params[1]["required"] is False
