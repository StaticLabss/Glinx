"""Example: High-frequency accelerometer with C++ core.

This demonstrates the hybrid architecture in action:
- C++ core handles 1kHz IMU data from I2C
- Python layer enriches and exposes to AI agents
"""

from glinx import Glinx

app = Glinx()

# The @sensor decorator automatically uses C++ driver for I2C
@app.sensor(
    "base_imu",
    protocol="i2c",
    bus="/dev/i2c-1",  # Raspberry Pi
    device_address=0x68,  # MPU6050 address
    sensor_type="mpu6050",
    register_address=0x3B,  # ACCEL_XOUT_H
    read_length=14,  # 6 accel + 2 temp + 6 gyro bytes
    poll_interval_us=1000,  # 1kHz sampling
    fields={
        "accel_x": "acceleration_x_g",
        "accel_y": "acceleration_y_g",
        "accel_z": "acceleration_z_g",
        "gyro_x": "angular_velocity_x_dps",
        "gyro_y": "angular_velocity_y_dps",
        "gyro_z": "angular_velocity_z_dps",
    },
    sensor_type="imu",
    location="robot.base",
    unit="g/dps",
)
def base_imu(raw):
    """
    C++ core reads raw I2C data at 1kHz with <1ms latency.
    Python enriches it semantically.
    """
    return raw  # Already parsed by C++ driver


@app.rule("base_imu", when="abs(acceleration_z_g) > 15", priority="HIGH")
def fall_detected(event):
    return "Robot fall detected based on Z-axis acceleration"


@app.rule("base_imu", when="abs(angular_velocity_x_dps) > 250", priority="MEDIUM")
def rapid_rotation(event):
    return "Rapid rotation detected on X-axis"


# Event callback for real-time alerts
@app.on_event("fall_detected")
def handle_fall(event):
    print(f"🚨 ALERT: {event.description}")
    # Could trigger emergency stop, send notification, etc.


if __name__ == "__main__":
    # Start MCP server - agents can now query IMU status
    app.serve()
    
    # The tool `get_base_imu_status()` is automatically available to agents
    # Sample response:
    # {
    #   "status": "ok",
    #   "source_id": "base_imu",
    #   "timestamp": 1234567890.123,
    #   "data": {
    #     "acceleration_x_g": 0.12,
    #     "acceleration_y_g": -0.05,
    #     "acceleration_z_g": 9.81,
    #     "angular_velocity_x_dps": 2.3,
    #     "angular_velocity_y_dps": -1.1,
    #     "angular_velocity_z_dps": 0.4,
    #     "semantic_summary": "base_imu at robot.base: stable orientation, Z-axis gravity normal"
    #   }
    # }
