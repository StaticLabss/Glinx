# Glinx Architecture

## System Overview

Glinx bridges the gap between physical hardware sensors and AI agents using a hybrid C++/Python architecture optimized for real-time IoT data processing.

```
┌────────────────────────────────────────────────────────────────┐
│                        AI Agent Layer                          │
│  (LangGraph, LangChain, AutoGen, Custom Agents)                │
└────────────────────────┬───────────────────────────────────────┘
                         │ MCP Protocol
┌────────────────────────▼───────────────────────────────────────┐
│                    Python Bridge Layer                         │
│  • Semantic enrichment   • MCP tool generation                 │
│  • Schema inference      • Event filtering                     │
│  • Rule engine           • Anomaly detection                   │
└────────────────────────┬───────────────────────────────────────┘
                         │ Shared Memory (IPC)
┌────────────────────────▼───────────────────────────────────────┐
│                     C++ Core Layer                             │
│  • Real-time ingestion   • Lock-free buffers                   │
│  • Protocol drivers      • <1ms latency                        │
│  • 10k+ msgs/sec         • Zero GIL contention                 │
└────────────────────────┬───────────────────────────────────────┘
                         │
┌────────────────────────▼───────────────────────────────────────┐
│                    Hardware Layer                              │
│  Serial/UART • I2C • SPI • CAN • MQTT • WebSocket              │
└────────────────────────────────────────────────────────────────┘
```

## Component Breakdown

### 1. Hardware Layer
Physical sensors and communication protocols:
- **Serial/UART**: Arduino, ESP32, GPS modules (9600-921600 baud)
- **I2C**: IMUs (MPU6050/9250), pressure sensors (BMP280), temperature sensors
- **SPI**: High-speed ADCs, displays, SD cards (up to 50 MHz)
- **CAN**: Automotive sensors, industrial equipment (250 kbps - 1 Mbps)
- **MQTT**: IoT devices over WiFi/Ethernet (network-bound)
- **WebSocket**: Web-based sensors, remote devices

### 2. C++ Core Layer

**Purpose**: Handle high-frequency sensor data without Python GIL constraints.

**Key Components**:

#### Ring Buffer (Lock-Free SPSC)
```cpp
template <typename T, size_t Capacity>
class RingBuffer {
    // Single-producer, single-consumer
    // Zero heap allocations in hot path
    // Cache-line aligned head/tail
};
```

- **Capacity**: 16,384 messages (configurable)
- **Latency**: < 100ns push/pop
- **Throughput**: 10M+ ops/sec

#### Driver Base Class
```cpp
class Driver {
    virtual void poll_loop() = 0;  // Runs in dedicated thread
    bool push_message(const SensorMessage& msg);
protected:
    SensorBuffer* buffer_;
    std::atomic<bool> stop_flag_;
};
```

All drivers inherit from `Driver` and run in isolated threads.

#### Supported Drivers

| Driver | Frequency | Latency | Platform |
|--------|-----------|---------|----------|
| Serial | Up to 921600 baud | <100µs | All |
| I2C | 100 kHz - 3.4 MHz | <50µs | Linux |
| SPI | Up to 50 MHz | <10µs | Linux |
| CAN | 250 kbps - 1 Mbps | <20µs | Linux (planned) |

#### IPC Layer
Shared memory communication with Python:
- **Header**: Message count (uint32_t)
- **Body**: Array of `SensorMessage` structs
- **Size**: 64 KB default (1000+ messages)
- **Platform**: Windows (CreateFileMapping), Linux (shm_open)

### 3. Python Bridge Layer

**Purpose**: Semantic enrichment and AI integration.

**Key Components**:

#### Schema Engine
Auto-infers JSON schemas from sensor data:
```python
{"x": 1.5, "y": 2.3} → {"type": "object", "properties": {"x": {"type": "number"}, ...}}
```

#### Semantic Tagger
Enriches raw data with context:
```python
Input:  {"p": 58.4, "temp": 31.5}
Output: {
    "contact_pressure_kPa": 58.4,
    "surface_temperature_C": 31.5,
    "sensor_type": "force_sensor",
    "location": "robot.hand.left.fingertip",
    "semantic_summary": "left_fingertip: contact_pressure=58.4, temp=31.5"
}
```

#### Event Filter
Three types of event detection:

1. **Rule-based**: Threshold conditions
   ```python
   @app.rule("temp", when="temperature_c > 50", priority="HIGH")
   ```

2. **Anomaly detection**: Z-score based outliers
   ```python
   EventFilterConfig(anomaly_stddev_threshold=3.0)
   ```

3. **Summary windows**: Periodic aggregations
   ```python
   @app.summary(sensors=["imu", "temp"], interval_seconds=5)
   ```

#### Message Flow
```
C++ Buffer → drain() → Python GlinxMessage → schema_engine.observe()
                                          → semantic_tagger.enrich()
                                          → event_filter.process()
                                          → message_bus.publish()
```

### 4. MCP Bridge Layer

Exposes sensors as MCP tools for AI agents:

