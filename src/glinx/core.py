"""Python interface to C++ core.

This module provides seamless integration between the C++ real-time core
and Python's high-level AI/LLM layer.
"""

from __future__ import annotations

import json
import time
from typing import Any

try:
    import _glinx_core  # type: ignore[import-not-found]

    HAS_CPP_CORE = True
except ImportError:
    HAS_CPP_CORE = False
    _glinx_core = None


class CppRuntimeBridge:
    """Bridge between Python and C++ runtime.
    
    Automatically uses C++ core if available, falls back to pure Python.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.cpp_runtime: Any = None
        self.use_cpp = HAS_CPP_CORE and self._should_use_cpp()

        if self.use_cpp:
            self._init_cpp_runtime()

    def _should_use_cpp(self) -> bool:
        """Check if C++ core should be used based on config."""
        # Use C++ for high-frequency protocols
        if not self.config.get("sources"):
            return False

        for source in self.config["sources"]:
            protocol = source.get("protocol", "")
            if protocol in ("serial", "i2c", "spi"):
                return True

        return False

    def _init_cpp_runtime(self) -> None:
        """Initialize C++ runtime with config."""
        config_json = json.dumps(self.config)
        self.cpp_runtime = _glinx_core.GlinxRuntime(config_json)
        self.cpp_runtime.start()

    def get_messages(self) -> list[dict[str, Any]]:
        """Get messages from C++ buffer."""
        if not self.use_cpp or self.cpp_runtime is None:
            return []

        messages = self.cpp_runtime.get_messages()
        return [self._convert_message(msg) for msg in messages]

    def _convert_message(self, cpp_msg: Any) -> dict[str, Any]:
        """Convert C++ SensorMessage to Python dict."""
        msg_dict = cpp_msg.to_dict()

        # Parse payload as JSON
        try:
            payload_str = msg_dict["payload"].decode("utf-8")
            msg_dict["parsed"] = json.loads(payload_str)
        except (json.JSONDecodeError, UnicodeDecodeError):
            msg_dict["parsed"] = {}

        return {
            "source_id": msg_dict["source_id"],
            "protocol": msg_dict["protocol"],
            "timestamp": msg_dict["timestamp"],
            "raw_payload": msg_dict["payload"],
            "parsed": msg_dict["parsed"],
            "metadata": {"cpp_core": True},
            "enriched": {},
        }

    def get_stats(self) -> dict[str, Any]:
        """Get runtime statistics."""
        if not self.use_cpp or self.cpp_runtime is None:
            return {"cpp_core_enabled": False}

        stats_json = self.cpp_runtime.get_stats()
        stats = json.loads(stats_json)
        stats["cpp_core_enabled"] = True
        return stats

    def stop(self) -> None:
        """Stop C++ runtime."""
        if self.cpp_runtime is not None:
            self.cpp_runtime.stop()
            self.cpp_runtime = None

    def __enter__(self) -> CppRuntimeBridge:
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop()


def benchmark_cpp_core(iterations: int = 100000) -> dict[str, Any]:
    """Benchmark C++ buffer performance."""
    if not HAS_CPP_CORE:
        return {"error": "C++ core not available"}

    return _glinx_core.benchmark_buffer(iterations)


def get_cpp_version() -> str | None:
    """Get C++ core version."""
    if not HAS_CPP_CORE:
        return None
    return _glinx_core.version()


def has_cpp_core() -> bool:
    """Check if C++ core is available."""
    return HAS_CPP_CORE
