"""Integration tests for C++ core with Python runtime."""

import pytest
from glinx.core import has_cpp_core, CppRuntimeBridge, benchmark_cpp_core


@pytest.mark.skipif(not has_cpp_core(), reason="C++ core not available")
def test_cpp_core_available():
    """Test that C++ core is properly installed."""
    assert has_cpp_core() is True


@pytest.mark.skipif(not has_cpp_core(), reason="C++ core not available")
def test_cpp_runtime_bridge():
    """Test C++ runtime bridge initialization."""
    config = {
        "sources": [
            {
                "id": "test_sensor",
                "protocol": "mock",
                "options": {"payloads": [{"x": 1.0, "y": 2.0}]},
            }
        ]
    }
    
    bridge = CppRuntimeBridge(config)
    assert bridge is not None
    
    stats = bridge.get_stats()
    assert "cpp_core_enabled" in stats
    
    bridge.stop()


@pytest.mark.skipif(not has_cpp_core(), reason="C++ core not available")
def test_cpp_buffer_performance():
    """Test C++ buffer performance meets targets."""
    result = benchmark_cpp_core(iterations=10000)
    
    assert "error" not in result
    assert result["iterations"] == 10000
    assert result["push_rate_mhz"] > 1.0  # > 1M msgs/sec
    
    print(f"\n  Push rate: {result['push_rate_mhz']:.2f} M msgs/sec")
    print(f"  Drain rate: {result['drain_rate_mhz']:.2f} M msgs/sec")


def test_python_fallback_when_no_cpp():
    """Test that Python runtime works without C++ core."""
    from glinx import Glinx
    
    app = Glinx()
    
    @app.sensor("test", protocol="mock", payloads=[{"val": 42}])
    def test_sensor(raw):
        return raw
    
    result = app.poll_once()
    assert "test" in result
    assert len(result["test"]) > 0
