<p align="center">
  <img src="docs/logo.png" alt="Glinx Logo" width="220" />
</p>

# Glinx

**The Universal Hardware to Agent Middleware**

Glinx is a Python middleware framework that connects physical hardware to AI agents without custom adapter code. It ingests sensor data from any protocol, enriches it with semantic meaning, and exposes clean MCP-compatible tools that any agent can reason over. Built for the era of physical AI and robotics.

> *Wire once. Think forever.*

## Quickstart

```python
from glinx import Glinx

app = Glinx()

@app.sensor("room_temp", protocol="mqtt", broker="localhost", topics=["home/temp"])
def room_temp(raw):
    return {"temperature_c": raw["t"], "humidity_pct": raw["h"]}

@app.rule("room_temp", when="temperature_c > 40", priority="HIGH")
def overheat(event):
    return "Room temperature critically high"

app.serve()  # MCP server is live — any agent can call get_room_temp_status()
```

That's it. Your sensor is now an MCP tool.

## Install

```bash
pip install glinx                  # core only
pip install glinx[mqtt]            # + MQTT driver (ESP32, IoT)
pip install glinx[serial]          # + Serial/UART driver (Arduino, Pi)
pip install glinx[mcp]             # + MCP server support
pip install glinx[all]             # everything
```

For development:

```bash
uv sync --extra dev
uv run pytest
```

## How It Works

```
  Hardware (MQTT / Serial / BLE / CAN / Camera / ...)
      │
      ▼
  Glinx Ingestion Layer ─── protocol drivers normalize data
      │
      ▼
  Schema + Semantic Layer ── auto-infer types, enrich with meaning
      │
      ▼
  Event Filter Layer ─────── rules, anomaly detection, summaries
      │
      ▼
  Agent Bridge ───────────── MCP tools exposed to any LLM agent
      │
      ▼
  AI Agent (LangGraph / LangChain / AutoGen / custom)
```

Raw sensor data like `{"p": 58.4, "temp": 31.5}` becomes:

```json
{
  "sensor": "left_fingertip",
  "sensor_type": "force_sensor",
  "location": "robot.hand.left.fingertip",
  "contact_pressure_kPa": 58.4,
  "surface_temperature_kPa": 31.5,
  "semantic_summary": "left_fingertip at robot.hand.left.fingertip: contact_pressure=58.4, surface_temperature=31.5"
}
```

The agent sees meaning, not bytes.

## Examples

### MQTT Sensor (ESP32, IoT devices)

```python
from glinx import Glinx

app = Glinx()

@app.sensor(
    "ultrasonic",
    protocol="mqtt",
    broker="192.168.1.100",
    topics=["robot/distance"],
    fields={"dist_cm": "distance"},
    sensor_type="proximity",
    location="robot.front",
    unit="cm",
)
def ultrasonic(raw):
    return raw

@app.rule("ultrasonic", when="distance_cm < 30", priority="HIGH")
def collision_warning(event):
    return "Obstacle within collision range"

app.serve()
```

### Serial Sensor (Arduino, Raspberry Pi)

```python
from glinx import Glinx

app = Glinx()

@app.sensor(
    "imu",
    protocol="serial",
    port="COM3",          # or /dev/ttyUSB0 on Linux
    baudrate=115200,
    fields={"ax": "accel_x", "ay": "accel_y", "az": "accel_z"},
    sensor_type="imu",
    location="robot.base",
)
def imu(raw):
    return raw

@app.rule("imu", when="abs(accel_z) > 15", priority="HIGH")
def fall_detected(event):
    return "Fall detected based on Z-axis acceleration"

app.serve()
```

### Mock Sensor (testing without hardware)

```python
from glinx import Glinx

app = Glinx()

@app.sensor(
    "finger",
    protocol="mock",
    payloads=[{"p": 23.4, "temp": 31.1}, {"p": 58.4, "temp": 31.5}],
    fields={"p": "contact_pressure", "temp": "surface_temperature"},
    sensor_type="force_sensor",
    location="robot.hand.left.fingertip",
    unit="kPa",
)
def finger(raw):
    return raw

@app.rule("finger", when="contact_pressure_kPa > 50", priority="HIGH")
def grip_overload(event):
    return "Grip pressure exceeded safe threshold"

app.serve()
```

### Event Callbacks (headless mode)

```python
from glinx import Glinx

app = Glinx()

@app.sensor("temp", protocol="mock", payloads=[{"t": 55}])
def temp(raw):
    return {"temperature": raw["t"]}

@app.rule("temp", when="temperature > 50", priority="HIGH", label="hot")
def hot_rule(event):
    return "Too hot"

@app.on_event("hot")
def handle_hot(event):
    print(f"🔥 Alert: {event.description}")

app.run(interval=1.0)  # no MCP, just poll + fire callbacks
```

