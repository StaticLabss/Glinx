"""Real hardware example: Arduino sending sensor data over Serial.

Arduino sketch:
```cpp
void setup() {
  Serial.begin(115200);
}

void loop() {
  // JSON format
  Serial.print("{\"temperature\":");
  Serial.print(analogRead(A0) * 0.48828125);
  Serial.print(",\"light\":");
  Serial.print(analogRead(A1));
  Serial.println("}");
  
  delay(100);  // 10 Hz
}
```

Or CSV format:
```cpp
void loop() {
  Serial.print(analogRead(A0) * 0.48828125);
  Serial.print(",");
  Serial.println(analogRead(A1));
  delay(100);
}
```
"""

from glinx import Glinx

app = Glinx()

# JSON format (auto-parsed by C++ driver)
@app.sensor(
    "arduino_json",
    protocol="serial",
    port="COM3",  # Change to your port (/dev/ttyUSB0 on Linux)
    baudrate=115200,
    parser="json",
    fields={
        "temperature": "temperature_c",
        "light": "light_level",
    },
    sensor_type="multi",
    location="arduino.sensors",
)
def arduino_json(raw):
    """C++ driver reads serial at 115200 baud with <100µs latency."""
    return raw


# CSV format
@app.sensor(
    "arduino_csv",
    protocol="serial",
    port="COM4",
    baudrate=115200,
    parser="csv",
    csv_fields=["temperature_c", "light_level"],
    sensor_type="multi",
    location="arduino.sensors",
)
def arduino_csv(raw):
    """CSV parsing in C++ for minimal overhead."""
    return raw


@app.rule("arduino_json", when="temperature_c > 30", priority="MEDIUM")
def high_temp(event):
    return "Temperature above 30°C"


@app.rule("arduino_json", when="light_level < 100", priority="LOW")
def dark_detected(event):
    return "Low light detected"


@app.summary(["arduino_json"], interval_seconds=10, label="sensor_summary")
def periodic_status(event):
    return "10-second sensor summary"


if __name__ == "__main__":
    print("Starting Arduino serial monitoring...")
    print("C++ driver handles high-speed serial I/O")
    print()
    
    # MCP server mode - expose to AI agents
    app.serve()
    
    # Agents can now call:
    # - get_arduino_json_status() → latest sensor readings
    # - drain_glinx_events() → get all threshold/anomaly events
