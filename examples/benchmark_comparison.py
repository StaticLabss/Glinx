"""Benchmark: Python-only vs C++ core performance.

Demonstrates the massive performance gain from C++ core.
"""

import time
import asyncio
from glinx.core import has_cpp_core, benchmark_cpp_core


def benchmark_python_only():
    """Simulate Python-only ingestion (mock)."""
    from glinx import Glinx
    
    app = Glinx()
    
    @app.sensor(
        "mock_sensor",
        protocol="mock",
        payloads=[{"x": 1.0, "y": 2.0, "z": 3.0}] * 1000,
    )
    def mock_sensor(raw):
        return raw
    
    start = time.perf_counter()
    results = app.poll_once()
    elapsed = time.perf_counter() - start
    
    count = sum(len(msgs) for msgs in results.values())
    rate = count / elapsed if elapsed > 0 else 0
    
    return {
        "messages": count,
        "time_sec": elapsed,
        "rate_msgs_sec": rate,
    }


def benchmark_cpp_core():
    """Benchmark C++ buffer directly."""
    if not has_cpp_core():
        return {"error": "C++ core not available"}
    
    return benchmark_cpp_core(iterations=100000)


if __name__ == "__main__":
    print("=== Glinx Performance Comparison ===\n")
    
    # Python benchmark
    print("Testing Python-only implementation...")
    py_result = benchmark_python_only()
    print(f"  Messages: {py_result['messages']}")
    print(f"  Time: {py_result['time_sec']:.3f}s")
    print(f"  Rate: {py_result['rate_msgs_sec']:.0f} msgs/sec")
    
    print()
    
    # C++ benchmark
    print("Testing C++ core...")
    cpp_result = benchmark_cpp_core()
    
    if "error" in cpp_result:
        print(f"  {cpp_result['error']}")
    else:
        print(f"  Iterations: {cpp_result['iterations']}")
        print(f"  Push time: {cpp_result['push_time_us']:.0f} µs")
        print(f"  Drain time: {cpp_result['drain_time_us']:.0f} µs")
        print(f"  Push rate: {cpp_result['push_rate_mhz']:.2f} M msgs/sec")
        print(f"  Drain rate: {cpp_result['drain_rate_mhz']:.2f} M msgs/sec")
        
        # Calculate speedup
        if py_result['rate_msgs_sec'] > 0:
            speedup = (cpp_result['push_rate_mhz'] * 1e6) / py_result['rate_msgs_sec']
            print(f"\n🚀 C++ core is {speedup:.0f}x faster than Python-only")
    
    print("\n=== Summary ===")
    print("Python: Good for network protocols (MQTT), low-frequency sensors")
    print("C++ Core: Essential for high-frequency sensors (IMU, accelerometers, force)")
    print("\nHybrid architecture gives best of both worlds:")
    print("  ✓ Real-time hardware ingestion (C++)")
    print("  ✓ Semantic enrichment (Python)")
    print("  ✓ AI/LLM integration (Python)")