## CLI

### Run a Python app

```bash
glinx run demo:app                       # like uvicorn main:app
```

### YAML config mode (power users)

```bash
glinx inspect-config --config glinx.yaml  # show detected sources/sensors
glinx print-tools --config glinx.yaml     # show generated MCP tool specs
glinx start --config glinx.yaml --serve-mcp  # start MCP server
```

## YAML Configuration (Advanced)

For complex setups with many sensors, use `glinx.yaml` instead of decorators:

```yaml
glinx:
  name: demo_robot
  agent_bridge: mcp

ingestion:
  sources:
    - id: base_imu
      protocol: mqtt
      broker: localhost
      topics: [robot/imu]
    - id: left_fingertip
      protocol: serial
      port: /dev/ttyUSB0
      baudrate: 115200

sensors:
  - id: base_imu
    type: imu
    location: robot.base
    fields:
      ax: accel_x
      ay: accel_y
      az: accel_z
  - id: left_fingertip
    type: force_sensor
    location: robot.hand.left.fingertip
    unit: kPa
    fields:
      p: contact_pressure
      temp: surface_temperature

event_rules:
  - sensor: left_fingertip
    condition: contact_pressure_kPa > 50
    priority: HIGH
    label: grip_overload

summary_windows:
  - sensors: [base_imu, left_fingertip]
    interval_seconds: 5
    label: periodic_status
```

```bash
glinx start --config glinx.yaml --serve-mcp
```

## Supported Protocols

| Protocol | Status | Install |
|---|---|---|
| Mock (testing) | ✅ Built-in | `pip install glinx` |
| MQTT | ✅ Implemented | `pip install glinx[mqtt]` |
| Serial / UART | ✅ Implemented | `pip install glinx[serial]` |
| WebSocket | 🔜 Planned | — |
| BLE | 🔜 Planned | — |
| CAN bus | 🔜 Planned | — |
| ROS2 | 🔜 Planned | — |
| Camera (OpenCV) | 🔜 Planned | — |

## Key Features

- **Decorator API** — `@app.sensor()`, `@app.rule()`, like FastAPI for hardware
- **Auto MCP tool generation** — sensors become agent-callable tools automatically
- **Semantic enrichment** — raw fields get human-readable names, units, and summaries
- **Event filtering** — threshold rules, z-score anomaly detection, summary windows
- **Config-driven or code-driven** — decorators for simplicity, YAML for complex setups
- **Protocol drivers** — pluggable, community-extensible driver registry
- **Async-native** — built on `asyncio` for concurrent hardware ingestion

## Architecture

```
src/glinx/
  app.py           Decorator-based Glinx API (primary interface)
  runtime.py       Orchestration layer
  config.py        YAML configuration models (Pydantic)
  models.py        Core message, event, and snapshot models
  schema.py        Schema inference engine
  semantic.py      Semantic enrichment logic
  events.py        Rule engine, anomaly detection, summary windows
  bus.py           Internal async pub/sub bus
  cli.py           CLI entrypoint (Typer)
  drivers/
    base.py        BaseDriver ABC + DriverRegistry
    mock.py        Mock driver for testing
    mqtt.py        MQTT driver (aiomqtt)
    serial.py      Serial/UART driver (pyserial-asyncio-fast)
  bridges/
    mcp.py         MCP bridge (FastMCP)
tests/
  test_app.py      Decorator API tests
  test_runtime.py  Runtime integration tests
  test_events.py   Event filter tests
  test_drivers.py  Driver tests
  test_bridge.py   MCP bridge tests
```

## Roadmap

### v0.1 (current)
- ✅ Decorator-based API
- ✅ Mock, MQTT, Serial drivers
- ✅ Schema inference + semantic enrichment
- ✅ Rule-based events + anomaly detection
- ✅ MCP bridge scaffold
- ✅ CLI with `glinx run`

### v0.2
- WebSocket driver
- BLE driver
- CAN bus driver
- Camera modality handler

### v0.3
- ROS2 topic bridge
- Audio modality (Whisper integration)
- LangGraph / LangChain bridges
- Web dashboard for live sensor monitoring

### v1.0
- Auto-discovery for known sensor types
- Distributed multi-node runtime
- Edge deployment (Raspberry Pi, Jetson Nano)
- Latency and quality benchmarking

## Development

```bash
uv sync --extra dev
uv run pytest -v
```

## License

MIT
