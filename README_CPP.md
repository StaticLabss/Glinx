# Glinx C++ Core

High-performance real-time sensor ingestion layer for IoT devices.

## Why C++?

Python hits performance limits with high-frequency sensor data:
- **Accelerometers**: 100-1000 Hz
- **IMUs**: 400-1000 Hz  
- **Force sensors**: 100+ Hz
- **Multiple sensors**: 1000s of events/second

The C++ core eliminates GIL constraints and provides:
- **< 1µs latency** sensor-to-buffer
- **10,000+ msgs/sec** sustained throughput
- **Lock-free** circular buffers
- **Zero-copy** IPC to Python

## Architecture

```
┌─────────────────────────────────────────┐
│  Hardware (Serial, I2C, SPI, CAN...)    │
└────────────────┬────────────────────────┘
                 │
        ┌────────▼─────────┐
        │  C++ Core Layer  │  ◄─ Real-time ingestion
        │  - Drivers       │     Lock-free buffers
        │  - Ring buffer   │     < 1ms latency
        │  - IPC           │
        └────────┬─────────┘
                 │ Shared Memory
        ┌────────▼─────────┐
        │  Python Bridge   │  ◄─ Semantic enrichment
        │  - Schema        │     MCP tools
        │  - Events        │     AI integration
        │  - MCP Server    │
        └──────────────────┘
```

## Building

### Prerequisites

**Windows:**
- Visual Studio 2022
- CMake 3.20+
- Python 3.11+

**Linux:**
```bash
sudo apt install build-essential cmake python3-dev
```

**macOS:**
```bash
brew install cmake python@3.11
```

### Build Commands

**Windows:**
```powershell
.\build-cpp.ps1                # Build only
.\build-cpp.ps1 --test         # Build + run tests
.\build-cpp.ps1 --bench        # Build + run benchmarks
```

**Linux/macOS:**
```bash
chmod +x build-cpp.sh
./build-cpp.sh                 # Build only
./build-cpp.sh --test          # Build + run tests
./build-cpp.sh --bench         # Build + run benchmarks
```

**Manual build:**
```bash
cd glinx-core
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build .
```

## Python Integration

The C++ core is transparently integrated via `_glinx_core` module:

```python
from glinx.core import has_cpp_core, CppRuntimeBridge

# Check if C++ core is available
print(f"C++ core: {has_cpp_core()}")

# Automatic fallback to Python
config = {
    "sources": [
        {
            "id": "imu",
            "protocol": "serial",
            "options": {"port": "COM3", "baudrate": 115200}
        }
    ]
}

with CppRuntimeBridge(config) as bridge:
    messages = bridge.get_messages()
    stats = bridge.get_stats()
```

## Benchmarks

Run benchmarks to verify performance targets:

```bash
# Latency test (target: < 1µs P99)
./glinx-core/build/latency_bench

# Throughput test (target: 10k msgs/sec)
./glinx-core/build/throughput_bench 1000 5
```

Expected output:
```
=== Glinx Buffer Latency Benchmark ===
Push Latency:
  Mean: 45 ns
  P99:  120 ns ✓ PASS

=== Glinx Throughput Benchmark ===
Target rate: 1000 msgs/sec
Actual: 1000.3 msgs/sec ✓ PASS
```

## Supported Protocols

| Protocol | Status | Platform |
|----------|--------|----------|
| Serial/UART | ✅ | Windows, Linux, macOS |
| I2C | ✅ | Linux (Raspberry Pi, etc.) |
| SPI | ✅ | Linux (Raspberry Pi, etc.) |
| CAN bus | 🔜 | Linux |

## Performance Targets

- ✅ **Latency**: < 1ms sensor-to-buffer
- ✅ **Throughput**: 10,000+ events/sec sustained
- ✅ **CPU**: < 20% single core @ 1kHz
- ✅ **Memory**: Bounded buffers, no hot-path allocations

## Development

### Project Structure

```
glinx-core/
├── include/glinx/
│   ├── buffer.hpp         # Lock-free ring buffer
│   ├── driver.hpp         # Base driver interface
│   ├── ipc.hpp           # Shared memory IPC
│   └── drivers/
│       ├── serial.hpp    # Serial/UART
│       ├── i2c.hpp      # I2C
│       └── spi.hpp      # SPI
├── src/
│   ├── buffer.cpp
│   ├── driver.cpp
│   ├── ipc.cpp
│   └── drivers/
│       ├── serial.cpp
│       ├── i2c.cpp
│       └── spi.cpp
├── bindings/
│   └── python.cpp        # nanobind Python bindings
├── tests/
│   └── test_buffer.cpp   # Unit tests (Google Test)
└── benchmarks/
    ├── latency_bench.cpp
    └── throughput_bench.cpp
```

### Adding New Drivers

1. Create header in `include/glinx/drivers/your_driver.hpp`
2. Inherit from `Driver` base class
3. Implement `poll_loop()` method
4. Add to CMakeLists.txt
5. Register in Python bridge

Example:
```cpp
class MyDriver : public Driver {
protected:
    void poll_loop() override {
        while (!stop_requested()) {
            // Read sensor data
            // Create SensorMessage
            // push_message(msg)
        }
    }
};
```

## Testing

```bash
cd glinx-core/build
ctest --output-on-failure
```

## License

MIT
