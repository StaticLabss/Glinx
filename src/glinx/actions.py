"""Agent action system for hardware control.

Allows AI agents to send commands back to hardware (actuators, LEDs, motors, etc.)
"""

from __future__ import annotations

from typing import Any, Callable
import asyncio
import logging

logger = logging.getLogger(__name__)


class ActionRegistry:
    """Registry for agent-callable hardware actions."""

    def __init__(self) -> None:
        self._actions: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, handler: Callable[..., Any]) -> None:
        """Register an action handler.
        
        Args:
            name: Action name (e.g., "turn_on_led", "set_motor_speed")
            handler: Function that executes the action
        """
        self._actions[name] = handler
        logger.info(f"Registered action: {name}")

    async def execute(self, name: str, **kwargs: Any) -> dict[str, Any]:
        """Execute an action.
        
        Args:
            name: Action name
            **kwargs: Action parameters
            
        Returns:
            Result dictionary with status and any return values
        """
        if name not in self._actions:
            return {
                "status": "error",
                "error": f"Unknown action: {name}",
            }
        
        try:
            handler = self._actions[name]
            
            # Call handler (sync or async)
            if asyncio.iscoroutinefunction(handler):
                result = await handler(**kwargs)
            else:
                result = handler(**kwargs)
            
            return {
                "status": "success",
                "result": result,
            }
        except Exception as e:
            logger.error(f"Action {name} failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
            }

    def list_actions(self) -> list[dict[str, Any]]:
        """Get list of available actions."""
        actions = []
        for name, handler in self._actions.items():
            import inspect
            sig = inspect.signature(handler)
            
            actions.append({
                "name": name,
                "parameters": [
                    {
                        "name": param.name,
                        "required": param.default == inspect.Parameter.empty,
                    }
                    for param in sig.parameters.values()
                ],
            })
        
        return actions
