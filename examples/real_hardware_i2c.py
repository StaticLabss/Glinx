"""Real hardware example: MPU6050 IMU on Raspberry Pi.

Connect MPU6050 to:
- VCC → 3.3V
- GND → GND
- SCL → GPIO 3 (SCL)
- SDA → GPIO 2 (SDA)

Enable I2C: sudo raspi-config → Interface Options → I2C → Enable
Install i2c-tools: sudo apt install i2c-tools
Check device: i2cdetect -y 1 (should show 0x68)
"""

from glinx import Glinx

app = Glinx()

# Automatically uses C++ driver for I2C (1000x faster than Python)
@app.sensor(
    "mpu6050",
    protocol="i2c",
    bus="/dev/i2c-1",
    device_address=0x68,  # MPU6050 default address
    register_address=0x3B,  # ACCEL_XOUT_H register
    read_length=14,  # 6 accel + 2 temp + 6 gyro bytes
    poll_interval_us=10000,  # 100 Hz sampling
    sensor_type="mpu6050",
    fields={
        "accel_x": "acceleration_x",
        "accel_y": "acceleration_y",
        "accel_z": "acceleration_z",
        "gyro_x": "angular_velocity_x",
        "gyro_y": "angular_velocity_y",
        "gyro_z": "angular_velocity_z",
    },
    sensor_type="imu",
    location="device.imu",
    unit="g/dps",
)
def mpu6050(raw):
    """C++ core handles high-frequency I2C reads."""
    return raw


@app.rule("mpu6050", when="abs(acceleration_z) > 15", priority="HIGH")
def impact_detected(event):
    return "Strong impact or fall detected on Z-axis"


@app.rule("mpu6050", when="abs(angular_velocity_x) > 200", priority="MEDIUM")
def rapid_rotation(event):
    return "Rapid rotation detected"


@app.on_event("impact_detected")
def handle_impact(event):
    print(f"⚠️  IMPACT: {event.description}")
    print(f"    Timestamp: {event.timestamp}")
    print(f"    Data: {event.payload}")


if __name__ == "__main__":
    print("Starting MPU6050 IMU monitoring...")
    print("Using C++ core for real-time I2C ingestion")
    print()
    
    # Run headless with event callbacks
    app.run(interval=0.1)  # Poll every 100ms
    
    # Or start MCP server for AI agents:
    # app.serve()