```json
{
  "name": "get_base_imu_status",
  "description": "Returns current semantic state for hardware source 'base_imu'",
  "inputSchema": {"type": "object", "properties": {}},
  "outputSchema": {
    "type": "object",
    "properties": {
      "acceleration_x_g": {"type": "number"},
      "acceleration_y_g": {"type": "number"},
      "acceleration_z_g": {"type": "number"},
      ...
    }
  }
}
```

Agent can call:
```python
result = tools.get_base_imu_status()
# Returns latest enriched sensor reading
```

### 5. AI Agent Layer

Agents use Glinx tools to:
- Query sensor state on-demand
- Drain event queues
- Make decisions based on physical world state
- Control actuators (future)

## Performance Characteristics

### Benchmarks

**Buffer Latency** (test_buffer.cpp):
```
Push: Mean 45ns, P99 120ns ✓
Drain: 2.5M msgs/sec ✓
```

**Throughput** (throughput_bench.cpp):
```
Target: 10,000 msgs/sec
Actual: 10,003 msgs/sec ✓
Dropped: 0.01% ✓
```

**Python Comparison** (benchmark_comparison.py):
```
Python-only: ~1,000 msgs/sec
C++ core:    ~1,000,000 msgs/sec
Speedup:     1000x
```

### Resource Usage

| Component | CPU | Memory |
|-----------|-----|--------|
| C++ Core (1 kHz) | <5% single core | 2-4 MB |
| Python Bridge | <10% single core | 20-40 MB |
| Total @ 10 sensors | <20% single core | 50 MB |

## Data Flow Example

High-frequency IMU on I2C:

```
1. Hardware: MPU6050 @ 1kHz on /dev/i2c-1
   └─> Registers 0x3B-0x48 (14 bytes)

2. C++ Driver (i2c.cpp):
   └─> read_register() every 1ms
   └─> parse_sensor_data() → {ax, ay, az, gx, gy, gz}
   └─> buffer_.push(msg) [45ns]

3. IPC (shared memory):
   └─> ipc_->write_messages(buffer_.drain())

4. Python Bridge (core.py):
   └─> bridge.get_messages()
   └─> semantic_tagger.enrich() → adds location, units
   └─> event_filter.process() → check thresholds

5. MCP Bridge (mcp.py):
   └─> snapshot.latest_message = enriched
   └─> Agent calls get_base_imu_status() → returns enriched data
```

**Total latency**: < 2ms (hardware → agent query)

## Threading Model

```
Main Thread (Python):
  ├─> GlinxRuntime.poll_once() [asyncio]
  ├─> EventFilter.process()
  └─> MCPBridge.serve() [stdio/HTTP]

C++ Threads (one per driver):
  ├─> SerialDriver::poll_loop()
  ├─> I2CDriver::poll_loop()
  └─> SPIDriver::poll_loop()

Background:
  └─> Message Bus subscribers (asyncio tasks)
```

## Deployment Targets

### Development
- Windows/macOS/Linux workstation
- USB serial devices
- Mock sensors for testing

### Edge Devices
- **Raspberry Pi 3/4/5**: I2C, SPI, Serial
- **NVIDIA Jetson Nano/Xavier**: High-performance AI + sensors
- **BeagleBone Black**: Industrial I/O

### Production
- Docker containers with device pass-through
- Kubernetes with privileged pods for hardware access
- systemd services for auto-start

## Configuration

### Decorator API (Simple)
```python
app = Glinx()

@app.sensor("imu", protocol="i2c", bus="/dev/i2c-1", device_address=0x68)
def imu(raw): return raw

app.serve()
```

### YAML API (Complex)
```yaml
glinx:
  name: robot_sensors
  agent_bridge: mcp

ingestion:
  sources:
    - id: base_imu
      protocol: i2c
      bus: /dev/i2c-1
      device_address: 0x68

sensors:
  - id: base_imu
    type: imu
    location: robot.base
```

## Extension Points

### Custom Drivers
```cpp
class MyDriver : public glinx::Driver {
protected:
    void poll_loop() override {
        while (!stop_requested()) {
            // Your sensor logic
            SensorMessage msg = read_sensor();
            push_message(msg);
        }
    }
};
```

### Custom Semantic Enrichment
```python
from glinx.semantic import SemanticTagger

class CustomTagger(SemanticTagger):
    def enrich(self, sensor, data):
        # Your enrichment logic
        return enriched_data
```

### Custom Event Filters
```python
from glinx.events import EventFilter

class MLAnomalyFilter(EventFilter):
    def process(self, message):
        # ML-based anomaly detection
        if self.model.predict(message.parsed) > threshold:
            yield self.create_event("ml_anomaly", ...)
```

## Security Considerations

1. **Hardware Access**: Requires root/admin for I2C/SPI on Linux
2. **Shared Memory**: Only accessible by same-user processes
3. **MCP Server**: Runs on localhost by default (stdio transport)
4. **Input Validation**: All sensor data validated before enrichment

## Future Enhancements

1. **CAN Bus Support**: Automotive/industrial protocols
2. **RTOS Integration**: Hard real-time guarantees
3. **Distributed Runtime**: Multi-node sensor networks
4. **GPU Acceleration**: Real-time computer vision sensors
5. **Edge AI**: On-device inference before cloud transmission
