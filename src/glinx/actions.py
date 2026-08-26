"""Action system for agents to control hardware."""

from __future__ import annotations

from typing import Any, Callable
import logging

logger = logging.getLogger(__name__)


class ActionRegistry:
    """Registry for hardware control actions that agents can invoke."""

    def __init__(self) -> None:
        self._actions: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, handler: Callable[..., Any]) -> None:
        """Register an action handler."""
        self._actions[name] = handler
        logger.info(f"Registered action: {name}")

    def invoke(self, name: str, **kwargs: Any) -> dict[str, Any]:
        """Invoke an action by name."""
        if name not in self._actions:
            return {
                "success": False,
                "error": f"Unknown action: {name}",
            }

        try:
            result = self._actions[name](**kwargs)
            return {
                "success": True,
                "result": result,
            }
        except Exception as e:
            logger.error(f"Action '{name}' failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def list_actions(self) -> list[dict[str, Any]]:
        """List all available actions."""
        actions = []
        for name, handler in self._actions.items():
            actions.append({
                "name": name,
                "description": handler.__doc__ or "No description",
            })
        return actions
