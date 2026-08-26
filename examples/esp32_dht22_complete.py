"""Complete ESP32 DHT22 example with auto-reconnect and logging.

Hardware setup:
1. Upload examples/esp32_sketches/esp32_dht22_serial.ino to ESP32
2. Connect ESP32 via USB
3. Note the COM port (e.g., COM3 on Windows, /dev/ttyUSB0 on Linux)
4. Run this script

Features:
- Automatic serial reconnection
- Historical data logging to SQLite
- Threshold-based alerts
- MCP tool exposure for AI agents
"""

from glinx import Glinx
import logging

logging.basicConfig(level=logging.INFO)

app = Glinx()

@app.sensor(
    "esp32_dht22",
    protocol="serial",
    port="COM3",  # Change to your port
    baudrate=115200,
    parser="json",
    fields={
        "temperature_c": "temperature_celsius",
        "humidity_pct": "relative_humidity",
    },
    sensor_type="environmental",
    location="room.desk",
    unit="C/%",
)
def esp32_dht22(raw):
    """C++ driver handles serial with auto-reconnect."""
    return raw


@app.rule("esp32_dht22", when="temperature_celsius > 30", priority="MEDIUM")
def high_temperature(event):
    return "Temperature above 30C - room getting hot"


@app.rule("esp32_dht22", when="relative_humidity > 70", priority="MEDIUM")
def high_humidity(event):
    return "Humidity above 70% - consider dehumidifier"


@app.rule("esp32_dht22", when="temperature_celsius < 18", priority="LOW")
def low_temperature(event):
    return "Temperature below 18C - room getting cold"


@app.on_event("high_temperature")
def handle_high_temp(event):
    """Real-time callback when threshold exceeded."""
    logging.warning(f"ALERT: {event.description}")
    logging.info(f"  Temperature: {event.payload.get('temperature_celsius')}C")
    logging.info(f"  Humidity: {event.payload.get('relative_humidity')}%")
    # Could trigger: fan control, notification, etc.


if __name__ == "__main__":
    print("Starting ESP32 DHT22 monitoring...")
    print("C++ serial driver with automatic reconnection")
    print()
    
    # Start MCP server for AI agents
    app.serve()
    
    # Agent can now call:
    # - get_esp32_dht22_status() -> latest temperature/humidity
    # - drain_glinx_events() -> alerts and anomalies
